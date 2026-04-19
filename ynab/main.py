"""Entry point for the YNAB bank import tool."""

import logging
import os
from pathlib import Path
from typing import Callable, List, Optional

from dotenv import load_dotenv

from ynab.bank.duplicate_filter import DEFAULT_DATE_TOLERANCE_DAYS, filter_already_in_ynab, derive_since_date
from ynab.bank.transaction import BankTransaction
from ynab.bank.transaction_filters import filter_unchecked_transactions
from ynab.bank.transaction_reader import read_transactions
from ynab.bank.transaction_writer import write_transactions
from ynab.budget_service import BudgetService
from ynab.utilities.config_util import read_accounts_config, read_credentials_file
from ynab.utilities.fs_util import form_file_paths
from ynab.ynab_api.ynab_api_client import TransactionsResponse
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def convert_bank_transactions(
    source_factory: Callable[[str], List[BankTransaction]] = read_transactions,
    budget_service_factory: Callable[[str], BudgetService] = YnabBudgetService,
    accounts_config_path: Optional[str] = None,
    dedup_enabled: bool = False,
    upload_enabled: bool = False,
    global_budget_id: Optional[str] = None,
) -> None:
    """Convert Finnish bank CSV exports to YNAB import CSVs.

    Set ``dedup_enabled=True`` to fetch existing YNAB transactions and
    filter out any bank rows that already appear in the budget.  Requires
    ``account_id`` per account in ``accounts.toml``, and a budget ID from
    either ``budget_id`` in ``accounts.toml`` or ``global_budget_id``
    (per-account value takes precedence).

    ``source_factory`` and ``budget_service_factory`` can be overridden in
    tests or to swap in alternative data providers without modifying this
    function.

    The YNAB API is called with a ``since_date`` derived from the earliest
    transaction date in the bank file minus the date-tolerance buffer, making
    each run idempotent for the same input data.
    """
    if accounts_config_path is None:
        accounts_config_path = str(_DATA_DIR.parent / "accounts.toml")
    account_configs = read_accounts_config(accounts_config_path)
    need_api = dedup_enabled or upload_enabled
    token: Optional[str] = read_credentials_file() if need_api else None
    budget_service: Optional[BudgetService] = budget_service_factory(token) if need_api else None  # type: ignore[arg-type]

    mappings = form_file_paths(
        input_dir=str(_DATA_DIR / "input"),
        output_dir=str(_DATA_DIR / "output"),
        accountno_budget_map={k: v.budget_name for k, v in account_configs.items()},
    )

    for mapping in mappings:
        log.info("%s -> %s", mapping.input_path, mapping.output_path)
        transactions = source_factory(mapping.input_path)
        transactions = filter_unchecked_transactions(transactions)
        cfg = account_configs[mapping.account_no]
        effective_budget_id = cfg.budget_id or global_budget_id

        if dedup_enabled and transactions:
            if not effective_budget_id or not cfg.account_id:
                raise ValueError(
                    f"YNAB_DEDUP_ENABLED=true but dedup config is incomplete for account "
                    f"'{mapping.account_no}': set 'account_id' in accounts.toml and either "
                    f"'budget_id' in accounts.toml or YNAB_BUDGET_ID in the environment."
                )
            tolerance = cfg.date_tolerance_days if cfg.date_tolerance_days is not None else DEFAULT_DATE_TOLERANCE_DAYS
            since = derive_since_date(transactions, tolerance)
            api_response: TransactionsResponse = budget_service.get_transactions(  # type: ignore[union-attr]
                effective_budget_id, since
            )
            transactions = filter_already_in_ynab(
                transactions, api_response.transactions, account_id=cfg.account_id,
                date_tolerance_days=tolerance,
            )

        transactions = sorted(set(transactions))
        write_transactions(mapping.output_path, transactions)

        if upload_enabled and transactions:
            if not effective_budget_id or not cfg.account_id:
                log.warning(
                    "Upload skipped for account '%s': set 'account_id' in accounts.toml "
                    "and either 'budget_id' in accounts.toml or YNAB_BUDGET_ID in the environment.",
                    mapping.account_no,
                )
            else:
                count = budget_service.create_transactions(  # type: ignore[union-attr]
                    effective_budget_id, cfg.account_id, transactions
                )
                log.info(
                    "Uploaded %d transaction(s) to YNAB for account '%s'",
                    count, mapping.account_no,
                )


def run_app() -> None:
    load_dotenv()
    
    convert_bank_transactions(
        accounts_config_path=os.environ.get("YNAB_ACCOUNTS_CONFIG"),
        dedup_enabled=os.environ.get("YNAB_DEDUP_ENABLED", "").lower() == "true",
        upload_enabled=os.environ.get("YNAB_UPLOAD_ENABLED", "").lower() == "true",
        global_budget_id=os.environ.get("YNAB_BUDGET_ID"),
    )


if __name__ == "__main__":
    run_app()
