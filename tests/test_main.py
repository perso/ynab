import os
import unittest
from tempfile import mkdtemp
from unittest.mock import patch

from ynab.main import convert_bank_transactions, fetch_transactions


class TestConvertBankTransactions(unittest.TestCase):
    def _write_input_csv(self, path: str, rows: list[str]) -> None:
        header = '"Pvm";"Luokka";"Alaluokka";"Saaja/Maksaja";"Määrä";"Saldo";"Tila";"Tarkastus"'
        content = "\n".join([header] + rows)
        with open(path, "wb") as f:
            f.write(content.encode("iso-8859-1"))

    def test_filters_pending_transactions(self):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"8 588,83";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"";"Odottaa";"Ei"',
        ])

        with patch("ynab.main.form_file_paths", return_value=[(input_file, output_file)]):
            convert_bank_transactions()

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines[0], "Date,Payee,Memo,Amount\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("Shop A", lines[1])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_deduplicates_and_sorts_by_date(self):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"20.04.2023";"Cat";"Sub";"Shop A";"-55,00";"100,00";"Toteutunut";"Ei"',
            '"19.04.2023";"Cat";"Sub";"Shop B";"-7,70";"200,00";"Toteutunut";"Ei"',
        ])

        with patch("ynab.main.form_file_paths", return_value=[(input_file, output_file)]):
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

    def test_empty_input_writes_only_header(self):
        temp_dir = mkdtemp()
        input_file = f"{temp_dir}/input.csv"
        output_file = f"{temp_dir}/output.csv"
        self._write_input_csv(input_file, [])

        with patch("ynab.main.form_file_paths", return_value=[(input_file, output_file)]):
            convert_bank_transactions()

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(lines, ["Date,Payee,Memo,Amount\n"])

        os.remove(input_file)
        os.remove(output_file)
        os.removedirs(temp_dir)

    def test_no_file_paths_does_nothing(self):
        with patch("ynab.main.form_file_paths", return_value=[]):
            convert_bank_transactions()


class TestRunApp(unittest.TestCase):
    @patch("ynab.main.convert_bank_transactions")
    def test_run_app_calls_convert(self, mock_convert):
        from ynab.main import run_app
        run_app()
        mock_convert.assert_called_once()


class TestFetchTransactions(unittest.TestCase):
    @patch("ynab.main.YnabApiClient.get_transactions")
    @patch("ynab.main.read_credentials_file")
    def test_calls_api_with_credentials(self, mock_credentials, mock_get_transactions):
        mock_credentials.return_value = "test_token"
        mock_get_transactions.return_value = []
        fetch_transactions()
        mock_credentials.assert_called_once()
        mock_get_transactions.assert_called_once()

    @patch("ynab.main.YnabApiClient.get_transactions")
    @patch("ynab.main.read_credentials_file")
    def test_logs_each_transaction(self, mock_credentials, mock_get_transactions):
        mock_credentials.return_value = "test_token"
        mock_get_transactions.return_value = ["tx1", "tx2"]
        with patch("ynab.main.log") as mock_log:
            fetch_transactions()
        self.assertEqual(mock_log.info.call_count, 2)
