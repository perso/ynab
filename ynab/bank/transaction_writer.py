"""Writer for YNAB-compatible import CSVs."""

import csv
from pathlib import Path
from typing import List, Optional, Union

from ynab.bank.transaction import BankTransaction

_HEADER = ["Date", "Payee", "Memo", "Amount"]


def format_memo(txn: BankTransaction, template: Optional[str]) -> str:
    """Format a memo string from a bank transaction using a template.

    The template may reference ``{category}`` and ``{sub_category}`` fields
    from the transaction (e.g. ``"{category} / {sub_category}"``).
    Returns an empty string when ``template`` is ``None`` or empty.
    """
    if not template:
        return ""
    return template.format(category=txn.category, sub_category=txn.sub_category)


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
