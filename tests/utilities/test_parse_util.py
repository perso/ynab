import unittest
from datetime import date

from ynab.utilities.parse_util import parse_date, parse_amount_sign_leading, parse_required_amount


class TestParseUtil(unittest.TestCase):
    def test_parse_valid_date(self):
        d = parse_date('21.09.1987')
        self.assertEqual(date(1987, 9, 21), d)

    def test_parse_invalid_date(self):
        self.assertRaises(Exception, parse_date, '21-09-1987')

    def test_parse_date_leap_year(self):
        self.assertEqual(date(2024, 2, 29), parse_date('29.02.2024'))

    def test_parse_date_invalid_calendar_date(self):
        with self.assertRaises(ValueError):
            parse_date('31.02.2023')

    def test_parse_date_year_boundaries(self):
        self.assertEqual(date(2023, 1, 1), parse_date('01.01.2023'))
        self.assertEqual(date(2023, 12, 31), parse_date('31.12.2023'))

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

    def test_parse_amount_with_thousands_space(self):
        self.assertAlmostEqual(8588.83, parse_amount_sign_leading('8 588,83'))
        self.assertAlmostEqual(-1234.56, parse_amount_sign_leading('-1 234,56'))

    def test_parse_amount_large_number(self):
        self.assertAlmostEqual(1000000.0, parse_amount_sign_leading('1 000 000,00'))

    def test_parse_required_amount_valid(self):
        self.assertAlmostEqual(-55.0, parse_required_amount('-55,00'))

    def test_parse_required_amount_empty_raises(self):
        with self.assertRaises(ValueError):
            parse_required_amount('')
