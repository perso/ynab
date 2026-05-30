"""Spending trend analysis: last month vs 3-month rolling average."""

import logging
from datetime import date
from pathlib import Path
from typing import Callable, List, NamedTuple, Tuple

from ynab.budget_dashboard import _collect_budget_ids, _display_width, _ljust
from ynab.utilities.config_util import read_credentials_file
from ynab.ynab_api.ynab_api_client import BudgetMonth
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ynab"


class CategoryTrend(NamedTuple):
    name: str
    category_group_name: str
    current_spend: float  # euros spent last month (positive = outflow)
    avg_spend: float      # 3-month average spend (positive = outflow)
    change: float         # current_spend - avg_spend; positive = climbing


def _add_months(d: date, n: int) -> date:
    """Return the first day of the month n months from d (n may be negative)."""
    total = d.year * 12 + (d.month - 1) + n
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _month_label(month_str: str) -> str:
    """'2026-04-01' → 'April 2026'"""
    d = date.fromisoformat(month_str)
    return d.strftime("%B %Y")


def _month_short(month_str: str) -> str:
    """'2026-04-01' → 'Apr 2026'"""
    d = date.fromisoformat(month_str)
    return d.strftime("%b %Y")


def _avg_range_label(month_strs: List[str]) -> str:
    """['2026-03-01', '2026-02-01', '2026-01-01'] → 'Jan–Mar 2026'"""
    dates = sorted(date.fromisoformat(m) for m in month_strs)
    start = dates[0].strftime("%b")
    end = dates[-1].strftime("%b %Y")
    return f"{start}–{end}"


def compute_trends(
    comparison: BudgetMonth,
    history: List[BudgetMonth],
    top_n: int,
) -> Tuple[List[CategoryTrend], List[CategoryTrend]]:
    """Compute climbing and easing categories for *comparison* vs *history*.

    Inclusion rule: a category must have non-zero activity in *comparison* AND
    non-zero activity in at least one of the *history* months.  New categories
    (no history) and absent-this-month categories are both excluded.

    The 3-month average always divides by 3, so months with zero activity pull
    the average down and make infrequent spend stand out naturally.

    Returns (climbing, easing), each sorted by absolute change and capped at top_n.
    """
    history_activity: dict[str, list[int]] = {}
    for month in history:
        for cat in month.categories:
            if cat.hidden or cat.deleted:
                continue
            history_activity.setdefault(cat.name, []).append(cat.activity)

    trends: List[CategoryTrend] = []
    for cat in comparison.categories:
        if cat.hidden or cat.deleted or cat.activity == 0:
            continue
        past = history_activity.get(cat.name, [])
        if not any(a != 0 for a in past):
            continue
        avg_activity = sum(past) / 3
        current_spend = -cat.activity / 1000.0
        avg_spend = -avg_activity / 1000.0
        change = current_spend - avg_spend
        trends.append(CategoryTrend(
            name=cat.name,
            category_group_name=cat.category_group_name,
            current_spend=current_spend,
            avg_spend=avg_spend,
            change=change,
        ))

    climbing = sorted(
        (t for t in trends if t.change > 0),
        key=lambda t: -t.change,
    )[:top_n]
    easing = sorted(
        (t for t in trends if t.change < 0),
        key=lambda t: t.change,
    )[:top_n]

    return climbing, easing


def _render_section(
    title: str,
    trends: List[CategoryTrend],
    name_width: int,
    col_label: str,
) -> None:
    col_widths = (name_width, 10, 10, 10)
    header = (
        f"{title:<{col_widths[0]}}  "
        f"{col_label:>{col_widths[1]}}  "
        f"{'3mo avg':>{col_widths[2]}}  "
        f"{'Change':>{col_widths[3]}}"
    )
    print(f"\n{header}")
    print("─" * len(header))

    if not trends:
        print("  (none)")
        return

    for t in trends:
        current = f"{t.current_spend:,.2f}"
        avg = f"{t.avg_spend:,.2f}"
        sign = "+" if t.change > 0 else ""
        change = f"{sign}{t.change:,.2f}"
        print(
            f"  {_ljust(t.name, col_widths[0] - 2)}  "
            f"{current:>{col_widths[1]}}  "
            f"{avg:>{col_widths[2]}}  "
            f"{change:>{col_widths[3]}}"
        )


def render_trends(
    comparison_month: str,
    avg_months: List[str],
    climbing: List[CategoryTrend],
    easing: List[CategoryTrend],
) -> None:
    """Print the spending trends report to stdout."""
    all_trends = climbing + easing
    if not all_trends:
        print(f"\n{_month_label(comparison_month)}: no trend data to display.")
        return

    name_width = max(_display_width(t.name) + 2 for t in all_trends)
    name_width = max(name_width, len("Climbing"), len("Easing"))

    col_label = _month_short(comparison_month)
    avg_label = _avg_range_label(avg_months)

    print(f"\nSpending trends — {_month_label(comparison_month)} vs 3-month avg ({avg_label})")
    _render_section("Climbing", climbing, name_width, col_label)
    _render_section("Easing", easing, name_width, col_label)


def run_trends(
    top_n: int = 5,
    today: date | None = None,
    budget_service_factory: Callable[[str], YnabBudgetService] = YnabBudgetService,
) -> None:
    """Fetch budget months and render a spending trends report.

    Compares last completed month (M-1) against the 3 months before it
    (M-2, M-3, M-4).  Budget IDs are read from accounts.toml.
    """
    if today is None:
        today = date.today()

    comparison_date = _add_months(today, -1)
    avg_dates = [_add_months(today, -i) for i in range(2, 5)]

    comparison_str = comparison_date.isoformat()
    avg_strs = [d.isoformat() for d in avg_dates]

    config_path = str(_CONFIG_DIR / "accounts.toml")
    budget_ids = _collect_budget_ids(config_path)

    if not budget_ids:
        log.error(
            "No budget IDs found in %s. "
            "Add budget_id to at least one account entry.",
            config_path,
        )
        raise SystemExit(1)

    token = read_credentials_file()
    service = budget_service_factory(token)

    for budget_id in budget_ids:
        comparison_month = service.get_budget_month(budget_id, comparison_str)
        history = [service.get_budget_month(budget_id, m) for m in avg_strs]
        climbing, easing = compute_trends(comparison_month, history, top_n)
        render_trends(comparison_month.month, [m.month for m in history], climbing, easing)
