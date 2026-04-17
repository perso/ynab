"""YNAB REST API client."""

from collections import namedtuple
from datetime import date
from typing import List

import requests

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


class YnabApiClient:
    BASE_URL = "https://api.youneedabudget.com/v1"

    @staticmethod
    def get_transactions(
        token: str, budget_id: str, since_date: date
    ) -> List[YnabTransaction]:
        """Fetch transactions from the YNAB API.

        Args:
            token: YNAB API bearer token.
            budget_id: YNAB budget UUID.
            since_date: Fetch transactions on or after this date.

        Returns:
            List of ``YnabTransaction`` namedtuples.

        Raises:
            requests.HTTPError: If the API returns a non-2xx status.
        """
        url = (
            f"{YnabApiClient.BASE_URL}/budgets/{budget_id}/transactions"
            f"?since_date={since_date.isoformat()}"
        )
        response = requests.get(url, headers={"Authorization": f"Bearer {token}"})
        response.raise_for_status()
        return [
            YnabTransaction(**{field: t[field] for field in YnabTransaction._fields})
            for t in response.json()["data"]["transactions"]
        ]
