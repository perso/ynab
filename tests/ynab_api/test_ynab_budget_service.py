import unittest
from datetime import date
from unittest.mock import patch

from ynab.budget_service import BudgetService
from ynab.ynab_api.ynab_api_client import TransactionsResponse
from ynab.ynab_api.ynab_budget_service import YnabBudgetService


class TestYnabBudgetServiceProtocol(unittest.TestCase):
    def test_satisfies_budget_service_protocol(self):
        service = YnabBudgetService("token")
        self.assertIsInstance(service, BudgetService)

    @patch("ynab.ynab_api.ynab_budget_service.YnabApiClient.get_transactions")
    def test_delegates_to_api_client(self, mock_get):
        mock_get.return_value = TransactionsResponse(transactions=[], server_knowledge=5)
        service = YnabBudgetService("tok")
        result = service.get_transactions("b1", date(2023, 1, 1))
        mock_get.assert_called_once_with("tok", "b1", date(2023, 1, 1))
        self.assertEqual(result.server_knowledge, 5)
