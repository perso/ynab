"""Apply regex-based payee harmonization rules to bank transactions."""

import re
from typing import Dict, List

from ynab.bank.transaction import BankTransaction


def harmonize_payee(payee: str, rules: Dict[str, str]) -> str:
    """Return the first replacement whose pattern fully matches *payee*, or *payee* unchanged."""
    for pattern, replacement in rules.items():
        if re.fullmatch(pattern, payee):
            return replacement
    return payee


def harmonize_payees(
    transactions: List[BankTransaction],
    rules: Dict[str, str],
) -> List[BankTransaction]:
    """Apply *rules* to every transaction, storing the raw payee in ``original_payee`` when changed."""
    if not rules:
        return transactions
    result = []
    for t in transactions:
        clean = harmonize_payee(t.payee, rules)
        if clean != t.payee:
            result.append(t._replace(payee=clean, original_payee=t.payee))
        else:
            result.append(t)
    return result
