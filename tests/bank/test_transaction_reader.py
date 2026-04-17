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
