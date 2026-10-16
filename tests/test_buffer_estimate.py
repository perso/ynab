import math
import unittest
from datetime import date
from io import StringIO
from unittest.mock import MagicMock, patch

from ynab.buffer_estimate import (
    CategoryCost,
    LastResort,
    ScenarioResult,
    _bar,
    _eur,
    _period_label,
    buffer_target,
    category_costs,
    emergency_balance,
    last_resort_accounts,
    render_buffer,
    render_last_resort,
    resolve_keep,
    run_buffer,
    runway_months,
    scenario_result,
)
from ynab.utilities.config_util import BufferConfig, BufferScenario, TrackingAccountConfig
from ynab.ynab_api.ynab_api_client import BudgetMonth, CategorySummary, YnabAccount


def _cat(name, group, activity=0, budgeted=0, balance=0, hidden=False, deleted=False):
    return CategorySummary(
        name=name,
        category_group_name=group,
        budgeted=budgeted,
        activity=activity,
        balance=balance,
        hidden=hidden,
        deleted=deleted,
    )


def _month(*cats, month="2026-09-01"):
    return BudgetMonth(month=month, categories=list(cats))


def _costs_by_name(history, keep=None, emergency="Emergency Fund"):
    return {c.name: c for c in category_costs(history, keep or {}, emergency)}


class TestResolveKeep(unittest.TestCase):
    def test_defaults_to_one(self):
        self.assertEqual(resolve_keep("Bills", "Mortgage", {}), 1.0)

    def test_uses_group_ratio(self):
        self.assertEqual(resolve_keep("Hobbies", "Lego", {"Hobbies": 0.2}), 0.2)

    def test_category_beats_group(self):
        keep = {"Regular": 0.5, "Regular: Groceries": 0.85}
        self.assertEqual(resolve_keep("Regular", "Groceries", keep), 0.85)


class TestCategoryCosts(unittest.TestCase):
    def test_averages_outflow_over_all_months(self):
        history = [_month(_cat("Gifts", "Irregular", activity=-300_000)), _month()]
        self.assertEqual(_costs_by_name(history)["Gifts"].monthly_cost, 150.0)

    def test_assigned_wins_when_higher_than_spent(self):
        history = [_month(_cat("Medical", "Irregular", activity=-50_000, budgeted=250_000))]
        self.assertEqual(_costs_by_name(history)["Medical"].monthly_cost, 250.0)

    def test_spent_wins_when_higher_than_assigned(self):
        history = [_month(_cat("Groceries", "Regular", activity=-879_000, budgeted=500_000))]
        self.assertEqual(_costs_by_name(history)["Groceries"].monthly_cost, 879.0)

    def test_net_refund_category_is_dropped(self):
        history = [_month(_cat("Refunds", "Regular", activity=100_000))]
        self.assertNotIn("Refunds", _costs_by_name(history))

    def test_excludes_credit_card_and_internal_groups(self):
        history = [_month(
            _cat("Visa", "Credit Card Payments", activity=-100_000),
            _cat("Inflow: Ready to Assign", "Internal Master Category", budgeted=100_000),
        )]
        self.assertEqual(_costs_by_name(history), {})

    def test_excludes_emergency_category(self):
        history = [_month(_cat("Emergency Fund", "Savings", budgeted=500_000))]
        self.assertEqual(_costs_by_name(history), {})

    def test_excludes_hidden_and_deleted(self):
        history = [_month(
            _cat("Old", "Bills", activity=-1_000, hidden=True),
            _cat("Gone", "Bills", activity=-1_000, deleted=True),
        )]
        self.assertEqual(_costs_by_name(history), {})

    def test_applies_keep_ratio(self):
        history = [_month(_cat("Investments", "Savings", budgeted=500_000))]
        costs = _costs_by_name(history, keep={"Savings": 0.0})
        self.assertEqual(costs["Investments"].crisis_cost, 0.0)


