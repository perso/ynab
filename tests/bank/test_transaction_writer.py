import os
import tempfile
import unittest
from datetime import date

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.bank.transaction_writer import TransactionWriter


class TestTransactionReader(unittest.TestCase):
    def setUp(self) -> None:
        self.expected_csv_lines = [
            'Date,Payee,Memo,Amount\n',
            '2023-04-20,Zettle_*TMI BARBER,,-55.0\n',
            '2023-04-20,K-Citymarket Kerava,,-13.85\n',
            '2023-04-19,Varaus,,-7.7\n',
            '2023-03-20,If Vakuutus,,-9.94\n',
        ]
        self.transactions = [
            BankTransaction(date(2023, 4, 20), 'Vaatteet, terveys ja hyvinvointi', 'Kampaamo- ja parturipalvelut',
                            'Zettle_*TMI BARBER', -55.0, 8588.83, TransactionStatus.CLEARED),
            BankTransaction(date(2023, 4, 20), 'Ruoka- ja päivittäisostokset', 'Ruokakaupat ja marketit',
                            'K-Citymarket Kerava', -13.85, 8643.83, TransactionStatus.CLEARED),
            BankTransaction(date(2023, 4, 19), '', '', 'Varaus', -7.7, None, TransactionStatus.PENDING),
            BankTransaction(date(2023, 3, 20), 'Henkilövakuutukset', 'Muut menot', 'If Vakuutus', -9.94, 11956.07,
                            TransactionStatus.RECONCILED)
        ]

    def test_write_transactions(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name

        TransactionWriter(filename).write_transactions(self.transactions)

        with open(filename, 'r') as f:
            lines = f.readlines()
            self.assertEqual(self.expected_csv_lines, lines)

        os.remove(filename)
