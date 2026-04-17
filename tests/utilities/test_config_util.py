import os
import unittest
from tempfile import NamedTemporaryFile

from ynab.utilities.config_util import read_credentials_file


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