class TestRunwayMonths(unittest.TestCase):
    def test_divides_balance_by_shortfall(self):
        self.assertEqual(runway_months(6000, need=4000, shortfall=1000, delay=0), 6.0)

    def test_income_delay_burns_full_need_first(self):
        self.assertEqual(runway_months(6000, need=4000, shortfall=1000, delay=1), 3.0)

    def test_buffer_runs_out_during_delay(self):
        self.assertEqual(runway_months(2000, need=4000, shortfall=1000, delay=1), 0.5)

    def test_infinite_when_income_covers_need(self):
        self.assertTrue(math.isinf(runway_months(6000, need=4000, shortfall=0, delay=0)))

    def test_infinite_when_nothing_is_needed(self):
        self.assertTrue(math.isinf(runway_months(0, need=0, shortfall=0, delay=1)))


class TestScenarioResult(unittest.TestCase):
    def test_required_covers_delay_and_shortfall_months(self):
        scenario = BufferScenario("unemployed", net_income=2000, months=6, income_delay_months=1)
        result = scenario_result(need=3000, scenario=scenario, balance=0)
        self.assertEqual(result.required, 3000 + 1000 * 6)

    def test_no_shortfall_when_income_exceeds_need(self):
        scenario = BufferScenario("bench", net_income=4000, months=6)
        self.assertEqual(scenario_result(3000, scenario, 0).shortfall, 0.0)


class TestBufferTarget(unittest.TestCase):
    def test_largest_scenario_wins(self):
        results = [ScenarioResult("a", 0, 0, 5000, 0), ScenarioResult("b", 0, 0, 20000, 0)]
        self.assertEqual(buffer_target(need=3000, results=results, floor_months=3), 20000)

    def test_floor_wins_when_scenarios_are_cheap(self):
        results = [ScenarioResult("bench", 0, 0, 1000, 0)]
        self.assertEqual(buffer_target(need=3000, results=results, floor_months=3), 9000)


class TestEmergencyBalance(unittest.TestCase):
    def test_returns_euros(self):
        month = _month(_cat("Emergency Fund", "Savings", balance=10_000_000))
        self.assertEqual(emergency_balance(month, "Emergency Fund"), 10_000.0)

    def test_missing_category_raises(self):
        with self.assertRaises(ValueError):
            emergency_balance(_month(), "Emergency Fund")


class TestFormatting(unittest.TestCase):
    def test_eur_groups_thousands_with_space(self):
        self.assertEqual(_eur(21940.4), "21 940")

    def test_bar_half_full(self):
        self.assertEqual(_bar(0.5), "█████░░░░░")

    def test_bar_clamps_overfunded(self):
        self.assertEqual(_bar(1.7), "██████████")

    def test_period_label_spans_years(self):
        self.assertEqual(_period_label(["2026-10-01", "2025-11-01"]), "Nov 2025–Oct 2026")


class TestRenderBuffer(unittest.TestCase):
    def _render(self, balance, results):
        costs = [CategoryCost("Mortgage", "Bills", 1450.0, 1.0)]
        with patch("sys.stdout", new_callable=StringIO) as out:
            render_buffer("Nov 2025–Oct 2026", costs, results, "Emergency Fund", balance, 9000)
        return out.getvalue()

    def test_flags_underfunded_scenario(self):
        output = self._render(1000, [ScenarioResult("unemployed", 0, 1450, 9000, 0.7)])
        self.assertIn("⚠", output)

    def test_shows_infinite_runway(self):
        output = self._render(9000, [ScenarioResult("bench", 3300, 0, 0, math.inf)])
        self.assertIn("∞", output)

    def test_shows_funding_percentage(self):
        output = self._render(4500, [ScenarioResult("bench", 3300, 0, 0, math.inf)])
        self.assertIn("50%", output)


_NORDNET = TrackingAccountConfig("Nordnet", "bud-2", "acc-1")


class TestLastResortAccounts(unittest.TestCase):
    def test_fetches_balance_in_euros(self):
        svc = MagicMock()
        svc.get_account.return_value = YnabAccount("acc-1", "Nordnet", 24_500_000)
        result = last_resort_accounts(["nordnet"], {"nordnet": _NORDNET}, svc)
        self.assertEqual(result, [LastResort("Nordnet", 24_500.0)])

    def test_uses_tracking_account_budget(self):
        svc = MagicMock()
        svc.get_account.return_value = YnabAccount("acc-1", "Nordnet", 0)
        last_resort_accounts(["nordnet"], {"nordnet": _NORDNET}, svc)
        svc.get_account.assert_called_once_with("bud-2", "acc-1")

    def test_unknown_slug_raises(self):
        with self.assertRaises(ValueError):
            last_resort_accounts(["typo"], {"nordnet": _NORDNET}, MagicMock())


