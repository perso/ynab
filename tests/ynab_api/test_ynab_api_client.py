import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import requests

from ynab.ynab_api.ynab_api_client import (
    BASE_URL,
    TransactionsResponse,
    YnabAccount,
    YnabApiError,
    YnabTransaction,
    create_transactions,
    get_account,
    get_transactions,
)

_SAMPLE_RAW = {
    "id": "1",
    "date": "2023-04-01",
    "amount": 1000,
    "cleared": "cleared",
    "account_id": "a1",
    "deleted": False,
}

_SAMPLE_TRANSACTION = YnabTransaction(
    id="1",
    date="2023-04-01",
    amount=1000,
    cleared="cleared",
    account_id="a1",
    deleted=False,
)


def _mock_response(transactions: list, server_knowledge: int = 42, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"data": {"transactions": transactions, "server_knowledge": server_knowledge}}
    mock.raise_for_status.return_value = None
    return mock


class TestYnabApiClient(unittest.TestCase):
    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions(self, mock_get):
        mock_get.return_value = _mock_response([_SAMPLE_RAW], server_knowledge=42)

        result = get_transactions("test_token", "test_budget_id", date(2023, 1, 1))

        self.assertEqual(result, TransactionsResponse([_SAMPLE_TRANSACTION], 42))
        mock_get.assert_called_once_with(
            "https://api.ynab.com/v1/plans/test_budget_id/transactions",
            headers={"Authorization": "Bearer test_token"},
            params={"since_date": "2023-01-01"},
        )

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_raises_on_http_error(self, mock_get):
        mock = MagicMock()
        mock.status_code = 500
        mock.raise_for_status.side_effect = requests.HTTPError("500")
        mock_get.return_value = mock

        with self.assertRaises(requests.HTTPError):
            get_transactions("token", "budget", date(2023, 1, 1))

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_raises_ynab_api_error_on_429(self, mock_get):
        mock = MagicMock()
        mock.status_code = 429
        mock.headers = {"Retry-After": "60"}
        mock_get.return_value = mock

        with self.assertRaises(YnabApiError) as ctx:
            get_transactions("token", "budget", date(2023, 1, 1))

        self.assertIn("60", str(ctx.exception))

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_raises_ynab_api_error_on_malformed_body(self, mock_get):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"unexpected": "shape"}
        mock_get.return_value = mock

        with self.assertRaises(YnabApiError):
            get_transactions("token", "budget", date(2023, 1, 1))

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_empty_list(self, mock_get):
        mock_get.return_value = _mock_response([], server_knowledge=0)

        result = get_transactions("token", "budget", date(2023, 1, 1))

        self.assertEqual(result.transactions, [])
        self.assertEqual(result.server_knowledge, 0)

    def test_base_url_is_current_ynab_domain(self):
        self.assertEqual(BASE_URL, "https://api.ynab.com/v1")


def _mock_post_response(transaction_ids: list, duplicate_ids: list, status_code: int = 201) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"data": {"transaction_ids": transaction_ids, "duplicate_import_ids": duplicate_ids, "transactions": []}}
    mock.raise_for_status.return_value = None
    return mock


_SAMPLE_PAYLOAD = {
    "account_id": "a1",
    "date": "2023-04-20",
    "amount": -55000,
    "payee_name": "Coffee Shop",
    "cleared": "cleared",
    "approved": False,
    "import_id": "abc123",
}


class TestYnabApiClientCreateTransactions(unittest.TestCase):
    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_returns_created_count(self, mock_post):
        mock_post.return_value = _mock_post_response(["id1", "id2"], [])

        result = create_transactions("token", "budget-id", [_SAMPLE_PAYLOAD, _SAMPLE_PAYLOAD])

        self.assertEqual(result, 2)

    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_posts_to_correct_url(self, mock_post):
        mock_post.return_value = _mock_post_response(["id1"], [])

        create_transactions("tok", "bud", [_SAMPLE_PAYLOAD])

        mock_post.assert_called_once_with(
            "https://api.ynab.com/v1/plans/bud/transactions",
            headers={"Authorization": "Bearer tok", "Content-Type": "application/json"},
            json={"transactions": [_SAMPLE_PAYLOAD]},
        )

    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_excludes_duplicates_from_count(self, mock_post):
        mock_post.return_value = _mock_post_response(["id1"], ["dup-import-id"])

        result = create_transactions("token", "budget-id", [_SAMPLE_PAYLOAD, _SAMPLE_PAYLOAD])

        self.assertEqual(result, 1)

    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_raises_on_http_error(self, mock_post):
        mock = MagicMock()
        mock.status_code = 500
        mock.raise_for_status.side_effect = requests.HTTPError("500")
        mock_post.return_value = mock

        with self.assertRaises(requests.HTTPError):
            create_transactions("token", "budget-id", [_SAMPLE_PAYLOAD])

    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_raises_ynab_api_error_on_429(self, mock_post):
        mock = MagicMock()
        mock.status_code = 429
        mock.headers = {"Retry-After": "30"}
        mock_post.return_value = mock

        with self.assertRaises(YnabApiError) as ctx:
            create_transactions("token", "budget-id", [_SAMPLE_PAYLOAD])

        self.assertIn("30", str(ctx.exception))

    @patch("ynab.ynab_api.ynab_api_client.requests.post")
    def test_create_transactions_raises_ynab_api_error_on_malformed_body(self, mock_post):
        mock = MagicMock()
        mock.status_code = 201
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"unexpected": "shape"}
        mock_post.return_value = mock

        with self.assertRaises(YnabApiError):
            create_transactions("token", "budget-id", [_SAMPLE_PAYLOAD])


def _mock_account_response(account_id: str, name: str, cleared_balance: int, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"data": {"account": {
        "id": account_id,
        "name": name,
        "cleared_balance": cleared_balance,
    }}}
    mock.raise_for_status.return_value = None
    return mock


class TestGetAccount(unittest.TestCase):
    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_returns_ynab_account(self, mock_get):
        mock_get.return_value = _mock_account_response("a1", "Checking", 1234567)

        result = get_account("token", "budget-id", "a1")

        self.assertEqual(result, YnabAccount(id="a1", name="Checking", cleared_balance=1234567))
        mock_get.assert_called_once_with(
            "https://api.ynab.com/v1/plans/budget-id/accounts/a1",
            headers={"Authorization": "Bearer token"},
        )

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_raises_on_http_error(self, mock_get):
        mock = MagicMock()
        mock.status_code = 404
        mock.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = mock

        with self.assertRaises(requests.HTTPError):
            get_account("token", "budget-id", "a1")

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_raises_ynab_api_error_on_429(self, mock_get):
        mock = MagicMock()
        mock.status_code = 429
        mock.headers = {"Retry-After": "10"}
        mock_get.return_value = mock

        with self.assertRaises(YnabApiError) as ctx:
            get_account("token", "budget-id", "a1")

        self.assertIn("10", str(ctx.exception))

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_raises_ynab_api_error_on_malformed_body(self, mock_get):
        mock = MagicMock()
        mock.status_code = 200
        mock.raise_for_status.return_value = None
        mock.json.return_value = {"unexpected": "shape"}
        mock_get.return_value = mock

        with self.assertRaises(YnabApiError):
            get_account("token", "budget-id", "a1")
