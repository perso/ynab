import os
import unittest
from datetime import date
from tempfile import mkdtemp
from typing import List
from unittest.mock import patch

from ynab.bank.transaction import BankTransaction
from ynab.main import convert_bank_transactions
from ynab.utilities.config_util import AccountConfig
from ynab.utilities.fs_util import FilePathMapping
from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabTransaction

_ACCOUNT_CONFIG_SIMPLE = {"FI111": AccountConfig("Budget", None, None)}
_ACCOUNT_CONFIG_DEDUP = {"FI111": AccountConfig("Budget", "b1", "a1")}
_ENV_DEDUP = {"YNAB_DEDUP_ENABLED": "true"}
_ENV_NO_DEDUP = {"YNAB_DEDUP_ENABLED": "", "YNAB_UPLOAD_ENABLED": ""}
_ENV_UPLOAD = {"YNAB_UPLOAD_ENABLED": "true", "YNAB_DEDUP_ENABLED": ""}

_EMPTY_RESPONSE = TransactionsResponse(transactions=[], server_knowledge=0)


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


class _FakeBudgetService:
    """Test double for BudgetService — records calls and returns preset responses."""

    def __init__(self, response: TransactionsResponse = _EMPTY_RESPONSE, created_count: int = 0) -> None:
        self.response = response
        self.created_count = created_count
        self.calls: list[tuple] = []
        self.create_calls: list[tuple] = []

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
    ) -> int:
        self.create_calls.append((budget_id, account_id, transactions))
        return self.created_count


@patch.dict(os.environ, _ENV_NO_DEDUP)
class TestConvertBankTransactions(unittest.TestCase):
    def _write_input_csv(self, path: str, rows: list[str]) -> None:
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header] + rows)
        with open(path, "wb") as f:
            f.write(content.encode("iso-8859-1"))

    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_filters_pending_transactions(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"8 588,83";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"";"Odottaa";"Ei"',
        ])

        with patch("ynab.main.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions()

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines[0], "Date,Payee,Memo,Amount\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("Shop A", lines[1])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_deduplicates_and_sorts_by_date(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"200,00";"Toteutunut";"Ei"',
        ])

        with patch("ynab.main.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions()

        with open(output_file) as f:
            lines = f.readlines()

        # header + 2 unique entries (duplicate removed), sorted by date ascending
        self.assertEqual(len(lines), 3)
        self.assertIn("Shop B", lines[1])
        self.assertIn("Shop A", lines[2])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_empty_input_writes_only_header(self, _mock_cfg):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [])

        with patch("ynab.main.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions()

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines, ["Date,Payee,Memo,Amount\n"])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_no_file_paths_does_nothing(self, _mock_cfg):
        with patch("ynab.main.form_file_paths", return_value=[]):
            convert_bank_transactions()


