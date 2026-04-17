"""Entry point for the YNAB bank import tool."""

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from dotenv import load_dotenv

from ynab.bank.duplicate_filter import DEFAULT_DATE_TOLERANCE_DAYS, filter_already_in_ynab
from ynab.bank.transaction_filters import filter_unchecked_transactions
from ynab.bank.transaction_reader import TransactionReader
from ynab.bank.transaction_source import BankTransactionSource
from ynab.bank.transaction_writer import TransactionWriter
from ynab.budget_service import BudgetService
from ynab.utilities.config_util import parse_accountno_budget_map, read_credentials_file
from ynab.utilities.fs_util import form_file_paths
from ynab.utilities.knowledge_cache import load_server_knowledge, save_server_knowledge
from ynab.ynab_api.ynab_api_client import YnabApiClient
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

_SINCE_DATE = date(2023, 4, 20)
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def fetch_transactions() -> None:
    """Fetch and log recent transactions from the YNAB API."""
    token = read_credentials_file()
    budget_id = os.environ["YNAB_BUDGET_ID"]
    response = YnabApiClient.get_transactions(token, budget_id, _SINCE_DATE)
    for t in response.transactions:
        log.info(t)


def convert_bank_transactions(
    source_factory: Callable[[str], BankTransactionSource] = TransactionReader,
    budget_service_factory: Callable[[str], BudgetService] = YnabBudgetService,
) -> None:
    """Convert Finnish bank CSV exports to YNAB import CSVs.

    Set ``YNAB_DEDUP_ENABLED=true`` to fetch existing YNAB transactions and
    filter out any bank rows that already appear in the budget.  Requires
    ``budget_id`` and ``account_id`` to be set for each account in
    ``YNAB_ACCOUNTNO_BUDGET_MAP``.

    ``source_factory`` and ``budget_service_factory`` can be overridden in
    tests or to swap in alternative data providers without modifying this
    function.

    On the first dedup run the full transaction history from the bank file's
    earliest date is fetched. Subsequent runs use YNAB's delta-sync mechanism
    (``last_knowledge_of_server``) to download only changes, keeping API calls
    fast and within the 200-request/hour rate limit.
    """
    account_configs = parse_accountno_budget_map(os.environ["YNAB_ACCOUNTNO_BUDGET_MAP"])
    dedup_enabled = os.environ.get("YNAB_DEDUP_ENABLED", "").lower() == "true"
    token: Optional[str] = read_credentials_file() if dedup_enabled else None
    budget_service: Optional[BudgetService] = budget_service_factory(token) if dedup_enabled else None  # type: ignore[arg-type]

    mappings = form_file_paths(
        input_dir=str(_DATA_DIR / "input"),
        output_dir=str(_DATA_DIR / "output"),
        accountno_budget_map={k: v.budget_name for k, v in account_configs.items()},
    )

    for mapping in mappings:
        log.info("%s -> %s", mapping.input_path, mapping.output_path)
        transactions = source_factory(mapping.input_path).read_transactions()
        transactions = filter_unchecked_transactions(transactions)

        if dedup_enabled and transactions:
            cfg = account_configs[mapping.account_no]
            if not cfg.budget_id or not cfg.account_id:
                raise ValueError(
                    f"YNAB_DEDUP_ENABLED=true but 'budget_id' and 'account_id' are missing "
                    f"for account '{mapping.account_no}'. Update YNAB_ACCOUNTNO_BUDGET_MAP."
                )
            since = min(t.date for t in transactions) - timedelta(days=DEFAULT_DATE_TOLERANCE_DAYS)
            last_knowledge = load_server_knowledge(cfg.budget_id, cfg.account_id)
            api_response = budget_service.get_transactions(  # type: ignore[union-attr]
                cfg.budget_id, since, last_knowledge_of_server=last_knowledge
            )
            save_server_knowledge(cfg.budget_id, cfg.account_id, api_response.server_knowledge)
            transactions = filter_already_in_ynab(
                transactions, api_response.transactions, account_id=cfg.account_id
            )

        transactions = sorted(set(transactions))
        TransactionWriter(mapping.output_path).write_transactions(transactions)


def run_app() -> None:
    convert_bank_transactions()


if __name__ == "__main__":
    run_app()
