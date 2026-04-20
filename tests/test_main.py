import os
import sys
import unittest
from datetime import date
from tempfile import mkdtemp
from typing import List
from unittest.mock import patch

from ynab.bank.transaction import BankTransaction
from ynab.converter import convert_bank_transactions
from ynab.utilities.config_util import AccountConfig
from ynab.utilities.fs_util import FilePathMapping
from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabAccount, YnabTransaction

_ACCOUNT_CONFIG_SIMPLE = {"FI111": AccountConfig("Budget", None, None)}
_ACCOUNT_CONFIG_DEDUP = {"FI111": AccountConfig("Budget", "b1", "a1")}

_EMPTY_RESPONSE = TransactionsResponse(transactions=[], server_knowledge=0)


def _write_input_csv(path: str, rows: list[str]) -> None:
    header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
    content = "\n".join([header] + rows)
    with open(path, "wb") as f:
        f.write(content.encode("iso-8859-1"))


def _make_ynab_transaction(
    txn_date: str,
    amount: int,
    account_id: str = "a1",
    cleared: str = "cleared",
    ynab_id: str = "y1",
) -> YnabTransaction:
    return YnabTransaction(
        id=ynab_id,
        date=txn_date,
        amount=amount,
        cleared=cleared,
        account_id=account_id,
        deleted=False,
    )


_DEFAULT_YNAB_ACCOUNT = YnabAccount(id="a1", name="Checking", cleared_balance=100000)


class _FakeBudgetService:
    """Test double for BudgetService — records calls and returns preset responses."""

    def __init__(
        self,
        response: TransactionsResponse = _EMPTY_RESPONSE,
        created_count: int = 0,
        account: YnabAccount = _DEFAULT_YNAB_ACCOUNT,
    ) -> None:
        self.response = response
        self.created_count = created_count
        self.account = account
        self.calls: list[tuple] = []
        self.create_calls: list[tuple] = []
        self.account_calls: list[tuple] = []

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
    ) -> TransactionsResponse:
        self.calls.append((budget_id, since_date))
        return self.response

    def create_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: List[BankTransaction],
        approved: bool = False,
    ) -> int:
        self.create_calls.append((budget_id, account_id, transactions, approved))
        return self.created_count

    def get_account(self, budget_id: str, account_id: str) -> YnabAccount:
        self.account_calls.append((budget_id, account_id))
        return self.account


