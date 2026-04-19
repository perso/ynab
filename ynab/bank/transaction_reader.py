"""Reader for Finnish bank CSV exports.

CSV columns (semicolon-delimited, iso-8859-1 encoding):
  Päivä          – transaction date (dd.mm.yyyy)
  Kategoria      – bank-assigned category (Finnish label, unrelated to YNAB categories)
  Alaluokka      – bank-assigned subcategory
  Saaja/Maksaja  – payee / counterparty name
  Määrä          – amount (comma decimal; negative = debit)
  Saldo          – running account balance after transaction; absent for pending rows
  Tila           – execution status: "Toteutunut" (executed) or "Odottaa" (pending)
  Tarkastettu    – user convenience checkmark in the bank app: "Kyllä" (yes) or "Ei" (no)
"""

import csv
from pathlib import Path
from typing import List, Union

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.utilities.parse_util import parse_date, parse_amount_sign_leading, parse_required_amount

_ENCODING = "iso-8859-1"
_DELIMITER = ";"

# Tila column values
_TILA_TOTEUTUNUT = "Toteutunut"  # transaction has been executed / cleared by the bank
_TILA_ODOTTAA = "Odottaa"        # transaction is pending / waiting to settle

# Tarkastettu column values (user-placed checkmark in the bank app, no financial meaning)
_TARKASTETTU_KYLLA = "Kyllä"
_TARKASTETTU_EI = "Ei"


def read_transactions(file_name: Union[str, Path], header: bool = True) -> List[BankTransaction]:
    """Read transactions from a Finnish bank CSV export."""
    file_path = Path(file_name)
    transactions = []
    with open(file_path, encoding=_ENCODING, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=_DELIMITER)
        if header:
            next(reader, None)
        for row_num, row in enumerate(reader, start=2):
            if len(row) < 8:
                raise ValueError(
                    f"Expected 8 columns, got {len(row)} in row {row_num} of {file_path}"
                )
            try:
                transaction = BankTransaction(
                    date=parse_date(row[0]),
                    category=row[1].strip(),
                    sub_category=row[2].strip(),
                    payee=row[3].strip(),
                    amount=parse_required_amount(row[4]),
                    balance=parse_amount_sign_leading(row[5]),
                    status=_resolve_status(row[6], row[7]),
                )
            except ValueError as exc:
                raise ValueError(
                    f"Failed to parse row {row_num} in {file_path}: {exc}"
                ) from exc
            transactions.append(transaction)
    return transactions


def _resolve_status(tila: str, tarkastettu: str) -> TransactionStatus:
    """Derive TransactionStatus from the Tila and Tarkastettu CSV columns.

    Tarkastettu="Kyllä" is treated as RECONCILED by convention: the user
    marking a transaction as checked in the bank app signals that it has
    already been reconciled in YNAB.
    """
    if tila == _TILA_TOTEUTUNUT and tarkastettu == _TARKASTETTU_KYLLA:
        return TransactionStatus.RECONCILED
    if tila == _TILA_TOTEUTUNUT and tarkastettu == _TARKASTETTU_EI:
        return TransactionStatus.CLEARED
    # Odottaa (pending) and any unexpected value
    return TransactionStatus.PENDING
