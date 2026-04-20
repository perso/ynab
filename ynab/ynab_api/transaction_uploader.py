"""Convert BankTransaction objects to YNAB API create-transaction payloads."""

from hashlib import sha256
from typing import Any, Dict, List

from ynab.bank.duplicate_filter import to_milliunits
from ynab.bank.transaction import BankTransaction


def to_api_payload(txn: BankTransaction, account_id: str, approved: bool = False) -> Dict[str, Any]:
    """Convert a single ``BankTransaction`` to a YNAB API create-transaction dict.

    The ``import_id`` is a deterministic SHA-256 hash of date, amount, payee,
    and (when present) running balance, truncated to 36 characters.  This makes
    repeated runs idempotent: YNAB silently skips a transaction whose
    ``import_id`` it has already seen.

    :param txn: The bank transaction to convert.
    :param account_id: YNAB account UUID to associate the transaction with.
    :param approved: Whether to mark the transaction as approved in YNAB.
    :returns: A dict ready to be serialised and POSTed to the YNAB transactions API.
    """
    milliunits = to_milliunits(txn.amount)
    balance_part = f"|{to_milliunits(txn.balance)}" if txn.balance is not None else ""
    import_id = sha256(
        f"{txn.date.isoformat()}|{milliunits}|{txn.payee}{balance_part}".encode()
    ).hexdigest()[:36]
    return {
        "account_id": account_id,
        "date": txn.date.isoformat(),
        "amount": milliunits,
        "payee_name": txn.payee,
        "cleared": "cleared",
        "approved": approved,
        "import_id": import_id,
    }


def to_api_payloads(
    txns: List[BankTransaction], account_id: str, approved: bool = False
) -> List[Dict[str, Any]]:
    """Convert a list of ``BankTransaction`` objects to YNAB API payloads.

    :param txns: Bank transactions to convert.
    :param account_id: YNAB account UUID to associate each transaction with.
    :param approved: Whether to mark each transaction as approved in YNAB.
    :returns: List of dicts ready to be POSTed to the YNAB transactions API.
    """
    return [to_api_payload(t, account_id, approved=approved) for t in txns]
