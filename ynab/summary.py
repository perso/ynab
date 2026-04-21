"""Per-account upload summary report."""

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger(__name__)


@dataclass
class AccountSummary:
    account_name: str
    read: int
    pending: int
    deduped: int
    uploaded: Optional[int]     # None when upload not enabled
    balance_ok: Optional[bool]  # None when reconcile not run
    balance_diff: Optional[float]
    bank_balance: Optional[float]


def print_summary(summaries: List[AccountSummary]) -> None:
    """Print a per-account table summarising the upload pipeline results."""
    if not summaries:
        return

    col_account = max(max(len(s.account_name) for s in summaries), len("Account"))

    header = (
        f"{'Account':<{col_account}}"
        f"  {'Read':>5}"
        f"  {'Pending':>7}"
        f"  {'Deduped':>7}"
        f"  {'Uploaded':>8}"
        f"  Balance check"
    )
    sep = "─" * len(header)

    log.info("")
    log.info(header)
    log.info(sep)

    for s in summaries:
        uploaded_str = "—" if s.uploaded is None else str(s.uploaded)

        if s.balance_ok is None:
            bal_col = "—"
        elif s.balance_ok:
            bank_bal = s.bank_balance if s.bank_balance is not None else 0.0
            bal_col = f"✓  {bank_bal:,.2f}"
        else:
            diff = s.balance_diff if s.balance_diff is not None else 0.0
            bal_col = f"✗  diff {diff:+.2f}"

        line = (
            f"{s.account_name:<{col_account}}"
            f"  {s.read:>5}"
            f"  {s.pending:>7}"
            f"  {s.deduped:>7}"
            f"  {uploaded_str:>8}"
            f"  {bal_col}"
        )
        log.info(line)
