"""Protocol for budget service integrations."""

from datetime import date
from typing import Optional, Protocol, runtime_checkable

from ynab.ynab_api.ynab_api_client import TransactionsResponse


@runtime_checkable
class BudgetService(Protocol):
    """Structural protocol for any budget service that can supply transactions.

    ``YnabBudgetService`` satisfies this protocol.
    A future alternative budget provider needs only implement
    ``get_transactions`` to be usable as a drop-in replacement.
    """

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
        last_knowledge_of_server: Optional[int] = None,
    ) -> TransactionsResponse: ...
