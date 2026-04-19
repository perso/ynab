import unittest
from datetime import date
from hashlib import sha256

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.ynab_api.transaction_uploader import to_api_payload, to_api_payloads

_CLEARED = TransactionStatus.CLEARED

_TXN = BankTransaction(
    date=date(2023, 4, 20),
    category="Cat",
    sub_category="Sub",
    payee="Coffee Shop",
    amount=-5.50,
    balance=100.00,
    status=_CLEARED,
)

_TXN_NO_BALANCE = _TXN._replace(balance=None)


class TestToApiPayload(unittest.TestCase):
    def test_fields_are_correct(self):
        payload = to_api_payload(_TXN, "acc-123")
        self.assertEqual(payload["account_id"], "acc-123")
        self.assertEqual(payload["date"], "2023-04-20")
        self.assertEqual(payload["amount"], -5500)
        self.assertEqual(payload["payee_name"], "Coffee Shop")
        self.assertEqual(payload["cleared"], "cleared")
        self.assertIs(payload["approved"], False)

    def test_import_id_is_deterministic(self):
        p1 = to_api_payload(_TXN, "acc-123")
        p2 = to_api_payload(_TXN, "acc-123")
        self.assertEqual(p1["import_id"], p2["import_id"])

    def test_import_id_max_36_chars(self):
        payload = to_api_payload(_TXN, "acc-123")
        self.assertLessEqual(len(payload["import_id"]), 36)

    def test_import_id_differs_by_payee(self):
        other = _TXN._replace(payee="Different Payee")
        self.assertNotEqual(
            to_api_payload(_TXN, "acc-123")["import_id"],
            to_api_payload(other, "acc-123")["import_id"],
        )

    def test_import_id_differs_by_amount(self):
        other = _TXN._replace(amount=-10.00)
        self.assertNotEqual(
            to_api_payload(_TXN, "acc-123")["import_id"],
            to_api_payload(other, "acc-123")["import_id"],
        )

    def test_import_id_differs_by_date(self):
        other = _TXN._replace(date=date(2023, 4, 21))
        self.assertNotEqual(
            to_api_payload(_TXN, "acc-123")["import_id"],
            to_api_payload(other, "acc-123")["import_id"],
        )

    def test_import_id_differs_by_balance(self):
        other = _TXN._replace(balance=200.00)
        self.assertNotEqual(
            to_api_payload(_TXN, "acc-123")["import_id"],
            to_api_payload(other, "acc-123")["import_id"],
        )

    def test_import_id_matches_expected_hash_with_balance(self):
        milliunits = -5500
        balance_milliunits = 100000
        expected = sha256(
            f"2023-04-20|{milliunits}|Coffee Shop|{balance_milliunits}".encode()
        ).hexdigest()[:36]
        self.assertEqual(to_api_payload(_TXN, "acc-123")["import_id"], expected)

    def test_import_id_matches_expected_hash_without_balance(self):
        milliunits = -5500
        expected = sha256(
            f"2023-04-20|{milliunits}|Coffee Shop".encode()
        ).hexdigest()[:36]
        self.assertEqual(to_api_payload(_TXN_NO_BALANCE, "acc-123")["import_id"], expected)


class TestToApiPayloads(unittest.TestCase):
    def test_returns_one_payload_per_transaction(self):
        txns = [_TXN, _TXN._replace(payee="Other")]
        result = to_api_payloads(txns, "acc-123")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["payee_name"], "Coffee Shop")
        self.assertEqual(result[1]["payee_name"], "Other")

    def test_empty_list_returns_empty(self):
        self.assertEqual(to_api_payloads([], "acc-123"), [])
