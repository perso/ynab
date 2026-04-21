"""Tests for the interactive tracking-account balance updater."""

import datetime
import unittest
from typing import List, Optional

from ynab.tracking_updater import update_tracking_accounts
from ynab.utilities.config_util import TrackingAccountConfig
from ynab.ynab_api.ynab_api_client import TransactionsResponse, YnabAccount

_TODAY = datetime.date(2026, 4, 21)

_CFG_NORDNET = TrackingAccountConfig("Nordnet", "budget-1", "acc-nordnet")
_CFG_MORTGAGE = TrackingAccountConfig("Mortgage", "budget-1", "acc-mortgage")

_ACCOUNT_NORDNET = YnabAccount(id="acc-nordnet", name="Nordnet", cleared_balance=44_500_000)
_ACCOUNT_MORTGAGE = YnabAccount(id="acc-mortgage", name="Mortgage", cleared_balance=-185_500_000)


class _FakeService:
    """Minimal BudgetService stand-in for tracking tests."""

    def __init__(self, accounts: dict) -> None:
        self._accounts = accounts  # account_id -> YnabAccount
        self.adjustment_calls: list = []

    def get_transactions(self, budget_id: str, since_date: datetime.date) -> TransactionsResponse:
        return TransactionsResponse(transactions=[], server_knowledge=0)

    def create_transactions(
        self,
        budget_id: str,
        account_id: str,
        transactions: list,
        approved: bool = False,
        memo_template: Optional[str] = None,
    ) -> int:
        return 0

    def create_adjustment(
        self,
        budget_id: str,
        account_id: str,
        adjustment_milliunits: int,
        new_balance_milliunits: int,
        on_date: datetime.date,
    ) -> None:
        self.adjustment_calls.append(
            (budget_id, account_id, adjustment_milliunits, new_balance_milliunits, on_date)
        )

    def get_account(self, budget_id: str, account_id: str) -> YnabAccount:
        return self._accounts[account_id]


def _prompt_returning(values: List[Optional[float]]):
    """Return a prompt_fn that yields pre-set values in order."""
    it = iter(values)

    def _fn(name: str, current: float) -> Optional[float]:
        return next(it)

    return _fn


class TestUpdateTrackingAccounts(unittest.TestCase):
    def test_posts_adjustment_when_balance_changes(self):
        svc = _FakeService({"acc-nordnet": _ACCOUNT_NORDNET})
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET],
            today=_TODAY,
            prompt_fn=_prompt_returning([45_230.50]),
        )
        self.assertEqual(len(svc.adjustment_calls), 1)
        _budget, _acc, adj, new_bal, on_date = svc.adjustment_calls[0]
        self.assertEqual(adj, 730_500)        # 45230.50 - 44500.00 = 730.50 → 730500 mu
        self.assertEqual(new_bal, 45_230_500)
        self.assertEqual(on_date, _TODAY)

    def test_skips_account_when_prompt_returns_none(self):
        svc = _FakeService({"acc-nordnet": _ACCOUNT_NORDNET})
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET],
            today=_TODAY,
            prompt_fn=_prompt_returning([None]),
        )
        self.assertEqual(svc.adjustment_calls, [])

    def test_no_adjustment_when_balance_unchanged(self):
        svc = _FakeService({"acc-nordnet": _ACCOUNT_NORDNET})
        # current balance is 44500.00 (44_500_000 mu)
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET],
            today=_TODAY,
            prompt_fn=_prompt_returning([44_500.00]),
        )
        self.assertEqual(svc.adjustment_calls, [])

    def test_multiple_accounts_all_updated(self):
        svc = _FakeService({
            "acc-nordnet": _ACCOUNT_NORDNET,
            "acc-mortgage": _ACCOUNT_MORTGAGE,
        })
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET, _CFG_MORTGAGE],
            today=_TODAY,
            prompt_fn=_prompt_returning([45_000.00, -185_000.00]),
        )
        self.assertEqual(len(svc.adjustment_calls), 2)
        # Nordnet: +500 (45000 - 44500)
        _, _, adj1, new1, _ = svc.adjustment_calls[0]
        self.assertEqual(adj1, 500_000)
        self.assertEqual(new1, 45_000_000)
        # Mortgage: +500000 mu (-185000 - -185500 = 500)
        _, _, adj2, new2, _ = svc.adjustment_calls[1]
        self.assertEqual(adj2, 500_000)
        self.assertEqual(new2, -185_000_000)

    def test_mixed_skip_and_update(self):
        svc = _FakeService({
            "acc-nordnet": _ACCOUNT_NORDNET,
            "acc-mortgage": _ACCOUNT_MORTGAGE,
        })
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET, _CFG_MORTGAGE],
            today=_TODAY,
            prompt_fn=_prompt_returning([None, -185_000.00]),
        )
        self.assertEqual(len(svc.adjustment_calls), 1)
        _, account_id, _, _, _ = svc.adjustment_calls[0]
        self.assertEqual(account_id, "acc-mortgage")

    def test_empty_config_list_posts_nothing(self):
        svc = _FakeService({})
        update_tracking_accounts(svc, [], today=_TODAY, prompt_fn=_prompt_returning([]))
        self.assertEqual(svc.adjustment_calls, [])

    def test_uses_budget_id_from_config(self):
        svc = _FakeService({"acc-nordnet": _ACCOUNT_NORDNET})
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET],
            today=_TODAY,
            prompt_fn=_prompt_returning([45_000.00]),
        )
        budget_id, _, _, _, _ = svc.adjustment_calls[0]
        self.assertEqual(budget_id, "budget-1")

    def test_negative_adjustment_for_loss(self):
        svc = _FakeService({"acc-nordnet": _ACCOUNT_NORDNET})
        # Investments dropped from 44500 to 44000
        update_tracking_accounts(
            svc,
            [_CFG_NORDNET],
            today=_TODAY,
            prompt_fn=_prompt_returning([44_000.00]),
        )
        _, _, adj, _, _ = svc.adjustment_calls[0]
        self.assertEqual(adj, -500_000)
