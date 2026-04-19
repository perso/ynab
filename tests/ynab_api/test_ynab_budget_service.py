import unittest
from datetime import date
from unittest.mock import patch

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.budget_service import BudgetService
from ynab.ynab_api.ynab_api_client import TransactionsResponse
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

_CLEARED = TransactionStatus.CLEARED
_TXN = BankTransaction(date(2023, 4, 20), "Cat", "Sub", "Shop", -5.50, None, _CLEARED)


class TestYnabBudgetServiceProtocol(unittest.TestCase):
    def test_satisfies_budget_service_protocol(self):
        service = YnabBudgetService("token")
        self.assertIsInstance(service, BudgetService)

    @patch("ynab.ynab_api.ynab_budget_service.ynab_api_client.get_transactions")
    def test_delegates_get_to_api_client(self, mock_get):
        mock_get.return_value = TransactionsResponse(transactions=[], server_knowledge=5)
        service = YnabBudgetService("tok")
        result = service.get_transactions("b1", date(2023, 1, 1))
        mock_get.assert_called_once_with("tok", "b1", date(2023, 1, 1))
        self.assertEqual(result.server_knowledge, 5)

    @patch("ynab.ynab_api.ynab_budget_service.ynab_api_client.create_transactions")
    def test_delegates_create_to_api_client(self, mock_create):
        mock_create.return_value = 1
        service = YnabBudgetService("tok")
        result = service.create_transactions("b1", "acc-1", [_TXN])
        self.assertEqual(result, 1)
        # Verify the call was made with correct token and budget_id; payload is a list of dicts
        args = mock_create.call_args[0]
        self.assertEqual(args[0], "tok")
        self.assertEqual(args[1], "b1")
        self.assertIsInstance(args[2], list)
        self.assertEqual(len(args[2]), 1)
        self.assertEqual(args[2][0]["payee_name"], "Shop")
