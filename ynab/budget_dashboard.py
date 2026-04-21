"""Budget spending dashboard for the current month."""

import logging
from pathlib import Path
from typing import Callable, List

from ynab.utilities.config_util import (
    read_accounts_config,
    read_credentials_file,
    read_tracking_accounts_config,
)
from ynab.ynab_api.ynab_api_client import BudgetMonth, CategorySummary
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ynab"


def _collect_budget_ids(config_path: str) -> List[str]:
    """Return distinct budget IDs from accounts.toml, in declaration order."""
    accounts = read_accounts_config(config_path)
    tracking = read_tracking_accounts_config(config_path)

    seen: set = set()
    budget_ids: List[str] = []

    for account_cfg in accounts.values():
        bid = account_cfg.budget_id
        if bid and bid not in seen:
            budget_ids.append(bid)
            seen.add(bid)

    for tracking_cfg in tracking.values():
        bid = tracking_cfg.budget_id
        if bid not in seen:
            budget_ids.append(bid)
            seen.add(bid)

    return budget_ids


def _active_categories(month: BudgetMonth) -> List[CategorySummary]:
    """Return non-hidden, non-deleted categories that have budget or activity."""
    return [
        c for c in month.categories
        if not c.hidden and not c.deleted and (c.budgeted != 0 or c.activity != 0)
    ]


def render_dashboard(month: BudgetMonth) -> None:
    """Print a spending summary table for *month* to stdout.

    Categories are grouped by category group name. Overspent categories
    (negative balance) are flagged with a warning marker.
    """
    visible = _active_categories(month)

    if not visible:
        print(f"\n{month.month}: no active categories to display.")
        return

    name_width = max(len(c.name) for c in visible)
    name_width = max(name_width, len("Category"))

    col_widths = (name_width, 10, 10, 12)
    header = (
        f"{'Category':<{col_widths[0]}}  "
        f"{'Budgeted':>{col_widths[1]}}  "
        f"{'Spent':>{col_widths[2]}}  "
        f"{'Remaining':>{col_widths[3]}}"
    )
    separator = "─" * len(header)

    print(f"\n{month.month}")
    print(header)
    print(separator)

    prev_group: str = ""
    for cat in visible:
        if cat.category_group_name != prev_group:
            prev_group = cat.category_group_name

        budgeted = f"{cat.budgeted / 1000.0:,.2f}"
        spent = f"{cat.activity / 1000.0:,.2f}"
        remaining = cat.balance / 1000.0
        warn = "⚠ " if remaining < 0 else ""
        remaining_str = f"{warn}{remaining:,.2f}"

        print(
            f"{cat.name:<{col_widths[0]}}  "
            f"{budgeted:>{col_widths[1]}}  "
            f"{spent:>{col_widths[2]}}  "
            f"{remaining_str:>{col_widths[3]}}"
        )


def run_status(
    budget_service_factory: Callable[[str], YnabBudgetService] = YnabBudgetService,
) -> None:
    """Fetch the current month's budget summary and render a spending table.

    Budget IDs are read from all ``accounts.toml`` entries (regular and
    tracking accounts).  Credentials are loaded from the environment or the
    credentials file.
    """
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
        month = service.get_budget_month(budget_id)
        render_dashboard(month)
