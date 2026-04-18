"""YNAB implementation of the BudgetService protocol."""

from datetime import date

from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabApiClient


class YnabBudgetService:
    """Wraps ``YnabApiClient`` as an instance-method service.

    Satisfies the ``BudgetService`` protocol so it can be injected into
    ``convert_bank_transactions`` or replaced with a different implementation
    without changing call sites.
    """

    def __init__(self, token: str) -> None:
        self._token = token

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
    ) -> TransactionsResponse:
        return YnabApiClient.get_transactions(self._token, budget_id, since_date)