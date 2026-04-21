import unittest
from datetime import date
from hashlib import sha256

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.ynab_api.transaction_uploader import to_adjustment_payload, to_api_payload, to_api_payloads

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

    def test_cleared_status_reconciled(self):
        txn = _TXN._replace(status=TransactionStatus.RECONCILED)
        self.assertEqual(to_api_payload(txn, "acc-123")["cleared"], "reconciled")

    def test_approved_false_by_default(self):
        self.assertIs(to_api_payload(_TXN, "acc-123")["approved"], False)

    def test_approved_true_when_requested(self):
        self.assertIs(to_api_payload(_TXN, "acc-123", approved=True)["approved"], True)

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


class TestToApiPayloadMemo(unittest.TestCase):
    def test_memo_absent_by_default(self):
        payload = to_api_payload(_TXN, "acc-123")
        self.assertNotIn("memo", payload)

    def test_memo_included_when_provided(self):
        payload = to_api_payload(_TXN, "acc-123", memo="Food / Cafe")
        self.assertEqual(payload["memo"], "Food / Cafe")

    def test_memo_absent_when_empty_string(self):
        payload = to_api_payload(_TXN, "acc-123", memo="")
        self.assertNotIn("memo", payload)


class TestToApiPayloads(unittest.TestCase):
    def test_returns_one_payload_per_transaction(self):
        txns = [_TXN, _TXN._replace(payee="Other")]
        result = to_api_payloads(txns, "acc-123")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["payee_name"], "Coffee Shop")
        self.assertEqual(result[1]["payee_name"], "Other")

    def test_empty_list_returns_empty(self):
        self.assertEqual(to_api_payloads([], "acc-123"), [])

    def test_memo_template_applied_to_all(self):
        txns = [_TXN, _TXN._replace(category="Other", sub_category="Sub2")]
        result = to_api_payloads(txns, "acc-123", memo_template="{category} / {sub_category}")
        self.assertEqual(result[0]["memo"], "Cat / Sub")
        self.assertEqual(result[1]["memo"], "Other / Sub2")

    def test_no_memo_when_template_absent(self):
        result = to_api_payloads([_TXN], "acc-123")
        self.assertNotIn("memo", result[0])


_ADJ_DATE = date(2026, 4, 21)
_ADJ_ACCOUNT = "acc-track-1"


class TestToAdjustmentPayload(unittest.TestCase):
    def _make(self, adjustment: int = 5000, new_balance: int = 45000) -> dict:
        return to_adjustment_payload(_ADJ_ACCOUNT, adjustment, new_balance, _ADJ_DATE)

    def test_required_fields_present(self):
        p = self._make()
        self.assertEqual(p["account_id"], _ADJ_ACCOUNT)
        self.assertEqual(p["date"], "2026-04-21")
        self.assertEqual(p["amount"], 5000)
        self.assertEqual(p["payee_name"], "Manual Balance Update")
        self.assertEqual(p["cleared"], "reconciled")
        self.assertIs(p["approved"], True)
        self.assertIn("memo", p)

    def test_import_id_max_36_chars(self):
        self.assertLessEqual(len(self._make()["import_id"]), 36)

    def test_import_id_is_deterministic(self):
        self.assertEqual(self._make()["import_id"], self._make()["import_id"])

    def test_import_id_differs_by_date(self):
        p1 = to_adjustment_payload(_ADJ_ACCOUNT, 5000, 45000, date(2026, 4, 21))
        p2 = to_adjustment_payload(_ADJ_ACCOUNT, 5000, 45000, date(2026, 4, 22))
        self.assertNotEqual(p1["import_id"], p2["import_id"])

    def test_import_id_differs_by_account(self):
        p1 = to_adjustment_payload("acc-1", 5000, 45000, _ADJ_DATE)
        p2 = to_adjustment_payload("acc-2", 5000, 45000, _ADJ_DATE)
        self.assertNotEqual(p1["import_id"], p2["import_id"])

    def test_import_id_differs_by_new_balance(self):
        p1 = to_adjustment_payload(_ADJ_ACCOUNT, 5000, 45000, _ADJ_DATE)
        p2 = to_adjustment_payload(_ADJ_ACCOUNT, 5000, 46000, _ADJ_DATE)
        self.assertNotEqual(p1["import_id"], p2["import_id"])

    def test_import_id_matches_expected_hash(self):
        expected = sha256(
            f"adj|2026-04-21|{_ADJ_ACCOUNT}|45000".encode()
        ).hexdigest()[:36]
        self.assertEqual(self._make(new_balance=45000)["import_id"], expected)
