import unittest
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from ynab.spending_trends import (
    CategoryTrend,
    _add_months,
    _avg_range_label,
    _month_label,
    _month_short,
    compute_trends,
    render_trends,
    run_trends,
)
from ynab.ynab_api.ynab_api_client import BudgetMonth, CategorySummary


def _cat(name, group, activity, hidden=False, deleted=False):
    return CategorySummary(
        name=name,
        category_group_name=group,
        budgeted=0,
        activity=activity,
        balance=0,
        hidden=hidden,
        deleted=deleted,
    )


_DINING = _cat("Dining Out", "Food", -187200)    # spent 187.20
_GROCERIES = _cat("Groceries", "Food", -431460)  # spent 431.46
_ENTERTAIN = _cat("Entertainment", "Fun", -12000) # spent 12.00
_RENT = _cat("Rent", "Housing", -1200000)         # spent 1200.00

_DINING_H1 = _cat("Dining Out", "Food", -82300)  # history: 82.30
_DINING_H2 = _cat("Dining Out", "Food", -50000)  # history: 50.00
_DINING_H3 = _cat("Dining Out", "Food", -115000) # history: 115.00

_ENTERTAIN_H1 = _cat("Entertainment", "Fun", -45000)  # history: 45.00
_ENTERTAIN_H2 = _cat("Entertainment", "Fun", -60000)
_ENTERTAIN_H3 = _cat("Entertainment", "Fun", -30000)


def _month(month_str, *cats):
    return BudgetMonth(month=month_str, categories=list(cats))


class TestAddMonths(unittest.TestCase):
    def test_subtract_one_month(self):
        self.assertEqual(_add_months(date(2026, 5, 30), -1), date(2026, 4, 1))

    def test_subtract_across_year_boundary(self):
        self.assertEqual(_add_months(date(2026, 1, 15), -1), date(2025, 12, 1))

    def test_subtract_four_months(self):
        self.assertEqual(_add_months(date(2026, 5, 30), -4), date(2026, 1, 1))

    def test_add_positive_months(self):
        self.assertEqual(_add_months(date(2026, 11, 1), 2), date(2027, 1, 1))


class TestLabelHelpers(unittest.TestCase):
    def test_month_label(self):
        self.assertEqual(_month_label("2026-04-01"), "April 2026")

    def test_month_short(self):
        self.assertEqual(_month_short("2026-04-01"), "Apr 2026")

    def test_avg_range_label(self):
        months = ["2026-03-01", "2026-01-01", "2026-02-01"]
        self.assertEqual(_avg_range_label(months), "Jan–Mar 2026")

    def test_avg_range_label_cross_year(self):
        months = ["2026-01-01", "2025-11-01", "2025-12-01"]
        self.assertEqual(_avg_range_label(months), "Nov–Jan 2026")


