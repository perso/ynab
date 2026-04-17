import os
import tempfile
import unittest
from datetime import date

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.bank.transaction_reader import TransactionReader


class TestTransactionReader(unittest.TestCase):
    def setUp(self) -> None:
        self.input_csv = "\n".join([
            '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"',
            '"20.04.2023";"Vaatteet, terveys ja hyvinvointi";"Kampaamo- ja parturipalvelut";"Zettle_*TMI BARBER";"-55,00";"8 588,83";"Toteutunut";"Ei"',
            '"20.04.2023";"Ruoka- ja päivittäisostokset   ";"Ruokakaupat ja marketit      ";"K-Citymarket Kerava";"-13,85";"8 643,83";"Toteutunut";"Ei"',
            '"19.04.2023";"      ";"    ";"Varaus";"-7,70";"";"Odottaa";"Ei"',
            '"20.03.2023";"Henkilövakuutukset";"Muut menot";"If Vakuutus";"-9,94";"11 956,07";"Toteutunut";"Kyllä"'
        ])
        self.expected_transactions = [
            BankTransaction(date(2023, 4, 20), 'Vaatteet, terveys ja hyvinvointi', 'Kampaamo- ja parturipalvelut',
                            'Zettle_*TMI BARBER', -55.0, 8588.83, TransactionStatus.CLEARED),
            BankTransaction(date(2023, 4, 20), 'Ruoka- ja päivittäisostokset', 'Ruokakaupat ja marketit',
                            'K-Citymarket Kerava', -13.85, 8643.83, TransactionStatus.CLEARED),
            BankTransaction(date(2023, 4, 19), '', '', 'Varaus', -7.7, None, TransactionStatus.PENDING),
            BankTransaction(date(2023, 3, 20), 'Henkilövakuutukset', 'Muut menot', 'If Vakuutus', -9.94, 11956.07,
                            TransactionStatus.RECONCILED)
        ]

    def test_read_transactions(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(self.input_csv.encode('iso-8859-1'))
            filename = f.name

        transactions = TransactionReader(f.name).read_transactions()
        self.assertEqual(self.expected_transactions, transactions)

        os.remove(filename)

    def test_read_transactions_invalid_row(self):
        bad_csv = "\n".join([
            '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"',
            '"NOT-A-DATE";"Cat";"Sub";"Payee";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(bad_csv.encode('iso-8859-1'))
            filename = f.name

        with self.assertRaises(ValueError) as ctx:
            TransactionReader(filename).read_transactions()
        self.assertIn("row 2", str(ctx.exception))

        os.remove(filename)

    def test_resolve_status_reconciled(self):
        self.assertEqual(
            TransactionReader._resolve_status("Toteutunut", "Kyllä"),
            TransactionStatus.RECONCILED,
        )

    def test_resolve_status_cleared(self):
        self.assertEqual(
            TransactionReader._resolve_status("Toteutunut", "Ei"),
            TransactionStatus.CLEARED,
        )

    def test_resolve_status_pending(self):
        self.assertEqual(
            TransactionReader._resolve_status("Odottaa", "Ei"),
            TransactionStatus.PENDING,
        )

    def test_resolve_status_unknown_is_pending(self):
        self.assertEqual(
            TransactionReader._resolve_status("", ""),
            TransactionStatus.PENDING,
        )

    def test_read_transactions_no_header(self):
        csv_without_header = "\n".join([
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"8 588,83";"Toteutunut";"Ei"',
        ])
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(csv_without_header.encode('iso-8859-1'))
            filename = f.name

        transactions = TransactionReader(filename, header=False).read_transactions()
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].payee, 'Shop A')
        self.assertEqual(transactions[0].status, TransactionStatus.CLEARED)

        os.remove(filename)
