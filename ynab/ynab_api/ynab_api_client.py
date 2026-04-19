"""YNAB REST API client."""

import logging
from collections import namedtuple
from datetime import date
from typing import Any, Dict, List, NamedTuple, Optional

import requests

log = logging.getLogger(__name__)

YnabTransaction = namedtuple(
    "YnabTransaction",
    [
        "id", "date", "amount", "memo", "cleared", "approved", "flag_color",
        "account_id", "payee_id", "category_id", "transfer_account_id",
        "transfer_transaction_id", "matched_transaction_id", "import_id",
        "import_payee_name", "import_payee_name_original", "debt_transaction_type",
        "deleted", "account_name", "payee_name", "category_name",
    ],
)


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
        last_knowledge_of_server: Optional[int] = None,
    ) -> TransactionsResponse:
        """Fetch transactions from the YNAB API.

        When ``last_knowledge_of_server`` is provided the endpoint returns only
        transactions changed since that knowledge mark (delta sync), which keeps
        payloads small on subsequent runs. The returned ``server_knowledge``
        should be persisted and passed on the next call.

        When omitted, all transactions on or after ``since_date`` are returned.

        Note: the endpoint is single-response (no page-number pagination).
        Use delta sync via ``last_knowledge_of_server`` for large budgets.

        Args:
            token: YNAB personal access token.
            budget_id: YNAB budget UUID.
            since_date: Fetch transactions on or after this date (ignored when
                ``last_knowledge_of_server`` is provided).
            last_knowledge_of_server: Knowledge mark from a previous call.

        Returns:
            ``TransactionsResponse`` with the transaction list and new knowledge mark.

        Raises:
            YnabApiError: On HTTP 429 (rate limit) or malformed response body.
            requests.HTTPError: On other non-2xx HTTP errors.
        """
        params = f"since_date={since_date.isoformat()}"
        if last_knowledge_of_server is not None:
            params += f"&last_knowledge_of_server={last_knowledge_of_server}"
        url = f"{YnabApiClient.BASE_URL}/budgets/{budget_id}/transactions?{params}"

        response = requests.get(url, headers={"Authorization": f"Bearer {token}"})

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
        log.info("GET %s → %d transactions, server_knowledge=%d", url, len(transactions), server_knowledge)
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
