import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

from ynab.budget_dashboard import _collect_budget_ids, render_dashboard, run_status
from ynab.ynab_api.ynab_api_client import BudgetMonth, CategorySummary

_CAT_GROCERIES = CategorySummary(
    name="Groceries",
    category_group_name="Everyday Expenses",
    budgeted=400000,
    activity=-312400,
    balance=87600,
    hidden=False,
    deleted=False,
)

_CAT_DINING = CategorySummary(
    name="Dining out",
    category_group_name="Everyday Expenses",
    budgeted=150000,
    activity=-187200,
    balance=-37200,
    hidden=False,
    deleted=False,
)

_CAT_HIDDEN = CategorySummary(
    name="Hidden Cat",
    category_group_name="Other",
    budgeted=100000,
    activity=0,
    balance=100000,
    hidden=True,
    deleted=False,
)

_CAT_DELETED = CategorySummary(
    name="Deleted Cat",
    category_group_name="Other",
    budgeted=0,
    activity=0,
    balance=0,
    hidden=False,
    deleted=True,
)

_CAT_ZERO = CategorySummary(
    name="Zero Cat",
    category_group_name="Other",
    budgeted=0,
    activity=0,
    balance=0,
    hidden=False,
    deleted=False,
)


class TestRenderDashboard(unittest.TestCase):
    @patch("sys.stdout", new_callable=StringIO)
    def test_renders_header_and_rows(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES, _CAT_DINING])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertIn("2026-04-01", output)
        self.assertIn("Category", output)
        self.assertIn("Budgeted", output)
        self.assertIn("Spent", output)
        self.assertIn("Remaining", output)
        self.assertIn("Groceries", output)
        self.assertIn("Dining out", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_flags_overspent_with_warning(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_DINING])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertIn("⚠", output)
        self.assertIn("-37.20", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_no_warning_for_positive_balance(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertNotIn("⚠", output)
        self.assertIn("87.60", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_excludes_hidden_categories(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES, _CAT_HIDDEN])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertNotIn("Hidden Cat", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_excludes_deleted_categories(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES, _CAT_DELETED])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertNotIn("Deleted Cat", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_excludes_zero_budget_and_zero_activity(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES, _CAT_ZERO])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertNotIn("Zero Cat", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_empty_active_categories_message(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_HIDDEN, _CAT_DELETED, _CAT_ZERO])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertIn("no active categories", output)

    @patch("sys.stdout", new_callable=StringIO)
    def test_amounts_formatted_to_two_decimal_places(self, mock_stdout):
        month = BudgetMonth(month="2026-04-01", categories=[_CAT_GROCERIES])
        render_dashboard(month)
        output = mock_stdout.getvalue()

        self.assertIn("400.00", output)
        self.assertIn("-312.40", output)
        self.assertIn("87.60", output)


class TestCollectBudgetIds(unittest.TestCase):
    def test_collects_from_regular_accounts(self):
        with (
            patch("ynab.budget_dashboard.read_accounts_config") as mock_accounts,
            patch("ynab.budget_dashboard.read_tracking_accounts_config") as mock_tracking,
        ):
            mock_accounts.return_value = {
                "FI001": MagicMock(budget_id="bud-1"),
                "FI002": MagicMock(budget_id="bud-2"),
            }
            mock_tracking.return_value = {}

            result = _collect_budget_ids("dummy.toml")

        self.assertEqual(result, ["bud-1", "bud-2"])

    def test_deduplicates_budget_ids(self):
        with (
            patch("ynab.budget_dashboard.read_accounts_config") as mock_accounts,
            patch("ynab.budget_dashboard.read_tracking_accounts_config") as mock_tracking,
        ):
            mock_accounts.return_value = {
                "FI001": MagicMock(budget_id="bud-1"),
                "FI002": MagicMock(budget_id="bud-1"),
            }
            mock_tracking.return_value = {}

            result = _collect_budget_ids("dummy.toml")

        self.assertEqual(result, ["bud-1"])

    def test_collects_from_tracking_accounts(self):
        with (
            patch("ynab.budget_dashboard.read_accounts_config") as mock_accounts,
            patch("ynab.budget_dashboard.read_tracking_accounts_config") as mock_tracking,
        ):
            mock_accounts.return_value = {}
            mock_tracking.return_value = {
                "nordnet": MagicMock(budget_id="bud-3"),
            }

            result = _collect_budget_ids("dummy.toml")

        self.assertEqual(result, ["bud-3"])

    def test_skips_accounts_without_budget_id(self):
        with (
            patch("ynab.budget_dashboard.read_accounts_config") as mock_accounts,
            patch("ynab.budget_dashboard.read_tracking_accounts_config") as mock_tracking,
        ):
            mock_accounts.return_value = {
                "FI001": MagicMock(budget_id=None),
                "FI002": MagicMock(budget_id="bud-2"),
            }
            mock_tracking.return_value = {}

            result = _collect_budget_ids("dummy.toml")

        self.assertEqual(result, ["bud-2"])


class TestRunStatus(unittest.TestCase):
    def _make_service(self, month: BudgetMonth) -> MagicMock:
        svc = MagicMock()
        svc.get_budget_month.return_value = month
        return svc

    @patch("ynab.budget_dashboard.render_dashboard")
    @patch("ynab.budget_dashboard.read_credentials_file", return_value="tok")
    @patch("ynab.budget_dashboard._collect_budget_ids", return_value=["bud-1"])
    def test_calls_render_for_each_budget(self, mock_ids, mock_creds, mock_render):
        month = BudgetMonth(month="2026-04-01", categories=[])
        fake_svc = MagicMock()
        fake_svc.get_budget_month.return_value = month

        run_status(budget_service_factory=lambda token: fake_svc)

        fake_svc.get_budget_month.assert_called_once_with("bud-1")
        mock_render.assert_called_once_with(month)

    @patch("ynab.budget_dashboard._collect_budget_ids", return_value=[])
    def test_exits_when_no_budget_ids(self, _mock_ids):
        with self.assertRaises(SystemExit):
            run_status()