class TestComputeTrends(unittest.TestCase):
    def _history(self, *month_tuples):
        return [_month(spec[0], *spec[1:]) for spec in month_tuples]

    def test_climbing_category(self):
        comparison = _month("2026-04-01", _DINING)
        history = self._history(
            ("2026-03-01", _DINING_H1),
            ("2026-02-01", _DINING_H2),
            ("2026-01-01", _DINING_H3),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(len(climbing), 1)
        self.assertAlmostEqual(climbing[0].current_spend, 187.20, places=2)
        self.assertAlmostEqual(climbing[0].avg_spend, (82.30 + 50.00 + 115.00) / 3, places=2)
        self.assertGreater(climbing[0].change, 0)
        self.assertEqual(easing, [])

    def test_easing_category(self):
        comparison = _month("2026-04-01", _ENTERTAIN)
        history = self._history(
            ("2026-03-01", _ENTERTAIN_H1),
            ("2026-02-01", _ENTERTAIN_H2),
            ("2026-01-01", _ENTERTAIN_H3),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(len(easing), 1)
        self.assertLess(easing[0].change, 0)
        self.assertEqual(climbing, [])

    def test_sorted_by_absolute_change(self):
        big_change = _cat("Big", "G", -500000)   # 500, avg will be ~82
        small_change = _cat("Small", "G", -200000) # 200, avg will be ~82
        comparison = _month("2026-04-01", big_change, small_change)
        history = self._history(
            ("2026-03-01", _cat("Big", "G", -82300), _cat("Small", "G", -82300)),
            ("2026-02-01", _cat("Big", "G", -82300), _cat("Small", "G", -82300)),
            ("2026-01-01", _cat("Big", "G", -82300), _cat("Small", "G", -82300)),
        )
        climbing, _ = compute_trends(comparison, history, top_n=5)

        self.assertEqual(climbing[0].name, "Big")
        self.assertEqual(climbing[1].name, "Small")

    def test_top_n_limits_results(self):
        cats = [_cat(f"Cat{i}", "G", -100000) for i in range(10)]
        hist_cats = [_cat(f"Cat{i}", "G", -50000) for i in range(10)]
        comparison = _month("2026-04-01", *cats)
        history = self._history(
            ("2026-03-01", *hist_cats),
            ("2026-02-01", *hist_cats),
            ("2026-01-01", *hist_cats),
        )
        climbing, _ = compute_trends(comparison, history, top_n=3)

        self.assertEqual(len(climbing), 3)

    def test_excludes_new_categories(self):
        new_cat = _cat("Brand New", "G", -100000)
        comparison = _month("2026-04-01", new_cat)
        history = self._history(
            ("2026-03-01",),
            ("2026-02-01",),
            ("2026-01-01",),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(climbing, [])
        self.assertEqual(easing, [])

    def test_excludes_absent_this_month(self):
        comparison = _month("2026-04-01")  # no Dining Out this month
        history = self._history(
            ("2026-03-01", _DINING_H1),
            ("2026-02-01", _DINING_H2),
            ("2026-01-01", _DINING_H3),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(climbing, [])
        self.assertEqual(easing, [])

    def test_excludes_hidden_categories(self):
        hidden = _cat("Hidden", "G", -100000, hidden=True)
        comparison = _month("2026-04-01", hidden)
        hist_hidden = _cat("Hidden", "G", -50000, hidden=True)
        history = self._history(
            ("2026-03-01", hist_hidden),
            ("2026-02-01", hist_hidden),
            ("2026-01-01", hist_hidden),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(climbing, [])
        self.assertEqual(easing, [])

    def test_average_divides_by_three_even_when_absent_in_some_months(self):
        # Category appears in only 1 of 3 history months → avg = activity/3, not activity/1
        comparison = _month("2026-04-01", _DINING)
        history = self._history(
            ("2026-03-01", _DINING_H1),  # only present here
            ("2026-02-01",),
            ("2026-01-01",),
        )
        climbing, _ = compute_trends(comparison, history, top_n=5)

        self.assertEqual(len(climbing), 1)
        self.assertAlmostEqual(climbing[0].avg_spend, 82.30 / 3, places=2)

    def test_zero_activity_in_comparison_excluded(self):
        zero_cat = _cat("Zero", "G", 0)
        comparison = _month("2026-04-01", zero_cat)
        hist_cat = _cat("Zero", "G", -50000)
        history = self._history(
            ("2026-03-01", hist_cat),
            ("2026-02-01", hist_cat),
            ("2026-01-01", hist_cat),
        )
        climbing, easing = compute_trends(comparison, history, top_n=5)

        self.assertEqual(climbing, [])
        self.assertEqual(easing, [])


class TestRenderTrends(unittest.TestCase):
    def _make_trend(self, name, current, avg):
        return CategoryTrend(
            name=name,
            category_group_name="Food",
            current_spend=current,
            avg_spend=avg,
            change=current - avg,
        )

    @patch("sys.stdout", new_callable=StringIO)
    def test_renders_title_with_month_and_range(self, mock_stdout):
        t = self._make_trend("Dining Out", 187.20, 82.30)
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [t], [])
        output = mock_stdout.getvalue()

        self.assertIn("April 2026", output)
        self.assertIn("Jan–Mar", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_renders_climbing_and_easing_sections(self, mock_stdout):
        climbing = [self._make_trend("Dining Out", 187.20, 82.30)]
        easing = [self._make_trend("Entertainment", 12.00, 45.00)]
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], climbing, easing)
        output = mock_stdout.getvalue()

        self.assertIn("Climbing", output)
        self.assertIn("Easing", output)
        self.assertIn("Dining Out", output)
        self.assertIn("Entertainment", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_climbing_change_shown_with_plus_sign(self, mock_stdout):
        t = self._make_trend("Dining Out", 187.20, 82.30)
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [t], [])
        output = mock_stdout.getvalue()

        self.assertIn("+104.90", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_easing_change_shown_with_minus_sign(self, mock_stdout):
        t = self._make_trend("Entertainment", 12.00, 45.00)
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [], [t])
        output = mock_stdout.getvalue()

        self.assertIn("-33.00", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_empty_section_shows_none(self, mock_stdout):
        t = self._make_trend("Dining Out", 187.20, 82.30)
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [t], [])
        output = mock_stdout.getvalue()

        self.assertIn("(none)", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_no_data_shows_message(self, mock_stdout):
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [], [])
        output = mock_stdout.getvalue()

        self.assertIn("no trend data", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_col_label_shows_comparison_month(self, mock_stdout):
        t = self._make_trend("Dining Out", 187.20, 82.30)
        render_trends("2026-04-01", ["2026-01-01", "2026-02-01", "2026-03-01"], [t], [])
        output = mock_stdout.getvalue()

        self.assertIn("Apr 2026", output)


class TestRunTrends(unittest.TestCase):
    @patch("ynab.spending_trends.render_trends")
    @patch("ynab.spending_trends.compute_trends", return_value=([], []))
    @patch("ynab.spending_trends.read_credentials_file", return_value="tok")
    @patch("ynab.spending_trends._collect_budget_ids", return_value=["bud-1"])
    def test_fetches_four_months(self, mock_ids, mock_creds, mock_compute, mock_render):
        fake_svc = MagicMock()
        fake_svc.get_budget_month.return_value = BudgetMonth(month="2026-04-01", categories=[])

        run_trends(today=date(2026, 5, 15), budget_service_factory=lambda tok: fake_svc)

        self.assertEqual(fake_svc.get_budget_month.call_count, 4)
        calls = [c.args[1] for c in fake_svc.get_budget_month.call_args_list]
        self.assertEqual(calls[0], "2026-04-01")  # M-1 comparison
        self.assertIn("2026-03-01", calls)         # M-2
        self.assertIn("2026-02-01", calls)         # M-3
        self.assertIn("2026-01-01", calls)         # M-4

    @patch("ynab.spending_trends._collect_budget_ids", return_value=[])
    def test_exits_when_no_budget_ids(self, _mock_ids):
        with self.assertRaises(SystemExit):
            run_trends()

    @patch("ynab.spending_trends.render_trends")
    @patch("ynab.spending_trends.compute_trends", return_value=([], []))
    @patch("ynab.spending_trends.read_credentials_file", return_value="tok")
    @patch("ynab.spending_trends._collect_budget_ids", return_value=["bud-1"])
    def test_passes_top_n_to_compute(self, mock_ids, mock_creds, mock_compute, mock_render):
        fake_svc = MagicMock()
        fake_svc.get_budget_month.return_value = BudgetMonth(month="2026-04-01", categories=[])

        run_trends(top_n=3, today=date(2026, 5, 15), budget_service_factory=lambda tok: fake_svc)

        _, _, top_n_arg = mock_compute.call_args.args
        self.assertEqual(top_n_arg, 3)
