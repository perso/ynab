"""Bank transaction domain model."""

import datetime
from enum import Enum
from typing import NamedTuple, Optional


class TransactionStatus(Enum):
    """Status of a bank transaction as reported by the Finnish bank export."""

    CLEARED = "Cleared"
    PENDING = "Pending"
    RECONCILED = "Reconciled"


class BankTransaction(NamedTuple):
    """A single bank transaction parsed from a Finnish bank CSV export."""

    date: datetime.date
    category: str
    sub_category: str
    payee: str
    amount: float
    balance: Optional[float]
    status: TransactionStatus
