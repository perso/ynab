"""Filter bank transactions that already exist in YNAB."""

from datetime import date, datetime
from typing import Iterable, List, Optional

from ynab.bank.transaction import BankTransaction
from ynab.ynab_api.ynab_api_client import YnabTransaction

DEFAULT_DATE_TOLERANCE_DAYS = 3

_YNAB_CLEARED_STATUSES = {"cleared", "reconciled"}


def to_milliunits(amount: float) -> int:
    """Convert a bank-side float amount to YNAB milliunits (1000 = 1.00)."""
    return int(round(amount * 1000))


def filter_already_in_ynab(
    bank_transactions: List[BankTransaction],
    ynab_transactions: Iterable[YnabTransaction],
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
        best_idx: Optional[int] = None
        best_delta: Optional[int] = None
        best_ynab_date: Optional[date] = None
        for i, (ynab_date, _ynab_id) in enumerate(pool):
            delta = abs((ynab_date - bt.date).days)
            if delta > date_tolerance_days:
                continue
            if (
                best_delta is None
                or delta < best_delta
                or (delta == best_delta and best_ynab_date is not None and ynab_date < best_ynab_date)
            ):
                best_idx = i
                best_delta = delta
                best_ynab_date = ynab_date
        if best_idx is None:
            kept.append(bt)
        else:
            pool.pop(best_idx)

    return kept
