"""Entry point for the YNAB bank import tool."""

import logging
from datetime import date
from pathlib import Path

from ynab.bank.transaction_filters import filter_unchecked_transactions
from ynab.bank.transaction_reader import TransactionReader
from ynab.bank.transaction_writer import TransactionWriter
from ynab.utilities.config_util import read_credentials_file
from ynab.utilities.fs_util import form_file_paths
from ynab.ynab_api.ynab_api_client import YnabApiClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Configuration — edit these values or replace with a config file / CLI flags.
_BUDGET_ID = "8241ed93-0dcf-4ecd-8a24-9a55efdf90ae"
_SINCE_DATE = date(2023, 4, 20)
_ACCOUNTNO_BUDGET_MAP = {
    "FI5380002631119863": "MyAccount",
    "FI7880207710867395": "MasterCard",
}
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def fetch_transactions() -> None:
    """Fetch and log recent transactions from the YNAB API."""
    token = read_credentials_file()
    transactions = YnabApiClient.get_transactions(token, _BUDGET_ID, _SINCE_DATE)
    for t in transactions:
        log.info(t)


def convert_bank_transactions() -> None:
    """Convert Finnish bank CSV exports to YNAB import CSVs."""
    paths = form_file_paths(
        input_dir=str(_DATA_DIR / "input"),
        output_dir=str(_DATA_DIR / "output"),
        accountno_budget_map=_ACCOUNTNO_BUDGET_MAP,
    )

    for input_path, output_path in paths:
        log.info("%s -> %s", input_path, output_path)
        transactions = TransactionReader(input_path).read_transactions()
        transactions = filter_unchecked_transactions(transactions)
        transactions = sorted(set(transactions))
        TransactionWriter(output_path).write_transactions(transactions)


def run_app() -> None:
    convert_bank_transactions()


if __name__ == "__main__":
    run_app()
