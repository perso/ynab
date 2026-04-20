"""Protocol for budget service integrations."""

from datetime import date
from typing import List, Protocol, runtime_checkable

from ynab.bank.transaction import BankTransaction
from ynab.ynab_api.ynab_api_client import TransactionsResponse


@runtime_checkable
class BudgetService(Protocol):
    """Structural protocol for any budget service that can supply and create transactions.

    ``YnabBudgetService`` satisfies this protocol.
    A future alternative budget provider needs only implement these methods
    to be usable as a drop-in replacement.
    """

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
    ) -> TransactionsResponse: ...

    def create_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: List[BankTransaction],
        approved: bool = False,
    ) -> int: ...
