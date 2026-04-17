import unittest
from datetime import date

from ynab.utilities.parse_util import parse_date, parse_amount_sign_leading


class TestParseUtil(unittest.TestCase):
    def test_parse_valid_date(self):
        d = parse_date('21.09.1987')
        self.assertEqual(date(1987, 9, 21), d)

    def test_parse_invalid_date(self):
        self.assertRaises(Exception, parse_date, '21-09-1987')

    def test_parse_amount_sign_leading(self):
        test_cases = [
            ('+20,43', 20.43),
            ('-19,15', -19.15),
            ('39,99', 39.99),
            ('1', 1.0),
            ('0,5', 0.5),
            ('', None),
        ]
        for test_case in test_cases:
            result = parse_amount_sign_leading(test_case[0])
            self.assertEqual(test_case[1], result)
