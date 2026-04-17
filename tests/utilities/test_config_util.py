import os
import unittest
from tempfile import NamedTemporaryFile

from ynab.utilities.config_util import AccountConfig, parse_accountno_budget_map, read_credentials_file


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

    def test_read_credentials_file_preserves_whitespace(self):
        contents = "token_with_trailing_newline\n"

        with NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(contents)
            temp_file_path = temp_file.name

        result = read_credentials_file(temp_file_path)
        self.assertEqual(result, contents)

        os.remove(temp_file_path)


class TestParseAccountnoBudgetMap(unittest.TestCase):
    def test_legacy_flat_shape(self):
        raw = '{"FI123": "Budget"}'
        result = parse_accountno_budget_map(raw)
        self.assertEqual(result, {"FI123": AccountConfig("Budget", None, None)})

    def test_nested_shape_full(self):
        raw = '{"FI123": {"budget_name": "Budget", "budget_id": "b1", "account_id": "a1"}}'
        result = parse_accountno_budget_map(raw)
        self.assertEqual(result, {"FI123": AccountConfig("Budget", "b1", "a1")})

    def test_nested_shape_partial_ids(self):
        raw = '{"FI123": {"budget_name": "Budget"}}'
        result = parse_accountno_budget_map(raw)
        self.assertEqual(result, {"FI123": AccountConfig("Budget", None, None)})

    def test_mixed_legacy_and_nested(self):
        raw = '{"FI1": "OldBudget", "FI2": {"budget_name": "NewBudget", "budget_id": "b2", "account_id": "a2"}}'
        result = parse_accountno_budget_map(raw)
        self.assertEqual(result["FI1"], AccountConfig("OldBudget", None, None))
        self.assertEqual(result["FI2"], AccountConfig("NewBudget", "b2", "a2"))

    def test_malformed_json_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_accountno_budget_map("not json")

    def test_missing_budget_name_raises_value_error(self):
        raw = '{"FI123": {"budget_id": "b1"}}'
        with self.assertRaises(ValueError) as ctx:
            parse_accountno_budget_map(raw)
        self.assertIn("FI123", str(ctx.exception))

    def test_empty_map(self):
        result = parse_accountno_budget_map("{}")
        self.assertEqual(result, {})
