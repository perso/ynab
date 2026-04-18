import unittest
from datetime import date

from ynab.bank.duplicate_filter import DEFAULT_DATE_TOLERANCE_DAYS, filter_already_in_ynab, to_milliunits
from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.ynab_api.ynab_api_client import YnabTransaction

_CLEARED = TransactionStatus.CLEARED


def _bt(txn_date: date, amount: float, payee: str = "", status: TransactionStatus = _CLEARED) -> BankTransaction:
    return BankTransaction(txn_date, "", "", payee, amount, None, status)


def _yt(
    txn_date: str,
    amount: int,
    account_id: str = "a1",
    cleared: str = "cleared",
    deleted: bool = False,
    ynab_id: str = "y1",
) -> YnabTransaction:
    return YnabTransaction(
        id=ynab_id,
        date=txn_date,
        amount=amount,
        memo=None,
        cleared=cleared,
        approved=True,
        flag_color=None,
        account_id=account_id,
        payee_id=None,
        category_id=None,
        transfer_account_id=None,
        transfer_transaction_id=None,
        matched_transaction_id=None,
        import_id=None,
        import_payee_name=None,
        import_payee_name_original=None,
        debt_transaction_type=None,
        deleted=deleted,
        account_name="",
        payee_name="",
        category_name="",
    )


class TestToMilliunits(unittest.TestCase):
    def test_negative_amount(self):
        self.assertEqual(-55000, to_milliunits(-55.0))

    def test_fractional_negative(self):
        self.assertEqual(-100, to_milliunits(-0.1))

    def test_positive_fractional(self):
        self.assertEqual(10005, to_milliunits(10.005))

    def test_zero(self):
        self.assertEqual(0, to_milliunits(0.0))

    def test_positive(self):
        self.assertEqual(1000, to_milliunits(1.0))


class TestFilterAlreadyInYnab(unittest.TestCase):
    def test_exact_date_and_amount_is_removed(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_bank_date_within_tolerance_is_removed(self):
        bank = [_bt(date(2023, 4, 22), -55.0)]  # 2 days after YNAB
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_bank_date_beyond_tolerance_is_kept(self):
        bank = [_bt(date(2023, 4, 24), -55.0)]  # 4 days after YNAB (> 3)
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(bank, result)

    def test_at_tolerance_boundary_is_removed(self):
        bank = [_bt(date(2023, 4, 23), -55.0)]  # exactly 3 days
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_custom_tolerance_zero_forces_exact_date(self):
        bank = [_bt(date(2023, 4, 21), -55.0)]  # 1 day off
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1", date_tolerance_days=0)
        self.assertEqual(bank, result)

    def test_one_to_one_consumption(self):
        """Two bank transactions with the same amount/date: only one YNAB match removes one."""
        bank = [
            _bt(date(2023, 4, 20), -55.0, "Shop A"),
            _bt(date(2023, 4, 20), -55.0, "Shop B"),
        ]
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(1, len(result))

    def test_two_ynab_two_bank_each_paired_to_nearest(self):
        """YNAB on D and D+1; bank on D and D+2 — D pairs with D, D+2 pairs with D+1."""
        bank = [
            _bt(date(2023, 4, 20), -10.0, "a"),
            _bt(date(2023, 4, 22), -10.0, "b"),
        ]
        ynab = [
            _yt("2023-04-20", -10000, ynab_id="y1"),
            _yt("2023-04-21", -10000, ynab_id="y2"),
        ]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_different_account_id_ignored(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -55000, account_id="other")]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(bank, result)

    def test_deleted_ynab_transaction_ignored(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -55000, deleted=True)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(bank, result)

    def test_uncleared_ynab_transaction_ignored(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -55000, cleared="uncleared")]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(bank, result)

    def test_reconciled_ynab_transaction_counts(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -55000, cleared="reconciled")]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_empty_ynab_returns_all_bank(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        result = filter_already_in_ynab(bank, [], "a1")
        self.assertEqual(bank, result)

    def test_empty_bank_returns_empty(self):
        ynab = [_yt("2023-04-20", -55000)]
        result = filter_already_in_ynab([], ynab, "a1")
        self.assertEqual([], result)

    def test_positive_inflow_matched(self):
        bank = [_bt(date(2023, 4, 20), 100.0)]
        ynab = [_yt("2023-04-20", 100000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual([], result)

    def test_amount_mismatch_is_kept(self):
        bank = [_bt(date(2023, 4, 20), -55.0)]
        ynab = [_yt("2023-04-20", -54000)]
        result = filter_already_in_ynab(bank, ynab, "a1")
        self.assertEqual(bank, result)

    def test_default_tolerance_is_three(self):
        self.assertEqual(3, DEFAULT_DATE_TOLERANCE_DAYS)
