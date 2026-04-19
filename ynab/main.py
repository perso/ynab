"""Entry point for the YNAB bank import tool."""

import argparse
import logging
from pathlib import Path
from typing import Callable, List, Optional

from ynab.bank.duplicate_filter import DEFAULT_DATE_TOLERANCE_DAYS, derive_since_date, filter_already_in_ynab
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

_CONFIG_DIR = Path.home() / ".config" / "ynab"


def convert_bank_transactions(
    source_factory: Callable[[str], List[BankTransaction]] = read_transactions,
    budget_service_factory: Callable[[str], BudgetService] = YnabBudgetService,
    input_dir: str = "./input",
    output_dir: str = "./output",
    accounts_config_path: str = "./accounts.toml",
    dedup_enabled: bool = False,
    upload_enabled: bool = False,
    global_budget_id: Optional[str] = None,
) -> None:
    """Convert Finnish bank CSV exports to YNAB import CSVs.

    Reads all ``*.csv`` files from ``input_dir``, converts them, and writes
    YNAB import CSVs to ``output_dir``.  Input filenames must follow the
    format ``<account_no>_<suffix>.csv``.

    Set ``dedup_enabled=True`` to fetch existing YNAB transactions and filter
    out bank rows that already appear in the budget.  Set ``upload_enabled=True``
    to POST transactions directly to the YNAB API.  Both require ``account_id``
    per account in ``accounts_config_path``, and a budget ID from either
    ``budget_id`` in that file or ``global_budget_id``.

    ``source_factory`` and ``budget_service_factory`` can be overridden in
    tests without modifying this function.
    """
    account_configs = read_accounts_config(accounts_config_path)
    need_api = dedup_enabled or upload_enabled
    token: Optional[str] = read_credentials_file() if need_api else None
    budget_service: Optional[BudgetService] = budget_service_factory(token) if need_api else None  # type: ignore[arg-type]

    mappings = form_file_paths(
        input_dir=input_dir,
        output_dir=output_dir,
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
                    f"--dedup requires complete config for account '{mapping.account_no}': "
                    f"set 'account_id' in accounts.toml and either 'budget_id' in accounts.toml "
                    f"or pass --budget-id."
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
                    "and either 'budget_id' in accounts.toml or pass --budget-id.",
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
    parser = argparse.ArgumentParser(
        description="Convert Finnish bank CSV exports to YNAB import CSVs.",
    )
    parser.add_argument(
        "--input-dir", default=str(_CONFIG_DIR / "input"), metavar="PATH",
        help=f"directory containing bank export CSVs (default: {_CONFIG_DIR / 'input'})",
    )
    parser.add_argument(
        "--output-dir", default=str(_CONFIG_DIR / "output"), metavar="PATH",
        help=f"directory for YNAB import CSVs (default: {_CONFIG_DIR / 'output'})",
    )
    parser.add_argument(
        "--accounts", default=str(_CONFIG_DIR / "accounts.toml"), metavar="PATH",
        help=f"path to accounts.toml (default: {_CONFIG_DIR / 'accounts.toml'})",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="upload transactions directly to the YNAB API",
    )
    parser.add_argument(
        "--dedup", action="store_true",
        help="fetch existing YNAB transactions and filter duplicates before writing",
    )
    parser.add_argument(
        "--budget-id", metavar="UUID",
        help="global YNAB budget ID; per-account value in accounts.toml takes precedence",
    )
    args = parser.parse_args()

    convert_bank_transactions(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        accounts_config_path=args.accounts,
        dedup_enabled=args.dedup,
        upload_enabled=args.upload,
        global_budget_id=args.budget_id,
    )


if __name__ == "__main__":
    run_app()