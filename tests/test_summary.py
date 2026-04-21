"""Tests for the per-account upload summary report."""

import unittest

from ynab.summary import AccountSummary, print_summary


def _summary(**kwargs) -> AccountSummary:
    defaults = dict(
        account_name="Checking",
        read=10,
        pending=1,
        deduped=2,
        uploaded=7,
        balance_ok=True,
        balance_diff=0.0,
        bank_balance=1000.0,
    )
    defaults.update(kwargs)
    return AccountSummary(**defaults)


class TestPrintSummary(unittest.TestCase):
    def test_empty_list_produces_no_output(self):
        with self.assertNoLogs("ynab.summary", level="INFO"):
            print_summary([])

    def test_header_contains_column_names(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary()])
        joined = "\n".join(cm.output)
        self.assertIn("Account", joined)
        self.assertIn("Read", joined)
        self.assertIn("Pending", joined)
        self.assertIn("Deduped", joined)
        self.assertIn("Uploaded", joined)
        self.assertIn("Balance check", joined)

    def test_account_name_appears_in_row(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(account_name="Visa")])
        self.assertTrue(any("Visa" in line for line in cm.output))

    def test_counts_appear_in_row(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(read=12, pending=1, deduped=3, uploaded=8)])
        data_lines = [entry for entry in cm.output if "12" in entry]
        self.assertTrue(data_lines, "Expected a line containing count 12")
        line = data_lines[0]
        self.assertIn("12", line)
        self.assertIn("1", line)
        self.assertIn("3", line)
        self.assertIn("8", line)

    def test_balance_ok_shows_checkmark_and_balance(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(balance_ok=True, bank_balance=8234.50, balance_diff=0.0)])
        self.assertTrue(any("✓" in line and "8,234.50" in line for line in cm.output))

    def test_balance_not_ok_shows_cross_and_diff(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(balance_ok=False, bank_balance=8234.50, balance_diff=-2.30)])
        self.assertTrue(any("✗" in line and "diff" in line and "-2.30" in line for line in cm.output))

    def test_balance_not_reconciled_shows_dash(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(balance_ok=None, bank_balance=None, balance_diff=None)])
        # The last column should contain "—"
        data_lines = [entry for entry in cm.output if _summary().account_name in entry]
        self.assertTrue(any("—" in line for line in data_lines))

    def test_upload_disabled_shows_dash(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(uploaded=None)])
        data_lines = [entry for entry in cm.output if _summary().account_name in entry]
        self.assertTrue(any("—" in line for line in data_lines))

    def test_multiple_accounts_all_appear(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([
                _summary(account_name="Checking"),
                _summary(account_name="Visa"),
            ])
        joined = "\n".join(cm.output)
        self.assertIn("Checking", joined)
        self.assertIn("Visa", joined)

    def test_separator_line_length_matches_header(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(account_name="Savings")])
        # Filter out the log level prefix to get the raw message
        raw_lines = [entry.split("INFO:ynab.summary:", 1)[-1] for entry in cm.output]
        non_empty = [entry for entry in raw_lines if entry.strip()]
        # header is first non-empty, separator is second
        header = non_empty[0]
        separator = non_empty[1]
        self.assertEqual(len(header), len(separator))

    def test_long_account_name_widens_column(self):
        long_name = "Very Long Account Name Here"
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(account_name=long_name)])
        self.assertTrue(any(long_name in line for line in cm.output))

    def test_positive_balance_diff_shown_with_plus(self):
        with self.assertLogs("ynab.summary", level="INFO") as cm:
            print_summary([_summary(balance_ok=False, balance_diff=5.50, bank_balance=100.0)])
        self.assertTrue(any("+5.50" in line for line in cm.output))