class TestConvertBankTransactionsWithDedup(unittest.TestCase):
    """Integration tests for the dedup path using _FakeBudgetService injection."""

    def _write_input_csv(self, path: str, rows: list[str]) -> None:
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header] + rows)
        with open(path, "wb") as f:
            f.write(content.encode("iso-8859-1"))

    def _run_with_fake_service(
        self,
        input_file: str,
        output_file: str,
        service: _FakeBudgetService,
    ) -> None:
        with (
            patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

    @patch.dict(os.environ, _ENV_DEDUP)
    def test_removes_bank_rows_already_in_ynab(self):
        service = _FakeBudgetService(TransactionsResponse(
            transactions=[_make_ynab_transaction("2023-04-20", -55000, account_id="a1")],
            server_knowledge=1,
        ))

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
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

    @patch.dict(os.environ, _ENV_DEDUP)
    def test_per_account_date_tolerance_overrides_default(self):
        account_cfg_custom = {"FI111": AccountConfig("Budget", "b1", "a1", date_tolerance_days=7)}
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.main.read_accounts_config", return_value=account_cfg_custom),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        _budget_id, since_date = service.calls[0]
        # min date is 2023-04-20, minus 7-day custom tolerance → 2023-04-13
        self.assertEqual(since_date, date(2023, 4, 13))

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_DEDUP)
    def test_since_date_derived_from_min_bank_date_minus_tolerance(self):
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
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

    @patch.dict(os.environ, _ENV_DEDUP)
    @patch("ynab.main.read_credentials_file", return_value="token")
    def test_api_not_called_when_all_transactions_filtered_as_pending(self, _mock_creds):
        """No budget service call when the CLEARED filter removes all transactions."""
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"";"Odottaa";"Ei"',
        ])

        with (
            patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_DEDUP),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        self.assertEqual(service.calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_NO_DEDUP)
    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    @patch("ynab.main.read_credentials_file")
    def test_credentials_not_loaded_when_dedup_disabled(self, mock_creds, _mock_cfg):
        with patch("ynab.main.form_file_paths", return_value=[]):
            convert_bank_transactions()
        mock_creds.assert_not_called()

    @patch.dict(os.environ, _ENV_DEDUP)
    @patch("ynab.main.read_credentials_file", return_value="token")
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
            patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            self.assertRaises(ValueError) as ctx,
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        self.assertIn("FI111", str(ctx.exception))

    @patch.dict(os.environ, {**_ENV_DEDUP, "YNAB_BUDGET_ID": "env-budget-id"})
    def test_uses_global_budget_id_when_account_budget_id_absent(self):
        """budget_id absent from accounts.toml falls back to YNAB_BUDGET_ID."""
        account_cfg_no_budget_id = {"FI111": AccountConfig("Budget", None, "a1")}
        service = _FakeBudgetService()

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.main.read_accounts_config", return_value=account_cfg_no_budget_id),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        self.assertEqual(len(service.calls), 1)
        budget_id_used, _ = service.calls[0]
        self.assertEqual(budget_id_used, "env-budget-id")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestConvertBankTransactionsWithUpload(unittest.TestCase):
    """Integration tests for the YNAB_UPLOAD_ENABLED path."""

    def _write_input_csv(self, path: str, rows: list[str]) -> None:
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header] + rows)
        with open(path, "wb") as f:
            f.write(content.encode("iso-8859-1"))

    def _run_with_fake_service(
        self,
        input_file: str,
        output_file: str,
        service: _FakeBudgetService,
        account_config: dict,
    ) -> None:
        with (
            patch("ynab.main.read_accounts_config", return_value=account_config),
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

    @patch.dict(os.environ, _ENV_UPLOAD)
    def test_create_transactions_called_with_correct_args(self):
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, _ACCOUNT_CONFIG_DEDUP)

        self.assertEqual(len(service.create_calls), 1)
        budget_id, account_id, txns = service.create_calls[0]
        self.assertEqual(budget_id, "b1")
        self.assertEqual(account_id, "a1")
        self.assertEqual(len(txns), 1)
        self.assertEqual(txns[0].payee, "Shop A")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_UPLOAD)
    def test_upload_skipped_when_account_config_missing_ids(self):
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
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

    @patch.dict(os.environ, _ENV_UPLOAD)
    def test_upload_not_called_when_no_transactions(self):
        service = _FakeBudgetService()
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        # All PENDING — filtered out before upload
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"";"Odottaa";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, _ACCOUNT_CONFIG_DEDUP)

        self.assertEqual(service.create_calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_UPLOAD)
    @patch("ynab.main.read_credentials_file")
    @patch("ynab.main.read_accounts_config", return_value=_ACCOUNT_CONFIG_SIMPLE)
    def test_credentials_loaded_when_upload_enabled(self, _mock_cfg, mock_creds):
        mock_creds.return_value = "token"
        with patch("ynab.main.form_file_paths", return_value=[]):
            convert_bank_transactions()
        mock_creds.assert_called_once()

    @patch.dict(os.environ, {**_ENV_UPLOAD, "YNAB_BUDGET_ID": "env-budget-id"})
    def test_upload_uses_global_budget_id_when_account_budget_id_absent(self):
        account_cfg_no_budget_id = {"FI111": AccountConfig("Budget", None, "a1")}
        service = _FakeBudgetService(created_count=1)
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        self._run_with_fake_service(input_file, output_file, service, account_cfg_no_budget_id)

        self.assertEqual(len(service.create_calls), 1)
        budget_id_used, _, _ = service.create_calls[0]
        self.assertEqual(budget_id_used, "env-budget-id")

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)


class TestRunApp(unittest.TestCase):
    @patch("ynab.main.convert_bank_transactions")
    def test_run_app_calls_convert(self, mock_convert):
        from ynab.main import run_app
        run_app()
        mock_convert.assert_called_once()


