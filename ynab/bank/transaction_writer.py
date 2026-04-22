"""Writer for YNAB-compatible import CSVs."""

import csv
from pathlib import Path
from typing import List, Optional, Union

from ynab.bank.transaction import BankTransaction

_HEADER = ["Date", "Payee", "Memo", "Amount"]


def format_memo(txn: BankTransaction, template: Optional[str]) -> str:
    """Format a memo string from a bank transaction.

    When the payee was harmonized, ``txn.original_payee`` holds the raw bank
    string and is prepended to the template output separated by `` | ``.
    The template may reference ``{category}`` and ``{sub_category}``.
    Returns an empty string when neither original payee nor template is present.
    """
    template_part = template.format(category=txn.category, sub_category=txn.sub_category) if template else ""
    parts = [p for p in (txn.original_payee, template_part) if p]
    return " | ".join(parts)


def write_transactions(
    file_name: Union[str, Path],
    transactions: List[BankTransaction],
    memo_template: Optional[str] = None,
) -> None:
    """Write transactions to the output CSV, overwriting any existing content."""
    with open(Path(file_name), mode="w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(_HEADER)
        for transaction in transactions:
            writer.writerow(
                [transaction.date, transaction.payee, format_memo(transaction, memo_template), transaction.amount]
            )
