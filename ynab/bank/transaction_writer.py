"""Writer for YNAB-compatible import CSVs."""

import csv
from pathlib import Path
from typing import List, Union

from ynab.bank.transaction import BankTransaction

_HEADER = ["Date", "Payee", "Memo", "Amount"]


class TransactionWriter:
    def __init__(self, file_name: Union[str, Path]):
        self.path = Path(file_name)

    def write_transactions(self, transactions: List[BankTransaction]) -> None:
        """Write transactions to the output CSV, overwriting any existing content."""
        with open(self.path, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(_HEADER)
            for transaction in transactions:
                writer.writerow(
                    [transaction.date, transaction.payee, "", transaction.amount]
                )