class TestConvertBankTransactions(unittest.TestCase):
    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_filters_pending_transactions(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"8 588,83";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"";"Odottaa";"Ei"',
        ])

        with patch("ynab.converter.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions(dedup_enabled=False, upload_enabled=False)

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines[0], "Date,Payee,Memo,Amount\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("Shop A", lines[1])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_deduplicates_and_sorts_by_date(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"200,00";"Toteutunut";"Ei"',
        ])

        with patch("ynab.converter.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions(dedup_enabled=False, upload_enabled=False)

        with open(output_file) as f:
            lines = f.readlines()

        # header + 2 unique entries (duplicate removed), sorted by date ascending
        self.assertEqual(len(lines), 3)
        self.assertIn("Shop B", lines[1])
        self.assertIn("Shop A", lines[2])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_empty_input_writes_only_header(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [])

        with patch("ynab.converter.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions(dedup_enabled=False, upload_enabled=False)

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines, ["Date,Payee,Memo,Amount\n"])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_no_file_paths_does_nothing(self, _mock_cfg):
        with patch("ynab.converter.form_file_paths", return_value=[]):
            convert_bank_transactions(dedup_enabled=False, upload_enabled=False)


class TestConvertBankTransactionsWithDedup(unittest.TestCase):
    """Integration tests for the dedup path using _FakeBudgetService injection."""

    def _run_with_fake_service(
        self,
        input_file: str,
        output_file: str,
        service: _FakeBudgetService,
    ) -> None:
        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
            )

    def test_removes_bank_rows_already_in_ynab(self):
        service = _FakeBudgetService(TransactionsResponse(
            transactions=[_make_ynab_transaction("2023-04-20", -55000, account_id="a1")],
            server_knowledge=1,
        ))

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"200,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service)

        with open(output_file) as f:
            lines = f.readlines()

        # Shop A matched in YNAB → removed; Shop B stays
        self.assertEqual(len(lines), 2)
        self.assertIn("Shop B", lines[1])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_per_account_date_tolerance_overrides_default(self):
        account_cfg_custom = {"FI111": AccountConfig("Budget", "b1", "a1", date_tolerance_days=7)}
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=account_cfg_custom),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
            )

        _budget_id, since_date = service.calls[0]
        # min date is 2023-04-20, minus 7-day custom tolerance → 2023-04-13
        self.assertEqual(since_date, date(2023, 4, 13))

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_since_date_derived_from_min_bank_date_minus_tolerance(self):
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"22.04.2023";"Cat";"Sub";"Shop B";"-7,70";"200,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service)

        budget_id, since_date = service.calls[0]
        self.assertEqual(budget_id, "b1")
        # min date is 2023-04-20, minus 3-day tolerance → 2023-04-17
        self.assertEqual(since_date, date(2023, 4, 17))

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_credentials_file", return_value="token")
    def test_api_not_called_when_all_transactions_filtered_as_pending(self, _mock_creds):
        """No budget service call when the CLEARED filter removes all transactions."""
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"";"Odottaa";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
            )

        self.assertEqual(service.calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    @patch("ynab.converter.read_credentials_file")
    def test_credentials_not_loaded_when_dedup_disabled(self, mock_creds, _mock_cfg):
        with patch("ynab.converter.form_file_paths", return_value=[]):
            convert_bank_transactions(dedup_enabled=False, upload_enabled=False)
        mock_creds.assert_not_called()

    @patch("ynab.converter.read_credentials_file", return_value="token")
    def test_raises_when_dedup_enabled_but_account_ids_missing(self, _mock_creds):
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header, '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"'])
        with open(input_file, "wb") as f:
            f.write(content.encode("iso-8859-1"))

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            self.assertRaises(ValueError) as ctx,
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
            )

        self.assertIn("FI111", str(ctx.exception))
        self.assertIn("--dedup", str(ctx.exception))

    def test_uses_global_budget_id_when_account_budget_id_absent(self):
        """budget_id absent from accounts.toml falls back to global_budget_id."""
        account_cfg_no_budget_id = {"FI111": AccountConfig("Budget", None, "a1")}
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=account_cfg_no_budget_id),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
                global_budget_id="env-budget-id",
            )

        self.assertEqual(len(service.calls), 1)
        budget_id_used, _ = service.calls[0]
        self.assertEqual(budget_id_used, "env-budget-id")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestConvertBankTransactionsWithUpload(unittest.TestCase):
    """Integration tests for the YNAB_UPLOAD_ENABLED path."""

    def _run_with_fake_service(
        self,
        input_file: str,
        output_file: str,
        service: _FakeBudgetService,
        account_config: dict,
    ) -> None:
        with (
            patch("ynab.converter.read_accounts_config", return_value=account_config),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                upload_enabled=True,
            )

    def test_create_transactions_called_with_correct_args(self):
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, _ACCOUNT_CONFIG_DEDUP)

        self.assertEqual(len(service.create_calls), 1)
        budget_id, account_id, txns, _approved = service.create_calls[0]
        self.assertEqual(budget_id, "b1")
        self.assertEqual(account_id, "a1")
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].payee, "Shop A")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_upload_skipped_when_account_config_missing_ids(self):
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, _ACCOUNT_CONFIG_SIMPLE)

        # No create call made; CSV still written
        self.assertEqual(service.create_calls, [])
        with open(output_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_upload_not_called_when_no_transactions(self):
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        # All PENDING — filtered out before upload
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"";"Odottaa";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, _ACCOUNT_CONFIG_DEDUP)

        self.assertEqual(service.create_calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.converter.read_credentials_file")
    @patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_credentials_loaded_when_upload_enabled(self, _mock_cfg, mock_creds):
        mock_creds.return_value = "token"
        with patch("ynab.converter.form_file_paths", return_value=[]):
            convert_bank_transactions(upload_enabled=True)
        mock_creds.assert_called_once()

    def test_upload_uses_global_budget_id_when_account_budget_id_absent(self):
        account_cfg_no_budget_id = {"FI111": AccountConfig("Budget", None, "a1")}
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=account_cfg_no_budget_id),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                upload_enabled=True,
                global_budget_id="env-budget-id",
            )

        self.assertEqual(len(service.create_calls), 1)
        budget_id_used, _, _, _approved = service.create_calls[0]
        self.assertEqual(budget_id_used, "env-budget-id")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_approve_enabled_passed_to_create_transactions(self):
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                upload_enabled=True,
                approve_enabled=True,
            )

        _budget_id, _account_id, _txns, approved = service.create_calls[0]
        self.assertTrue(approved)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_approve_disabled_by_default(self):
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                upload_enabled=True,
            )

        _budget_id, _account_id, _txns, approved = service.create_calls[0]
        self.assertFalse(approved)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestConvertBankTransactionsWithDedupAndUpload(unittest.TestCase):
    """Verify that dedup and upload can both run in the same pass."""

    def test_dedup_and_upload_both_run(self):
        service = _FakeBudgetService(response=_EMPTY_RESPONSE, created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                dedup_enabled=True,
                upload_enabled=True,
            )

        # Dedup ran
        self.assertEqual(len(service.calls), 1)
        # Upload ran
        self.assertEqual(len(service.create_calls), 1)
        budget_id, account_id, txns, _approved = service.create_calls[0]
        self.assertEqual(budget_id, "b1")
        self.assertEqual(account_id, "a1")
        self.assertEqual(len(txns), 1)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestConvertBankTransactionsWithReconcile(unittest.TestCase):
    """Integration tests for the --reconcile path using _FakeBudgetService injection."""

    def _run_reconcile(
        self,
        input_file: str,
        output_file: str,
        service: _FakeBudgetService,
    ) -> None:
        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                reconcile_enabled=True,
            )

    def test_get_account_called_with_correct_args(self):
        service = _FakeBudgetService(account=YnabAccount("a1", "Checking", 100000))
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        self._run_reconcile(input_file, output_file, service)

        self.assertEqual(len(service.account_calls), 1)
        budget_id, account_id = service.account_calls[0]
        self.assertEqual(budget_id, "b1")
        self.assertEqual(account_id, "a1")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_reconcile_skipped_when_no_balance_in_csv(self):
        """All PENDING rows → balance is None → get_account not called."""
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"";"Odottaa";"Ei"',
        ])

        self._run_reconcile(input_file, output_file, service)

        self.assertEqual(service.account_calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_reconcile_skipped_when_account_config_missing(self):
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(
                budget_service_factory=lambda _token: service,
                reconcile_enabled=True,
            )

        self.assertEqual(service.account_calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_credentials_loaded_when_reconcile_enabled(self):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [])

        with (
            patch("ynab.converter.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE),
            patch("ynab.converter.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.converter.read_credentials_file", return_value="token") as mock_creds,
        ):
            convert_bank_transactions(reconcile_enabled=True)

        mock_creds.assert_called_once()

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_balance_from_csv_used_regardless_of_cleared_status(self):
        """Balance is taken from all transactions, not just CLEARED ones."""
        # Only RECONCILED row has a balance — should still be captured
        service = _FakeBudgetService(account=YnabAccount("a1", "Savings", 500000))
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"500,00";"Toteutunut";"Kyllä"',
        ])

        self._run_reconcile(input_file, output_file, service)

        # get_account was called despite the row being RECONCILED (filtered from import)
        self.assertEqual(len(service.account_calls), 1)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_balance_uses_most_recent_date_not_maximum_value(self):
        """Reconciliation must compare the latest transaction's balance, not the peak balance.

        With multiple transactions the running balance can go up and down.
        Using max() would pick the numerically highest balance (an old peak),
        producing a wrong diff.  The correct balance is the one attached to
        the transaction with the latest date.
        """
        # Older transaction has a higher balance (1 500 €); newer one is lower (800 €).
        # YNAB cleared balance is 800 €.  Diff must be 0, not 700.
        service = _FakeBudgetService(account=YnabAccount("a1", "Checking", 800000))
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        _write_input_csv(input_file, [
            '"01.01.2023";"Cat";"Sub";"Shop A";"-200,00";"1500,00";"Toteutunut";"Ei"',
            '"01.02.2023";"Cat";"Sub";"Shop B";"-700,00";"800,00";"Toteutunut";"Ei"',
        ])

        with self.assertLogs("ynab.converter", level="INFO") as cm:
            self._run_reconcile(input_file, output_file, service)

        log_text = "\n".join(cm.output)
        self.assertIn("Bank balance:  800.00", log_text)
        self.assertIn("Difference:    0.00", log_text)

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestRunApp(unittest.TestCase):
    @patch("ynab.cli.convert_bank_transactions")
    def test_run_app_upload_calls_convert_with_defaults(self, mock_convert):
        from ynab.cli import run_app
        from ynab.converter import _CONFIG_DIR
        with patch.object(sys, "argv", ["ynab", "upload"]):
            run_app()
        mock_convert.assert_called_once_with(
            input_dir=str(_CONFIG_DIR / "input"),
            output_dir=str(_CONFIG_DIR / "output"),
            dedup_enabled=False,
            upload_enabled=True,
            approve_enabled=False,
            reconcile_enabled=False,
            global_budget_id=None,
        )

    @patch("ynab.cli.convert_bank_transactions")
    def test_run_app_upload_passes_flags(self, mock_convert):
        from ynab.cli import run_app
        with patch.object(sys, "argv", [
            "ynab", "upload",
            "--input-dir", "/tmp/in",
            "--output-dir", "/tmp/out",
            "--dedup",
            "--approve",
            "--reconcile",
            "--budget-id", "b-uuid",
        ]):
            run_app()
        mock_convert.assert_called_once_with(
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            dedup_enabled=True,
            upload_enabled=True,
            approve_enabled=True,
            reconcile_enabled=True,
            global_budget_id="b-uuid",
        )

    def test_run_app_no_subcommand_prints_help(self):
        from ynab.cli import run_app
        with patch.object(sys, "argv", ["ynab"]):
            with patch("ynab.cli.build_parser") as mock_build:
                mock_parser = mock_build.return_value
                mock_parser.parse_args.return_value.command = None
                run_app()
        mock_parser.print_help.assert_called_once()