class TestRenderLastResort(unittest.TestCase):
    def test_shows_balance_after_drop(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            render_last_resort([LastResort("Nordnet", 24_500.0)], market_drop=0.3)
        self.assertIn("Nordnet 24 500  (17 150 after a 30% drop)", out.getvalue())

    def test_prints_nothing_without_accounts(self):
        with patch("sys.stdout", new_callable=StringIO) as out:
            render_last_resort([], market_drop=0.3)
        self.assertEqual(out.getvalue(), "")


_CONFIG = BufferConfig(
    budget_id="bud-1",
    category="Emergency Fund",
    scenarios=[BufferScenario("unemployed", net_income=1000, months=6)],
    keep={},
    history_months=2,
)


class TestRunBuffer(unittest.TestCase):
    def _service(self):
        svc = MagicMock()
        svc.get_budget_month.side_effect = lambda budget_id, month="current": _month(
            _cat("Mortgage", "Bills", activity=-1_500_000),
            _cat("Emergency Fund", "Savings", balance=3_000_000),
        )
        return svc

    @patch("ynab.buffer_estimate.read_credentials_file", return_value="tok")
    @patch("ynab.buffer_estimate.read_buffer_config", return_value=_CONFIG)
    def test_fetches_complete_months_and_current(self, _cfg, _cred):
        svc = self._service()
        with patch("sys.stdout", new_callable=StringIO):
            run_buffer(today=date(2026, 10, 16), budget_service_factory=lambda tok: svc)
        months = [c.args[1] if len(c.args) > 1 else "current" for c in svc.get_budget_month.call_args_list]
        self.assertEqual(months, ["2026-09-01", "2026-08-01", "current"])

    @patch("ynab.buffer_estimate.read_credentials_file", return_value="tok")
    @patch("ynab.buffer_estimate.read_buffer_config", return_value=_CONFIG)
    def test_history_months_override(self, _cfg, _cred):
        svc = self._service()
        with patch("sys.stdout", new_callable=StringIO):
            run_buffer(history_months=4, today=date(2026, 10, 16), budget_service_factory=lambda tok: svc)
        self.assertEqual(svc.get_budget_month.call_count, 5)

    @patch("ynab.buffer_estimate.read_credentials_file", return_value="tok")
    @patch("ynab.buffer_estimate.read_buffer_config", return_value=_CONFIG)
    def test_prints_runway(self, _cfg, _cred):
        with patch("sys.stdout", new_callable=StringIO) as out:
            run_buffer(today=date(2026, 10, 16), budget_service_factory=lambda tok: self._service())
        self.assertIn("6.0 mo", out.getvalue())  # 3000 / (1500 - 1000)

    @patch("ynab.buffer_estimate.read_tracking_accounts_config", return_value={"nordnet": _NORDNET})
    @patch("ynab.buffer_estimate.read_credentials_file", return_value="tok")
    @patch("ynab.buffer_estimate.read_buffer_config", return_value=_CONFIG._replace(last_resort=["nordnet"]))
    def test_prints_last_resort(self, _cfg, _cred, _tracking):
        svc = self._service()
        svc.get_account.return_value = YnabAccount("acc-1", "Nordnet", 10_000_000)
        with patch("sys.stdout", new_callable=StringIO) as out:
            run_buffer(today=date(2026, 10, 16), budget_service_factory=lambda tok: svc)
        self.assertIn("Last resort  Nordnet 10 000", out.getvalue())

    @patch("ynab.buffer_estimate.read_tracking_accounts_config")
    @patch("ynab.buffer_estimate.read_credentials_file", return_value="tok")
    @patch("ynab.buffer_estimate.read_buffer_config", return_value=_CONFIG)
    def test_skips_tracking_config_without_last_resort(self, _cfg, _cred, tracking):
        with patch("sys.stdout", new_callable=StringIO):
            run_buffer(today=date(2026, 10, 16), budget_service_factory=lambda tok: self._service())
        tracking.assert_not_called()

    @patch("ynab.buffer_estimate.read_buffer_config", return_value=None)
    def test_exits_without_buffer_section(self, _cfg):
        with self.assertRaises(SystemExit):
            run_buffer()


if __name__ == "__main__":
    unittest.main()
