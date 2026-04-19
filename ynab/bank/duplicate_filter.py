"""Filter bank transactions that already exist in YNAB."""

import logging
from datetime import date, datetime, timedelta
from typing import Iterable, List, Protocol

from ynab.bank.transaction import BankTransaction


class _YnabTransactionLike(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def date(self) -> str: ...
    @property
    def amount(self) -> int: ...
    @property
    def cleared(self) -> str: ...
    @property
    def account_id(self) -> str: ...
    @property
    def deleted(self) -> bool: ...

log = logging.getLogger(__name__)

DEFAULT_DATE_TOLERANCE_DAYS = 3

_YNAB_CLEARED_STATUSES = {"cleared", "reconciled"}


def to_milliunits(amount: float) -> int:
    """Convert a bank-side float amount to YNAB milliunits (1000 = 1.00)."""
    return int(round(amount * 1000))


def filter_already_in_ynab(
    bank_transactions: List[BankTransaction],
    ynab_transactions: Iterable[_YnabTransactionLike],
    account_id: str,
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
) -> List[BankTransaction]:
    """Return bank transactions not already present in YNAB.

    Match rule: same amount (milliunits, exact) and |date delta| <= tolerance.
    Scope: only YNAB transactions with matching account_id, not deleted, and
    cleared status in {"cleared", "reconciled"}.
    Consumption: each YNAB transaction matches at most one bank transaction.
    Determinism: bank transactions are processed in (date, amount, payee) order;
    ties broken by YNAB date ascending then YNAB id.

    Note: the YNAB /transactions endpoint returns parent transactions only
    (no subtransactions). Parent amount equals the sum of its children, which
    matches the corresponding bank row amount.
    """
    # Build a pool of candidate YNAB entries indexed by milliunit amount.
    # Each bucket holds (ynab_date, ynab_id) pairs, still unconsumed.
    by_amount: dict[int, list[tuple[date, str]]] = {}
    for yt in ynab_transactions:
        if yt.account_id != account_id:
            continue
        if yt.deleted:
            continue
        if yt.cleared not in _YNAB_CLEARED_STATUSES:
            continue
        ynab_date = datetime.strptime(yt.date, "%Y-%m-%d").date()
        by_amount.setdefault(yt.amount, []).append((ynab_date, yt.id))

    kept: List[BankTransaction] = []
    for bt in sorted(bank_transactions, key=lambda t: (t.date, t.amount, t.payee)):
        amt_mu = to_milliunits(bt.amount)
        pool = by_amount.get(amt_mu, [])
        candidates = [
            (abs((ynab_date - bt.date).days), ynab_date, i)
            for i, (ynab_date, _) in enumerate(pool)
            if abs((ynab_date - bt.date).days) <= date_tolerance_days
        ]
        if not candidates:
            kept.append(bt)
        else:
            best_idx = min(candidates)[2]
            pool.pop(best_idx)

    filtered = len(bank_transactions) - len(kept)
    log.info(
        "Dedup: %d bank transaction(s) in, %d matched in YNAB, %d remaining",
        len(bank_transactions), filtered, len(kept),
    )
    return kept


def derive_since_date(transactions: List[BankTransaction], tolerance_days: int) -> date:
    """Return the earliest transaction date minus tolerance, for querying the YNAB API."""
    return min(t.date for t in transactions) - timedelta(days=tolerance_days)
