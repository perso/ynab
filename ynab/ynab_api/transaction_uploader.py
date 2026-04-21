"""Convert BankTransaction objects to YNAB API create-transaction payloads."""

import datetime
from hashlib import sha256
from typing import Any, Dict, List, Optional

from ynab.bank.duplicate_filter import to_milliunits
from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.bank.transaction_writer import format_memo


def to_api_payload(
    txn: BankTransaction,
    account_id: str,
    approved: bool = False,
    memo: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert a single ``BankTransaction`` to a YNAB API create-transaction dict.

    The ``import_id`` is a deterministic SHA-256 hash of date, amount, payee,
    and (when present) running balance, truncated to 36 characters.  This makes
    repeated runs idempotent: YNAB silently skips a transaction whose
    ``import_id`` it has already seen.

    :param txn: The bank transaction to convert.
    :param account_id: YNAB account UUID to associate the transaction with.
    :param approved: Whether to mark the transaction as approved in YNAB.
    :param memo: Optional memo text to attach to the transaction in YNAB.
    :returns: A dict ready to be serialised and POSTed to the YNAB transactions API.
    """
    milliunits = to_milliunits(txn.amount)
    balance_part = f"|{to_milliunits(txn.balance)}" if txn.balance is not None else ""
    import_id = sha256(
        f"{txn.date.isoformat()}|{milliunits}|{txn.payee}{balance_part}".encode()
    ).hexdigest()[:36]
    cleared = "reconciled" if txn.status == TransactionStatus.RECONCILED else "cleared"
    payload: Dict[str, Any] = {
        "account_id": account_id,
        "date": txn.date.isoformat(),
        "amount": milliunits,
        "payee_name": txn.payee,
        "cleared": cleared,
        "approved": approved,
        "import_id": import_id,
    }
    if memo:
        payload["memo"] = memo
    return payload


def to_api_payloads(
    txns: List[BankTransaction],
    account_id: str,
    approved: bool = False,
    memo_template: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Convert a list of ``BankTransaction`` objects to YNAB API payloads.

    :param txns: Bank transactions to convert.
    :param account_id: YNAB account UUID to associate each transaction with.
    :param approved: Whether to mark each transaction as approved in YNAB.
    :param memo_template: Optional template string for the memo field.  May
        reference ``{category}`` and ``{sub_category}`` from each transaction.
    :returns: List of dicts ready to be POSTed to the YNAB transactions API.
    """
    return [
        to_api_payload(t, account_id, approved=approved, memo=format_memo(t, memo_template))
        for t in txns
    ]


def to_adjustment_payload(
    account_id: str,
    adjustment_milliunits: int,
    new_balance_milliunits: int,
    on_date: datetime.date,
) -> Dict[str, Any]:
    """Build a YNAB API payload for a manual tracking-account balance adjustment.

    The ``import_id`` encodes the target date, account, and new balance so that
    re-running with the same inputs on the same day is idempotent — YNAB will
    silently discard the duplicate.

    :param account_id: YNAB account UUID.
    :param adjustment_milliunits: Delta to apply (new_balance - current_balance), milliunits.
    :param new_balance_milliunits: Target balance after adjustment, milliunits.
    :param on_date: Date to record for the transaction.
    :returns: Dict ready to be POSTed to the YNAB transactions API.
    """
    import_id = sha256(
        f"adj|{on_date.isoformat()}|{account_id}|{new_balance_milliunits}".encode()
    ).hexdigest()[:36]
    return {
        "account_id": account_id,
        "date": on_date.isoformat(),
        "amount": adjustment_milliunits,
        "payee_name": "Manual Balance Update",
        "memo": "Updated via ynab CLI",
        "cleared": "reconciled",
        "approved": True,
        "import_id": import_id,
    }
