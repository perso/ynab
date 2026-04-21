"""YNAB implementation of the BudgetService protocol."""

from datetime import date
from typing import List, Optional

from ynab.bank.transaction import BankTransaction
from ynab.ynab_api import ynab_api_client
from ynab.ynab_api.transaction_uploader import to_api_payloads
from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabAccount


class YnabBudgetService:
    """Wraps ``ynab_api_client`` as an instance-method service.

    Satisfies the ``BudgetService`` protocol so it can be injected into
    ``convert_bank_transactions`` or replaced with a different implementation
    without changing call sites.
    """

    def __init__(self, token: str) -> None:
        """Initialise the service with a YNAB personal access token.

        :param token: YNAB personal access token used to authenticate all API calls.
        """
        self._token = token

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
    ) -> TransactionsResponse:
        """Fetch transactions for a budget from the YNAB API.

        :param budget_id: YNAB budget UUID to query.
        :param since_date: Only return transactions on or after this date.
        :returns: Response containing the transaction list and server knowledge value.
        """
        return ynab_api_client.get_transactions(self._token, budget_id, since_date)

    def create_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: List[BankTransaction],
        approved: bool = False,
        memo_template: Optional[str] = None,
    ) -> int:
        """Upload bank transactions to a YNAB account.

        Converts ``transactions`` to API payloads via ``to_api_payloads`` before
        posting.  YNAB deduplicates by ``import_id``, so repeated calls with the
        same input are safe.

        :param budget_id: YNAB budget UUID to post transactions into.
        :param account_id: YNAB account UUID to associate each transaction with.
        :param transactions: Bank transactions to upload.
        :param approved: Whether to mark each transaction as approved in YNAB.
        :param memo_template: Optional template string for the memo field.
        :returns: Number of transactions accepted by the YNAB API.
        """

        payloads = to_api_payloads(transactions, account_id, approved=approved, memo_template=memo_template)
        return ynab_api_client.create_transactions(self._token, budget_id, payloads)

    def get_account(self, budget_id: str, account_id: str) -> YnabAccount:
        """Fetch a single account from the YNAB API.

        :param budget_id: YNAB budget UUID.
        :param account_id: YNAB account UUID.
        :returns: ``YnabAccount`` with id, name, and cleared_balance (milliunits).
        """
        return ynab_api_client.get_account(self._token, budget_id, account_id)
