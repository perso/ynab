"""Writer for YNAB-compatible import CSVs."""

import csv
from pathlib import Path
from typing import List, Union

from ynab.bank.transaction import BankTransaction

_HEADER = ["Date", "Payee", "Memo", "Amount"]


def write_transactions(file_name: Union[str, Path], transactions: List[BankTransaction]) -> None:
    """Write transactions to the output CSV, overwriting any existing content."""
    with open(Path(file_name), mode="w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(_HEADER)
        for transaction in transactions:
            writer.writerow(
                [transaction.date, transaction.payee, "", transaction.amount]
            )
