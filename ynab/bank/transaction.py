"""Bank transaction domain model."""

import datetime
from enum import Enum
from typing import NamedTuple, Optional


class TransactionStatus(Enum):
    """Status of a bank transaction as reported by the Finnish bank export.

    Derived from two CSV columns: Tila (execution status) and Tarkastettu
    (user checkmark). See transaction_reader._resolve_status for the mapping.
    """

    CLEARED = "Cleared"      # Toteutunut + not checked: executed, ready to import
    PENDING = "Pending"      # Odottaa: not yet settled, excluded from import
    RECONCILED = "Reconciled"  # Toteutunut + checked: treated as already reconciled in YNAB


class BankTransaction(NamedTuple):
    """A single transaction parsed from a Finnish bank CSV export.

    ``category`` and ``sub_category`` are the bank's own Finnish labels
    (e.g. "Ruoka- ja päivittäisostokset" / "Ruokakaupat ja marketit").
    They are unrelated to YNAB categories and are not forwarded to YNAB.

    ``balance`` is the running account balance after the transaction.
    It is always present for executed (Toteutunut) transactions and always
    absent (None) for pending (Odottaa) ones.
    """

    date: datetime.date
    category: str
    sub_category: str
    payee: str
    amount: float
    balance: Optional[float]
    status: TransactionStatus
    original_payee: Optional[str] = None
