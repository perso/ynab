"""Convert BankTransaction objects to YNAB API create-transaction payloads."""

from hashlib import sha256
from typing import Any, Dict, List

from ynab.bank.duplicate_filter import to_milliunits
from ynab.bank.transaction import BankTransaction


def to_api_payload(txn: BankTransaction, account_id: str) -> Dict[str, Any]:
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
        "approved": False,
        "import_id": import_id,
    }


def to_api_payloads(txns: List[BankTransaction], account_id: str) -> List[Dict[str, Any]]:
    return [to_api_payload(t, account_id) for t in txns]
