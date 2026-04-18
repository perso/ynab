import os
import tempfile
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from ynab.utilities.config_util import AccountConfig, read_accounts_config, read_credentials_file


class TestConfigUtil(unittest.TestCase):
    def test_read_credentials_file_when_exists(self):
        contents = "secret"

        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, contents)

    def test_read_credentials_file_when_not_exists(self):
        contents = "secret"

        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        with self.assertRaises(FileNotFoundError):
            read_credentials_file("path/does/not/exist")

        os.remove(temp_file_path)

    def test_read_credentials_file_strips_whitespace(self):
        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("my-token\n")
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, "my-token")

        os.remove(temp_file_path)


def _write_toml(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
    f.write(content)
    f.close()
    return Path(f.name)


class TestReadAccountsConfig(unittest.TestCase):
    def test_full_config(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "MyAccount"
budget_id   = "b1"
account_id  = "a1"
""")
        result = read_accounts_config(path)
        self.assertEqual(result, {"FI123": AccountConfig("MyAccount", "b1", "a1")})
        os.remove(path)

    def test_optional_ids_absent(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "MyAccount"
""")
        result = read_accounts_config(path)
        self.assertEqual(result, {"FI123": AccountConfig("MyAccount", None, None)})
        os.remove(path)

    def test_multiple_accounts(self):
        path = _write_toml("""
[accounts.FI111]
budget_name = "Checking"
budget_id   = "b1"
account_id  = "a1"

[accounts.FI222]
budget_name = "MasterCard"
""")
        result = read_accounts_config(path)
        self.assertEqual(result["FI111"], AccountConfig("Checking", "b1", "a1"))
        self.assertEqual(result["FI222"], AccountConfig("MasterCard", None, None))
        os.remove(path)

    def test_empty_accounts_section(self):
        path = _write_toml("[accounts]\n")
        result = read_accounts_config(path)
        self.assertEqual(result, {})
        os.remove(path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_accounts_config("/nonexistent/accounts.toml")

    def test_missing_budget_name_raises(self):
        path = _write_toml("""
[accounts.FI123]
budget_id = "b1"
""")
        with self.assertRaises(ValueError) as ctx:
            read_accounts_config(path)
        self.assertIn("FI123", str(ctx.exception))
        os.remove(path)

    def test_accepts_path_object(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "Budget"
""")
        result = read_accounts_config(Path(path))
        self.assertEqual(result["FI123"].budget_name, "Budget")
        os.remove(path)

    def test_date_tolerance_days_parsed(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "MyAccount"
budget_id   = "b1"
account_id  = "a1"
date_tolerance_days = 7
""")
        result = read_accounts_config(path)
        self.assertEqual(result["FI123"].date_tolerance_days, 7)
        os.remove(path)

    def test_date_tolerance_days_absent_is_none(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "MyAccount"
""")
        result = read_accounts_config(path)
        self.assertIsNone(result["FI123"].date_tolerance_days)
        os.remove(path)