"""Interactive balance updater for YNAB tracking accounts."""

import datetime
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional

from ynab.bank.duplicate_filter import to_milliunits
from ynab.budget_service import BudgetService
from ynab.utilities.config_util import (
    TrackingAccountConfig,
    read_credentials_file,
    read_tracking_accounts_config,
)
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ynab"


def _prompt_new_balance(name: str, current_balance: float) -> Optional[float]:
    """Show the current YNAB balance and prompt for a new value.

    Returns ``None`` when the user presses Enter without typing (skip).
    Re-prompts on invalid input.
    """
    print(f"\n{name}")
    print(f"  Current YNAB balance: {current_balance:,.2f}")
    while True:
        raw = input("  New balance (Enter to skip): ").strip()
        if not raw:
            return None
        try:
            return float(raw.replace(",", "."))
        except ValueError:
            print("  Invalid number, try again (or press Enter to skip).")


def update_tracking_accounts(
    budget_service: BudgetService,
    tracking_configs: List[TrackingAccountConfig],
    *,
    today: datetime.date,
    prompt_fn: Callable[[str, float], Optional[float]] = _prompt_new_balance,
) -> None:
    """Core loop: prompt for each tracking account and post any balance adjustments.

    For each configured account:
    - Fetches the current YNAB cleared balance.
    - Calls ``prompt_fn`` to ask for the real-world value (returns None to skip).
    - If the value differs, posts a reconciled adjustment transaction.
    - Prints a net-worth-change summary when at least one account was updated.

    :param budget_service: Service used to read and write YNAB data.
    :param tracking_configs: Ordered list of accounts to update.
    :param today: Date stamped on each adjustment transaction.
    :param prompt_fn: Callable that receives (name, current_balance) and returns
        the new balance as a float, or None to skip.
    """
    if not tracking_configs:
        log.info("No tracking accounts configured.")
        log.info("Add [tracking_accounts] sections to %s", _CONFIG_DIR / "accounts.toml")
        return

    total_adjustment_milliunits = 0
    updated_count = 0

    for cfg in tracking_configs:
        account = budget_service.get_account(cfg.budget_id, cfg.account_id)
        current_balance = account.cleared_balance / 1000.0

        new_balance = prompt_fn(cfg.name, current_balance)
        if new_balance is None:
            log.info("  Skipped.")
            continue

        new_milliunits = to_milliunits(new_balance)
        adjustment_milliunits = new_milliunits - account.cleared_balance

        if adjustment_milliunits == 0:
            log.info("  No change.")
            continue

        budget_service.create_adjustment(
            cfg.budget_id,
            cfg.account_id,
            adjustment_milliunits,
            new_milliunits,
            today,
        )

        adjustment = adjustment_milliunits / 1000.0
        sign = "+" if adjustment >= 0 else ""
        log.info("  Adjustment: %s%.2f  ✓", sign, adjustment)

        total_adjustment_milliunits += adjustment_milliunits
        updated_count += 1

    if updated_count > 0:
        total = total_adjustment_milliunits / 1000.0
        sign = "+" if total >= 0 else ""
        print(f"\n{'─' * 40}")
        print(f"Net worth change: {sign}{total:,.2f}")


def run_tracking_update(
    budget_service_factory: Callable[[str], BudgetService] = YnabBudgetService,  # type: ignore[assignment]
) -> None:
    """Orchestration entry point called from the CLI.

    Reads tracking account config, acquires a YNAB token, and runs the
    interactive update loop.
    """
    config_path = str(_CONFIG_DIR / "accounts.toml")
    tracking_configs_by_slug: Dict[str, TrackingAccountConfig] = read_tracking_accounts_config(config_path)
    configs = list(tracking_configs_by_slug.values())

    if not configs:
        log.info("No tracking accounts configured.")
        log.info("Add [tracking_accounts] sections to %s", _CONFIG_DIR / "accounts.toml")
        return

    token = read_credentials_file()
    budget_service = budget_service_factory(token)
    update_tracking_accounts(budget_service, configs, today=datetime.date.today())
