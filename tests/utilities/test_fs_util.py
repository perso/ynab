import os
import unittest
from tempfile import mkdtemp

from ynab.utilities.fs_util import form_file_paths


class TestFileSystemUtil(unittest.TestCase):
    def test_form_file_paths(self):
        temp_dir = mkdtemp()
        test_file = f"{temp_dir}/FI1234567890_2023.03.24-2023.04.24.csv"

        open(test_file, mode="w")

        test_budget_map = {"FI1234567890": "TestBudget"}
        expected_output = [(test_file, f"{temp_dir}/TestBudget_2023.03.24-2023.04.24.csv")]

        paths = form_file_paths(input_dir=temp_dir,
                                output_dir=temp_dir,
                                accountno_budget_map=test_budget_map)

        self.assertEqual(expected_output, paths)

        os.remove(test_file)
        os.removedirs(temp_dir)
