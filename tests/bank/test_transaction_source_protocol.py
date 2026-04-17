import unittest

from ynab.bank.transaction_source import BankTransactionSource
from ynab.bank.transaction_reader import TransactionReader


class TestBankTransactionSourceProtocol(unittest.TestCase):
    def test_transaction_reader_satisfies_protocol(self):
        # Use a non-existent path — we only check structural compliance, not runtime behaviour.
        reader = TransactionReader("/dev/null")
        self.assertIsInstance(reader, BankTransactionSource)
