"""YNAB REST API client."""

import logging
from datetime import date
from typing import Any, Dict, List, NamedTuple, Optional

import requests

log = logging.getLogger(__name__)


class YnabTransaction(NamedTuple):
    id: str
    date: str
    amount: int
    memo: Optional[str]
    cleared: str
    approved: bool
    flag_color: Optional[str]
    account_id: str
    payee_id: Optional[str]
    category_id: Optional[str]
    transfer_account_id: Optional[str]
    transfer_transaction_id: Optional[str]
    matched_transaction_id: Optional[str]
    import_id: Optional[str]
    import_payee_name: Optional[str]
    import_payee_name_original: Optional[str]
    debt_transaction_type: Optional[str]
    deleted: bool
    account_name: str
    payee_name: Optional[str]
    category_name: Optional[str]


class TransactionsResponse(NamedTuple):
    """Response from the YNAB transactions endpoint."""

    transactions: List[YnabTransaction]
    server_knowledge: int


class YnabApiError(Exception):
    """Raised when the YNAB API returns an unexpected response."""


class YnabApiClient:
    BASE_URL = "https://api.ynab.com/v1"

    @staticmethod
    def get_transactions(
        token: str,
        budget_id: str,
        since_date: date,
    ) -> TransactionsResponse:
        """Fetch transactions from the YNAB API.

        Returns all transactions on or after ``since_date``.

        Note: the endpoint is single-response (no page-number pagination).

        Args:
            token: YNAB personal access token.
            budget_id: YNAB budget UUID.
            since_date: Fetch transactions on or after this date.

        Returns:
            ``TransactionsResponse`` with the transaction list and new knowledge mark.

        Raises:
            YnabApiError: On HTTP 429 (rate limit) or malformed response body.
            requests.HTTPError: On other non-2xx HTTP errors.
        """
        query: Dict[str, Any] = {"since_date": since_date.isoformat()}
        url = f"{YnabApiClient.BASE_URL}/budgets/{budget_id}/transactions"

        response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=query)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise YnabApiError(
                f"YNAB API rate limit reached. Retry after {retry_after} seconds."
            )

        response.raise_for_status()

        try:
            data = response.json()["data"]
            raw_transactions = data["transactions"]
            server_knowledge: int = data["server_knowledge"]
        except (KeyError, ValueError) as exc:
            raise YnabApiError(f"Unexpected YNAB API response format: {exc}") from exc

        transactions = [
            YnabTransaction(**{field: t[field] for field in YnabTransaction._fields})
            for t in raw_transactions
        ]
        log.info("GET %s → %d transactions, server_knowledge=%d", response.url, len(transactions), server_knowledge)
        return TransactionsResponse(transactions=transactions, server_knowledge=server_knowledge)

    @staticmethod
    def create_transactions(
        token: str,
        budget_id: str,
        transactions: List[Dict[str, Any]],
    ) -> int:
        """POST new transactions to the YNAB API.

        Args:
            token: YNAB personal access token.
            budget_id: YNAB budget UUID.
            transactions: List of transaction payload dicts ready to send.

        Returns:
            Count of newly created transactions (duplicates excluded).

        Raises:
            YnabApiError: On HTTP 429 (rate limit) or malformed response body.
            requests.HTTPError: On other non-2xx HTTP errors.
        """
        url = f"{YnabApiClient.BASE_URL}/budgets/{budget_id}/transactions"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"transactions": transactions},
        )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise YnabApiError(
                f"YNAB API rate limit reached. Retry after {retry_after} seconds."
            )

        response.raise_for_status()

        try:
            data = response.json()["data"]
            created_ids: List[str] = data["transaction_ids"]
            duplicate_ids: List[str] = data["duplicate_import_ids"]
        except (KeyError, ValueError) as exc:
            raise YnabApiError(f"Unexpected YNAB API response format: {exc}") from exc

        log.info(
            "POST %s → %d created, %d duplicates skipped",
            url, len(created_ids), len(duplicate_ids),
        )
        return len(created_ids)
