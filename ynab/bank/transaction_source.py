"""Protocol for bank transaction data sources."""

from typing import List, Protocol, runtime_checkable

from ynab.bank.transaction import BankTransaction


@runtime_checkable
class BankTransactionSource(Protocol):
    """Structural protocol for anything that provides a list of bank transactions.

    ``TransactionReader`` satisfies this protocol without modification.
    A future bank API client need only implement ``read_transactions`` to be
    usable as a drop-in replacement.
    """

    def read_transactions(self) -> List[BankTransaction]: ...
