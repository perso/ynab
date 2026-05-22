import os
import tempfile
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from ynab.utilities.config_util import (
    AccountConfig,
    TrackingAccountConfig,
    read_accounts_config,
    read_credentials_file,
    read_payee_rules,
    read_tracking_accounts_config,
)


class TestConfigUtil(unittest.TestCase):
    def setUp(self):
        os.environ.pop("YNAB_ACCESS_TOKEN", None)

    def tearDown(self):
        os.environ.pop("YNAB_ACCESS_TOKEN", None)

    def test_read_credentials_file_when_exists(self):
        contents = "secret"

        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, contents)

    def test_read_credentials_file_when_not_exists_raises(self):
        with self.assertRaises(ValueError):
            read_credentials_file("path/does/not/exist")

    def test_read_credentials_file_strips_whitespace(self):
        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("my-token\n")
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, "my-token")

        os.remove(temp_file_path)

    def test_env_var_takes_priority_over_file(self):
        os.environ["YNAB_ACCESS_TOKEN"] = "env-token"
        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("file-token")
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, "env-token")
        os.remove(temp_file_path)

    def test_env_var_used_when_no_credentials_file(self):
        os.environ["YNAB_ACCESS_TOKEN"] = "env-token"
        result = read_credentials_file("path/does/not/exist")
        self.assertEqual(result, "env-token")

    def test_env_var_strips_whitespace(self):
        os.environ["YNAB_ACCESS_TOKEN"] = "  env-token\n"
        result = read_credentials_file("path/does/not/exist")
        self.assertEqual(result, "env-token")

    def test_neither_env_var_nor_file_raises(self):
        with self.assertRaises(ValueError) as ctx:
            read_credentials_file("path/does/not/exist")
        self.assertIn("YNAB_ACCESS_TOKEN", str(ctx.exception))


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

    def test_memo_template_parsed(self):
        path = _write_toml("""
[accounts.FI123]
budget_name   = "MyAccount"
memo_template = "{category} / {sub_category}"
""")
        result = read_accounts_config(path)
        self.assertEqual(result["FI123"].memo_template, "{category} / {sub_category}")
        os.remove(path)

    def test_memo_template_absent_is_none(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "MyAccount"
""")
        result = read_accounts_config(path)
        self.assertIsNone(result["FI123"].memo_template)
        os.remove(path)


class TestReadTrackingAccountsConfig(unittest.TestCase):
    def test_full_config(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
name       = "Nordnet Investments"
budget_id  = "b1"
account_id = "a1"
""")
        result = read_tracking_accounts_config(path)
        self.assertEqual(result, {"nordnet": TrackingAccountConfig("Nordnet Investments", "b1", "a1")})
        os.remove(path)

    def test_multiple_accounts_preserves_order(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
name       = "Nordnet"
budget_id  = "b1"
account_id = "a1"

[tracking_accounts.mortgage]
name       = "Mortgage"
budget_id  = "b1"
account_id = "a2"
""")
        result = read_tracking_accounts_config(path)
        slugs = list(result.keys())
        self.assertEqual(slugs, ["nordnet", "mortgage"])
        self.assertEqual(result["mortgage"], TrackingAccountConfig("Mortgage", "b1", "a2"))
        os.remove(path)

    def test_absent_section_returns_empty_dict(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "Checking"
""")
        result = read_tracking_accounts_config(path)
        self.assertEqual(result, {})
        os.remove(path)

    def test_missing_name_raises(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
budget_id  = "b1"
account_id = "a1"
""")
        with self.assertRaises(ValueError) as ctx:
            read_tracking_accounts_config(path)
        self.assertIn("nordnet", str(ctx.exception))
        self.assertIn("name", str(ctx.exception))
        os.remove(path)

    def test_missing_budget_id_raises(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
name       = "Nordnet"
account_id = "a1"
""")
        with self.assertRaises(ValueError) as ctx:
            read_tracking_accounts_config(path)
        self.assertIn("budget_id", str(ctx.exception))
        os.remove(path)

    def test_missing_account_id_raises(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
name      = "Nordnet"
budget_id = "b1"
""")
        with self.assertRaises(ValueError) as ctx:
            read_tracking_accounts_config(path)
        self.assertIn("account_id", str(ctx.exception))
        os.remove(path)

    def test_negative_flag_parsed(self):
        path = _write_toml("""
[tracking_accounts.mortgage]
name       = "Mortgage"
budget_id  = "b1"
account_id = "a1"
negative   = true
""")
        result = read_tracking_accounts_config(path)
        self.assertTrue(result["mortgage"].negative)
        os.remove(path)

    def test_negative_flag_defaults_to_false(self):
        path = _write_toml("""
[tracking_accounts.nordnet]
name       = "Nordnet"
budget_id  = "b1"
account_id = "a1"
""")
        result = read_tracking_accounts_config(path)
        self.assertFalse(result["nordnet"].negative)
        os.remove(path)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_tracking_accounts_config("/nonexistent/accounts.toml")


class TestReadPayeeRules(unittest.TestCase):
    def test_parses_rules(self):
        path = _write_toml("""
[payee_rules]
"K-CITYMARKET.*" = "K-Citymarket"
"IF VAKUUTUS.*"  = "If Vakuutus"
""")
        result = read_payee_rules(path)
        self.assertEqual(result, {"K-CITYMARKET.*": "K-Citymarket", "IF VAKUUTUS.*": "If Vakuutus"})
        os.remove(path)

    def test_absent_section_returns_empty_dict(self):
        path = _write_toml("""
[accounts.FI123]
budget_name = "Checking"
""")
        result = read_payee_rules(path)
        self.assertEqual(result, {})
        os.remove(path)

    def test_missing_file_returns_empty(self):
        result = read_payee_rules("/nonexistent/accounts.toml")
        self.assertEqual(result, {})

    def test_preserves_insertion_order(self):
        path = _write_toml("""
[payee_rules]
"ZETTLE.*"       = "Zettle"
"K-CITYMARKET.*" = "K-Citymarket"
"IF VAKUUTUS.*"  = "If Vakuutus"
""")
        result = read_payee_rules(path)
        self.assertEqual(list(result.keys()), ["ZETTLE.*", "K-CITYMARKET.*", "IF VAKUUTUS.*"])
        os.remove(path)