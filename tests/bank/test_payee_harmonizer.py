import unittest
from datetime import date

from ynab.bank.payee_harmonizer import harmonize_payee, harmonize_payees
from ynab.bank.transaction import BankTransaction, TransactionStatus


def _txn(payee: str) -> BankTransaction:
    return BankTransaction(date(2024, 1, 1), "", "", payee, -10.0, None, TransactionStatus.CLEARED)


class TestHarmonizePayee(unittest.TestCase):
    def test_exact_match(self):
        self.assertEqual("Barber", harmonize_payee("TMI BARBER", {"TMI BARBER": "Barber"}))

    def test_suffix_wildcard(self):
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        self.assertEqual("K-Citymarket", harmonize_payee("K-CITYMARKET KERAVA 12345", rules))

    def test_escaped_special_char(self):
        rules = {r"ZETTLE\*TMI BARBER.*": "Barber"}
        self.assertEqual("Barber", harmonize_payee("ZETTLE*TMI BARBER HELSINKI", rules))

    def test_no_match_returns_original(self):
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        self.assertEqual("S-MARKET VANTAA", harmonize_payee("S-MARKET VANTAA", rules))

    def test_first_match_wins(self):
        rules = {"IF.*": "If", "IF VAKUUTUS.*": "If Vakuutus"}
        self.assertEqual("If", harmonize_payee("IF VAKUUTUS OYJ", rules))

    def test_empty_rules_returns_original(self):
        self.assertEqual("SOME PAYEE", harmonize_payee("SOME PAYEE", {}))

    def test_partial_match_does_not_apply(self):
        # re.fullmatch requires the whole string to match
        rules = {"K-CITYMARKET": "K-Citymarket"}
        self.assertEqual("K-CITYMARKET KERAVA", harmonize_payee("K-CITYMARKET KERAVA", rules))


class TestHarmonizePayees(unittest.TestCase):
    def test_harmonized_transaction_has_clean_payee_and_original(self):
        txn = _txn("K-CITYMARKET KERAVA 12345")
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        result = harmonize_payees([txn], rules)
        self.assertEqual("K-Citymarket", result[0].payee)
        self.assertEqual("K-CITYMARKET KERAVA 12345", result[0].original_payee)

    def test_unmatched_transaction_is_unchanged(self):
        txn = _txn("S-MARKET VANTAA")
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        result = harmonize_payees([txn], rules)
        self.assertEqual(txn, result[0])
        self.assertIsNone(result[0].original_payee)

    def test_empty_rules_returns_same_list(self):
        txns = [_txn("PAYEE A"), _txn("PAYEE B")]
        result = harmonize_payees(txns, {})
        self.assertIs(txns, result)

    def test_mixed_list(self):
        txns = [_txn("K-CITYMARKET KERAVA"), _txn("S-MARKET VANTAA")]
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        result = harmonize_payees(txns, rules)
        self.assertEqual("K-Citymarket", result[0].payee)
        self.assertEqual("K-CITYMARKET KERAVA", result[0].original_payee)
        self.assertEqual("S-MARKET VANTAA", result[1].payee)
        self.assertIsNone(result[1].original_payee)

    def test_all_other_fields_preserved(self):
        txn = _txn("K-CITYMARKET KERAVA")
        rules = {"K-CITYMARKET.*": "K-Citymarket"}
        result = harmonize_payees([txn], rules)[0]
        self.assertEqual(txn.date, result.date)
        self.assertEqual(txn.amount, result.amount)
        self.assertEqual(txn.status, result.status)
