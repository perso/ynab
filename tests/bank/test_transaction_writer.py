import os
import tempfile
import unittest
from datetime import date

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.bank.transaction_writer import format_memo, write_transactions

_BARBER = BankTransaction(
    date(2023, 4, 20), 'Vaatteet, terveys ja hyvinvointi', 'Kampaamo- ja parturipalvelut',
    'Zettle_*TMI BARBER', -55.0, 8588.83, TransactionStatus.CLEARED,
)
_GROCERY = BankTransaction(
    date(2023, 4, 20), 'Ruoka- ja päivittäisostokset', 'Ruokakaupat ja marketit',
    'K-Citymarket Kerava', -13.85, 8643.83, TransactionStatus.CLEARED,
)


class TestFormatMemo(unittest.TestCase):
    def test_returns_empty_when_no_template(self):
        self.assertEqual(format_memo(_BARBER, None), "")

    def test_returns_empty_when_empty_template(self):
        self.assertEqual(format_memo(_BARBER, ""), "")

    def test_category_placeholder(self):
        result = format_memo(_BARBER, "{category}")
        self.assertEqual(result, "Vaatteet, terveys ja hyvinvointi")

    def test_sub_category_placeholder(self):
        result = format_memo(_BARBER, "{sub_category}")
        self.assertEqual(result, "Kampaamo- ja parturipalvelut")

    def test_combined_template(self):
        result = format_memo(_BARBER, "{category} / {sub_category}")
        self.assertEqual(result, "Vaatteet, terveys ja hyvinvointi / Kampaamo- ja parturipalvelut")

    def test_empty_category_fields(self):
        txn = _BARBER._replace(category="", sub_category="")
        result = format_memo(txn, "{category} / {sub_category}")
        self.assertEqual(result, " / ")


class TestTransactionWriter(unittest.TestCase):
    def setUp(self) -> None:
        self.expected_csv_lines = [
            'Date,Payee,Memo,Amount\n',
            '2023-04-20,Zettle_*TMI BARBER,,-55.0\n',
            '2023-04-20,K-Citymarket Kerava,,-13.85\n',
            '2023-04-19,Varaus,,-7.7\n',
            '2023-03-20,If Vakuutus,,-9.94\n',
        ]
        self.transactions = [
            _BARBER,
            _GROCERY,
            BankTransaction(date(2023, 4, 19), '', '', 'Varaus', -7.7, None, TransactionStatus.PENDING),
            BankTransaction(date(2023, 3, 20), 'Henkilövakuutukset', 'Muut menot', 'If Vakuutus', -9.94, 11956.07,
                            TransactionStatus.RECONCILED)
        ]

    def test_write_transactions(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name

        write_transactions(filename, self.transactions)

        with open(filename, 'r') as f:
            lines = f.readlines()
            self.assertEqual(self.expected_csv_lines, lines)

        os.remove(filename)

    def test_write_transactions_with_memo_template(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name

        write_transactions(filename, [_BARBER, _GROCERY], memo_template="{category} / {sub_category}")

        with open(filename, 'r') as f:
            lines = f.readlines()

        self.assertEqual(lines[0], 'Date,Payee,Memo,Amount\n')
        self.assertIn('Vaatteet, terveys ja hyvinvointi / Kampaamo- ja parturipalvelut', lines[1])
        self.assertIn('Ruoka- ja päivittäisostokset / Ruokakaupat ja marketit', lines[2])
        os.remove(filename)

    def test_second_write_overwrites_first(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name

        tx1 = BankTransaction(date(2023, 4, 20), '', '', 'Shop A', -10.0, None, TransactionStatus.CLEARED)
        tx2 = BankTransaction(date(2023, 4, 21), '', '', 'Shop B', -5.0, None, TransactionStatus.CLEARED)
        write_transactions(filename, [tx1])
        write_transactions(filename, [tx2])

        with open(filename, 'r') as f:
            lines = f.readlines()
        self.assertEqual(lines[0], 'Date,Payee,Memo,Amount\n')
        self.assertEqual(len(lines), 2)
        self.assertIn('Shop B', lines[1])
        self.assertNotIn('Shop A', ''.join(lines))

        os.remove(filename)

    def test_write_transactions_empty_list(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            filename = f.name

        write_transactions(filename, [])

        with open(filename, 'r') as f:
            lines = f.readlines()
        self.assertEqual(lines, ['Date,Payee,Memo,Amount\n'])

        os.remove(filename)
