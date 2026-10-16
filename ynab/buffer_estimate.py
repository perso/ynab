"""Emergency buffer estimate: how long the emergency fund lasts if income drops."""

import logging
import math
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from ynab.budget_dashboard import _display_width, _ljust
from ynab.spending_trends import _add_months
from ynab.utilities.config_util import (
    BufferConfig,
    BufferScenario,
    read_buffer_config,
    read_credentials_file,
)
from ynab.ynab_api.ynab_api_client import BudgetMonth
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ynab"
_EXCLUDED_GROUPS = ("Internal Master Category", "Credit Card Payments")
_BAR_WIDTH = 10


class CategoryCost(NamedTuple):
    """Average monthly cost of one category and the share kept in a crisis."""

    name: str
    group: str
    monthly_cost: float  # euros
    keep: float          # 0.0–1.0

    @property
    def crisis_cost(self) -> float:
        """Monthly cost after cutting down to the kept share."""
        return self.monthly_cost * self.keep


class ScenarioResult(NamedTuple):
    """Outcome of one income-loss scenario."""

    name: str
    net_income: float
    shortfall: float  # euros per month drawn from the buffer
    required: float   # euros needed to survive the whole scenario
    runway: float     # months the current buffer lasts; inf when income covers needs


def resolve_keep(group: str, name: str, keep_map: Dict[str, float]) -> float:
    """Return the keep ratio for a category: ``"Group: Name"`` beats ``"Group"``, default 1.0."""
    return keep_map.get(f"{group}: {name}", keep_map.get(group, 1.0))


def category_costs(
    history: List[BudgetMonth],
    keep_map: Dict[str, float],
    emergency_category: str,
) -> List[CategoryCost]:
    """Average monthly cost per category over *history*.

    Cost is ``max(avg outflow, avg assigned)`` so sinking funds count even in
    months nothing was spent.  The emergency category itself is saving, not cost.
    """
    totals: Dict[Tuple[str, str], Tuple[int, int]] = {}
    for month in history:
        for cat in month.categories:
            if cat.hidden or cat.deleted or cat.category_group_name in _EXCLUDED_GROUPS:
                continue
            if cat.name == emergency_category:
                continue
            key = (cat.category_group_name, cat.name)
            activity, budgeted = totals.get(key, (0, 0))
            totals[key] = (activity + cat.activity, budgeted + cat.budgeted)

    n = len(history)
    costs = []
    for (group, name), (activity, budgeted) in totals.items():
        monthly = max(-activity, budgeted, 0) / 1000.0 / n
        if monthly > 0:
            costs.append(CategoryCost(name, group, monthly, resolve_keep(group, name, keep_map)))
    return costs


def runway_months(balance: float, need: float, shortfall: float, delay: float) -> float:
    """Months *balance* lasts: full *need* during the income delay, then *shortfall*."""
    if need == 0:
        return math.inf
    delay_cost = need * delay
    if balance < delay_cost:
        return balance / need
    if shortfall == 0:
        return math.inf
    return delay + (balance - delay_cost) / shortfall


def scenario_result(need: float, scenario: BufferScenario, balance: float) -> ScenarioResult:
    """Evaluate *scenario* for a monthly crisis *need* against the current *balance*."""
    shortfall = max(0.0, need - scenario.net_income)
    required = need * scenario.income_delay_months + shortfall * scenario.months
    return ScenarioResult(
        name=scenario.name,
        net_income=scenario.net_income,
        shortfall=shortfall,
        required=required,
        runway=runway_months(balance, need, shortfall, scenario.income_delay_months),
    )


def buffer_target(need: float, results: List[ScenarioResult], floor_months: float) -> float:
    """Largest scenario requirement, but never below *floor_months* of crisis spending."""
    return max([need * floor_months] + [r.required for r in results])


def emergency_balance(month: BudgetMonth, category: str) -> float:
    """Return the euro balance of *category* in *month*.

    Raises:
        ValueError: If no category has that name.
    """
    for cat in month.categories:
        if cat.name == category and not cat.deleted:
            return cat.balance / 1000.0
    raise ValueError(f"Emergency category '{category}' not found in budget month {month.month}")


