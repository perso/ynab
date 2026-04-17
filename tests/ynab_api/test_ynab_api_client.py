import unittest
from datetime import date
from unittest.mock import patch

from ynab.ynab_api.ynab_api_client import YnabTransaction, YnabApiClient


class TestYnabApiClient(unittest.TestCase):
    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions(self, mock_get):
        mock_response = {
            "data": {
                "transactions": [
                    {
                        "id": "1",
                        "date": "2023-04-01",
                        "amount": 1000,
                        "memo": "Test transaction",
                        "cleared": "cleared",
                        "approved": True,
                        "flag_color": "blue",
                        "account_id": "a1",
                        "payee_id": "p1",
                        "category_id": "c1",
                        "transfer_account_id": None,
                        "transfer_transaction_id": None,
                        "matched_transaction_id": None,
                        "import_id": "i1",
                        "import_payee_name": None,
                        "import_payee_name_original": None,
                        "debt_transaction_type": None,
                        "deleted": False,
                        "account_name": "Test account",
                        "payee_name": "Test payee",
                        "category_name": "Test category"
                    }
                ]
            }
        }
        mock_get.return_value.json.return_value = mock_response
        token = "test_token"
        budget_id = "test_budget_id"
        since_date = date(2023, 1, 1)
        transactions = YnabApiClient.get_transactions(token, budget_id, since_date)
        expected_transactions = [
            YnabTransaction(
                id="1",
                date="2023-04-01",
                amount=1000,
                memo="Test transaction",
                cleared="cleared",
                approved=True,
                flag_color="blue",
                account_id="a1",
                payee_id="p1",
                category_id="c1",
                transfer_account_id=None,
                transfer_transaction_id=None,
                matched_transaction_id=None,
                import_id="i1",
                import_payee_name=None,
                import_payee_name_original=None,
                debt_transaction_type=None,
                deleted=False,
                account_name="Test account",
                payee_name="Test payee",
                category_name="Test category"
            )
        ]
        self.assertEqual(transactions, expected_transactions)
        mock_get.assert_called_once_with(
            "https://api.youneedabudget.com/v1/budgets/test_budget_id/transactions?since_date=2023-01-01",
            headers={"Authorization": "Bearer test_token"}
        )

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_raises_on_http_error(self, mock_get):
        import requests
        mock_get.return_value.raise_for_status.side_effect = requests.HTTPError("404")
        with self.assertRaises(requests.HTTPError):
            YnabApiClient.get_transactions("token", "budget", date(2023, 1, 1))

    @patch("ynab.ynab_api.ynab_api_client.requests.get")
    def test_get_transactions_empty_list(self, mock_get):
        mock_get.return_value.json.return_value = {"data": {"transactions": []}}
        result = YnabApiClient.get_transactions("token", "budget", date(2023, 1, 1))
        self.assertEqual(result, [])
