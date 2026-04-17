"""Filters for bank transaction lists."""

from typing import List

from ynab.bank.transaction import BankTransaction, TransactionStatus


def filter_unchecked_transactions(transactions: List[BankTransaction]) -> List[BankTransaction]:
    """Keep only CLEARED transactions, filtering out PENDING and RECONCILED.

    PENDING transactions have not settled; RECONCILED transactions are already
    in YNAB. Only CLEARED ones are ready to import.

    Args:
        transactions: Input transaction list.

    Returns:
        Transactions with ``CLEARED`` status only.
    """
    return [t for t in transactions if t.status == TransactionStatus.CLEARED]
