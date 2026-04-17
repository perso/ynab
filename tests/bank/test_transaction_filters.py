import unittest
from datetime import date

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.bank.transaction_filters import filter_unchecked_transactions


class TestTransactionFilters(unittest.TestCase):
    def setUp(self) -> None:
        self.transactions = [
            BankTransaction(date(2023, 4, 20), '', '', '', 1.0, None, TransactionStatus.CLEARED),
            BankTransaction(date(2023, 4, 19), '', '', '', 2.0, None, TransactionStatus.PENDING),
            BankTransaction(date(2023, 3, 20), '', '', '', 3.0, None, TransactionStatus.RECONCILED)
        ]

    def test_filter_unchecked_transactions(self):
        unchecked = filter_unchecked_transactions(self.transactions)
        expected = [BankTransaction(date(2023, 4, 20), '', '', '', 1.0, None, TransactionStatus.CLEARED)]
        self.assertEqual(expected, unchecked)
