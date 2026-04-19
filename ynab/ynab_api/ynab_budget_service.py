"""YNAB implementation of the BudgetService protocol."""

from datetime import date
from typing import List

from ynab.bank.transaction import BankTransaction
from ynab.ynab_api.transaction_uploader import to_api_payloads
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

    def create_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: List[BankTransaction],
    ) -> int:
        payloads = to_api_payloads(transactions, account_id)
        return YnabApiClient.create_transactions(self._token, budget_id, payloads)