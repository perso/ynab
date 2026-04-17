import os
import unittest
from datetime import date
from tempfile import mkdtemp
from typing import Optional
from unittest.mock import patch

from ynab.main import convert_bank_transactions, fetch_transactions
from ynab.utilities.fs_util import FilePathMapping
from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabTransaction

# Nested shape — the canonical format going forward.
_ENV_CONVERT = {"YNAB_ACCOUNTNO_BUDGET_MAP": '{"FI111": {"budget_name": "Budget"}}'}
_ENV_FETCH = {"YNAB_BUDGET_ID": "test-budget-id"}
_ENV_DEDUP = {
    "YNAB_ACCOUNTNO_BUDGET_MAP": '{"FI111": {"budget_name": "Budget", "budget_id": "b1", "account_id": "a1"}}',
    "YNAB_DEDUP_ENABLED": "true",
}

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
        deleted=False,
        account_name="",
        payee_name="",
        category_name="",
    )


class _FakeBudgetService:
    """Test double for BudgetService — records calls and returns a preset response."""

    def __init__(self, response: TransactionsResponse = _EMPTY_RESPONSE) -> None:
        self.response = response
        self.calls: list[tuple] = []

    def get_transactions(
        self,
        budget_id: str,
        since_date: date,
        last_knowledge_of_server: Optional[int] = None,
    ) -> TransactionsResponse:
        self.calls.append((budget_id, since_date, last_knowledge_of_server))
        return self.response


class TestConvertBankTransactions(unittest.TestCase):
    def _write_input_csv(self, path: str, rows: list[str]) -> None:
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header] + rows)
        with open(path, "wb") as f:
            f.write(content.encode("iso-8859-1"))

    @patch.dict(os.environ, _ENV_CONVERT)
    def test_filters_pending_transactions(self):
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

    @patch.dict(os.environ, _ENV_CONVERT)
    def test_deduplicates_and_sorts_by_date(self):
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

    @patch.dict(os.environ, _ENV_CONVERT)
    def test_empty_input_writes_only_header(self):
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

    @patch.dict(os.environ, _ENV_CONVERT)
    def test_no_file_paths_does_nothing(self):
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
        last_knowledge: Optional[int] = None,
    ) -> None:
        with (
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
            patch("ynab.main.load_server_knowledge", return_value=last_knowledge),
            patch("ynab.main.save_server_knowledge"),
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

        budget_id, since_date, _knowledge = service.calls[0]
        self.assertEqual(budget_id, "b1")
        # min date is 2023-04-20, minus 3-day tolerance → 2023-04-17
        self.assertEqual(since_date, date(2023, 4, 17))

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_DEDUP)
    def test_passes_knowledge_to_service_and_saves_new_value(self):
        service = _FakeBudgetService(TransactionsResponse(transactions=[], server_knowledge=99))

        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop";"-10,00";"100,00";"Toteutunut";"Ei"',
        ])

        with (
            patch("ynab.main.form_file_paths",
                  return_value=[FilePathMapping("FI111", input_file, output_file)]),
            patch("ynab.main.read_credentials_file", return_value="token"),
            patch("ynab.main.load_server_knowledge", return_value=42),
            patch("ynab.main.save_server_knowledge") as mock_save,
        ):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        _budget_id, _since_date, knowledge = service.calls[0]
        self.assertEqual(knowledge, 42)
        mock_save.assert_called_once_with("b1", "a1", 99)

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

        with patch("ynab.main.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            convert_bank_transactions(budget_service_factory=lambda _token: service)

        self.assertEqual(service.calls, [])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    @patch.dict(os.environ, _ENV_CONVERT)
    @patch("ynab.main.read_credentials_file")
    def test_credentials_not_loaded_when_dedup_disabled(self, mock_creds):
        with patch("ynab.main.form_file_paths", return_value=[]):
            convert_bank_transactions()
        mock_creds.assert_not_called()

    @patch.dict(os.environ, {
        "YNAB_ACCOUNTNO_BUDGET_MAP": '{"FI111": {"budget_name": "Budget"}}',
        "YNAB_DEDUP_ENABLED": "true",
    })
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

        with patch("ynab.main.form_file_paths",
                   return_value=[FilePathMapping("FI111", input_file, output_file)]):
            with self.assertRaises(ValueError) as ctx:
                convert_bank_transactions(budget_service_factory=lambda _token: service)

        self.assertIn("FI111", str(ctx.exception))

        os.remove(input_file)
        os.removedirs(temp_dir)


class TestRunApp(unittest.TestCase):
    @patch("ynab.main.convert_bank_transactions")
    def test_run_app_calls_convert(self, mock_convert):
        from ynab.main import run_app
        run_app()
        mock_convert.assert_called_once()


class TestFetchTransactions(unittest.TestCase):
    @patch.dict(os.environ, _ENV_FETCH)
    @patch("ynab.main.YnabApiClient.get_transactions")
    @patch("ynab.main.read_credentials_file")
    def test_calls_api_with_credentials(self, mock_credentials, mock_get_transactions):
        mock_credentials.return_value = "test_token"
        mock_get_transactions.return_value = _EMPTY_RESPONSE
        fetch_transactions()
        mock_credentials.assert_called_once()
        mock_get_transactions.assert_called_once()

    @patch.dict(os.environ, _ENV_FETCH)
    @patch("ynab.main.YnabApiClient.get_transactions")
    @patch("ynab.main.read_credentials_file")
    def test_logs_each_transaction(self, mock_credentials, mock_get_transactions):
        mock_credentials.return_value = "test_token"
        mock_get_transactions.return_value = TransactionsResponse(
            transactions=["tx1", "tx2"], server_knowledge=0  # type: ignore[list-item]
        )
        with patch("ynab.main.log") as mock_log:
            fetch_transactions()
        self.assertEqual(mock_log.info.call_count, 2)
