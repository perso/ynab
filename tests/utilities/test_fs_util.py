import os
import unittest
from tempfile import mkdtemp

from ynab.utilities.fs_util import FilePathMapping, form_file_paths


class TestFileSystemUtil(unittest.TestCase):
    def test_form_file_paths(self):
        temp_dir = mkdtemp()
        test_file = f"{temp_dir}/FI1234567890_2023.03.24-2023.04.24.csv"

        open(test_file, mode="w")

        test_budget_map = {"FI1234567890": "TestBudget"}
        expected_output = [
            FilePathMapping(
                "FI1234567890",
                test_file,
                f"{temp_dir}/TestBudget_2023.03.24-2023.04.24.csv",
            )
        ]

        paths = form_file_paths(input_dir=temp_dir,
                                output_dir=temp_dir,
                                accountno_budget_map=test_budget_map)

        self.assertEqual(expected_output, paths)

        os.remove(test_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_empty_dir(self):
        temp_dir = mkdtemp()
        paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map={})
        self.assertEqual([], paths)
        os.removedirs(temp_dir)

    def test_form_file_paths_unknown_account(self):
        temp_dir = mkdtemp()
        test_file = f"{temp_dir}/UNKNOWN_2023.csv"
        open(test_file, mode="w")

        with self.assertLogs("ynab.utilities.fs_util", level="WARNING") as cm:
            paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map={})
        self.assertEqual([], paths)
        self.assertTrue(any("UNKNOWN" in msg for msg in cm.output))

        os.remove(test_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_multiple_files(self):
        temp_dir = mkdtemp()
        file1 = f"{temp_dir}/FI111_period1.csv"
        file2 = f"{temp_dir}/FI222_period2.csv"
        open(file1, mode="w")
        open(file2, mode="w")

        budget_map = {"FI111": "BudgetA", "FI222": "BudgetB"}
        paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map=budget_map)

        self.assertEqual(len(paths), 2)
        input_paths = {p.input_path for p in paths}
        output_paths = {p.output_path for p in paths}
        self.assertIn(file1, input_paths)
        self.assertIn(file2, input_paths)
        self.assertIn(f"{temp_dir}/BudgetA_period1.csv", output_paths)
        self.assertIn(f"{temp_dir}/BudgetB_period2.csv", output_paths)

        os.remove(file1)
        os.remove(file2)
        os.removedirs(temp_dir)

    def test_form_file_paths_ignores_non_csv_files(self):
        temp_dir = mkdtemp()
        csv_file = f"{temp_dir}/FI111_data.csv"
        txt_file = f"{temp_dir}/FI111_data.txt"
        open(csv_file, mode="w")
        open(txt_file, mode="w")

        budget_map = {"FI111": "BudgetA"}
        paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map=budget_map)

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].input_path, csv_file)

        os.remove(csv_file)
        os.remove(txt_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_filename_without_underscore(self):
        temp_dir = mkdtemp()
        csv_file = f"{temp_dir}/export.csv"
        open(csv_file, mode="w")

        with self.assertLogs("ynab.utilities.fs_util", level="WARNING") as cm:
            paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map={})
        self.assertEqual([], paths)
        self.assertTrue(any("export.csv" in msg for msg in cm.output))

        os.remove(csv_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_single_file(self):
        temp_dir = mkdtemp()
        csv_file = f"{temp_dir}/FI1234567890_2023.03.24-2023.04.24.csv"
        open(csv_file, mode="w")

        budget_map = {"FI1234567890": "TestBudget"}
        paths = form_file_paths(input_dir=csv_file, output_dir=temp_dir, accountno_budget_map=budget_map)

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].input_path, csv_file)
        self.assertEqual(paths[0].output_path, f"{temp_dir}/TestBudget_2023.03.24-2023.04.24.csv")

        os.remove(csv_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_single_file_unknown_account(self):
        temp_dir = mkdtemp()
        csv_file = f"{temp_dir}/UNKNOWN_2023.csv"
        open(csv_file, mode="w")

        with self.assertLogs("ynab.utilities.fs_util", level="WARNING") as cm:
            paths = form_file_paths(input_dir=csv_file, output_dir=temp_dir, accountno_budget_map={})
        self.assertEqual([], paths)
        self.assertTrue(any("UNKNOWN" in msg for msg in cm.output))

        os.remove(csv_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_single_file_bad_filename(self):
        temp_dir = mkdtemp()
        csv_file = f"{temp_dir}/export.csv"
        open(csv_file, mode="w")

        with self.assertLogs("ynab.utilities.fs_util", level="WARNING") as cm:
            paths = form_file_paths(input_dir=csv_file, output_dir=temp_dir, accountno_budget_map={})
        self.assertEqual([], paths)
        self.assertTrue(any("export.csv" in msg for msg in cm.output))

        os.remove(csv_file)
        os.removedirs(temp_dir)

    def test_form_file_paths_suffix_with_multiple_underscores(self):
        temp_dir = mkdtemp()
        test_file = f"{temp_dir}/FI123_2023_04_export.csv"
        open(test_file, mode="w")

        budget_map = {"FI123": "MyBudget"}
        paths = form_file_paths(input_dir=temp_dir, output_dir=temp_dir, accountno_budget_map=budget_map)

        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].output_path, f"{temp_dir}/MyBudget_2023_04_export.csv")

        os.remove(test_file)
        os.removedirs(temp_dir)