class TestRunInit(unittest.TestCase):
    def test_init_creates_directories_and_template(self):
        from importlib.resources import files
        from ynab.cli import run_init
        expected_template = files("ynab.templates").joinpath("accounts.toml.example").read_text(encoding="utf-8")
        with patch("ynab.cli._CONFIG_DIR") as mock_dir:
            mock_dir.mkdir = unittest.mock.MagicMock()
            input_dir = unittest.mock.MagicMock()
            output_dir = unittest.mock.MagicMock()
            accounts_path = unittest.mock.MagicMock()
            accounts_path.exists.return_value = False
            mock_dir.__truediv__ = lambda self, key: {
                "input": input_dir,
                "output": output_dir,
                "accounts.toml": accounts_path,
            }[key]
            run_init()
        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        input_dir.mkdir.assert_called_once_with(exist_ok=True)
        output_dir.mkdir.assert_called_once_with(exist_ok=True)
        accounts_path.write_text.assert_called_once_with(expected_template)

    def test_init_skips_existing_accounts_toml(self):
        from ynab.cli import run_init
        with patch("ynab.cli._CONFIG_DIR") as mock_dir:
            mock_dir.mkdir = unittest.mock.MagicMock()
            input_dir = unittest.mock.MagicMock()
            output_dir = unittest.mock.MagicMock()
            accounts_path = unittest.mock.MagicMock()
            accounts_path.exists.return_value = True
            mock_dir.__truediv__ = lambda self, key: {
                "input": input_dir,
                "output": output_dir,
                "accounts.toml": accounts_path,
            }[key]
            run_init()
        accounts_path.write_text.assert_not_called()