def _eur(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


def _group_totals(costs: List[CategoryCost]) -> List[Tuple[str, float, float]]:
    groups: Dict[str, Tuple[float, float]] = {}
    for c in costs:
        normal, crisis = groups.get(c.group, (0.0, 0.0))
        groups[c.group] = (normal + c.monthly_cost, crisis + c.crisis_cost)
    return [(g, normal, crisis) for g, (normal, crisis) in groups.items()]


def _render_costs(costs: List[CategoryCost]) -> None:
    rows = _group_totals(costs) + [
        ("Total", sum(c.monthly_cost for c in costs), sum(c.crisis_cost for c in costs))
    ]
    width = max(_display_width(name) for name, _, _ in rows) + 2
    print(f"\n  {_ljust('Monthly', width)}{'Normal':>9}{'Crisis':>9}")
    for name, normal, crisis in rows:
        print(f"  {_ljust(name, width)}{_eur(normal):>9}{_eur(crisis):>9}")


def _render_scenarios(results: List[ScenarioResult], balance: float) -> None:
    width = max(len(r.name) for r in results) + 2
    print(f"\n  {'Scenario':<{width}}{'Income':>9}{'Shortfall':>11}{'Needed':>9}{'Runway':>10}")
    for r in results:
        runway = "∞" if math.isinf(r.runway) else f"{r.runway:.1f} mo"
        flag = " ⚠" if balance < r.required else ""
        print(
            f"  {r.name:<{width}}{_eur(r.net_income):>9}{_eur(r.shortfall):>11}"
            f"{_eur(r.required):>9}{runway:>10}{flag}"
        )


def _bar(fraction: float) -> str:
    filled = round(min(max(fraction, 0.0), 1.0) * _BAR_WIDTH)
    return "█" * filled + "░" * (_BAR_WIDTH - filled)


def render_buffer(
    period: str,
    costs: List[CategoryCost],
    results: List[ScenarioResult],
    category: str,
    balance: float,
    target: float,
) -> None:
    """Print the buffer report to stdout."""
    print(f"\nEmergency buffer — based on {period}")
    _render_costs(costs)
    _render_scenarios(results, balance)
    fraction = balance / target if target else 1.0
    gap = balance - target
    sign = "+" if gap >= 0 else "−"
    print(
        f"\n  Target {_eur(target)}   {category} {_eur(balance)}  "
        f"{_bar(fraction)} {fraction:.0%}   ({sign}{_eur(abs(gap))})"
    )


def _period_label(months: List[str]) -> str:
    """['2026-10-01', …, '2025-11-01'] → 'Nov 2025–Oct 2026'"""
    dates = sorted(date.fromisoformat(m) for m in months)
    return f"{dates[0]:%b %Y}–{dates[-1]:%b %Y}"


def run_buffer(
    history_months: Optional[int] = None,
    today: Optional[date] = None,
    budget_service_factory: Callable[[str], YnabBudgetService] = YnabBudgetService,
) -> None:
    """Fetch budget history and print how long the emergency fund would last.

    Uses the last *history_months* complete months (default from config) and
    the current month's balance of the configured emergency category.
    """
    config_path = _CONFIG_DIR / "accounts.toml"
    config: Optional[BufferConfig] = read_buffer_config(config_path)
    if config is None:
        log.error("No [buffer] section in %s. See accounts.toml.example.", config_path)
        raise SystemExit(1)

    today = today or date.today()
    n = history_months or config.history_months
    month_strs = [_add_months(today, -i).isoformat() for i in range(1, n + 1)]

    service = budget_service_factory(read_credentials_file())
    history = [service.get_budget_month(config.budget_id, m) for m in month_strs]
    balance = emergency_balance(service.get_budget_month(config.budget_id), config.category)

    costs = category_costs(history, config.keep, config.category)
    need = sum(c.crisis_cost for c in costs)
    results = [scenario_result(need, s, balance) for s in config.scenarios]
    target = buffer_target(need, results, config.floor_months)
    render_buffer(_period_label(month_strs), costs, results, config.category, balance, target)
