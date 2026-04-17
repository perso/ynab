"""Reader for Finnish bank CSV exports."""

import csv
from pathlib import Path
from typing import List, Union

from ynab.bank.transaction import BankTransaction, TransactionStatus
from ynab.utilities.parse_util import parse_date, parse_amount_sign_leading

_ENCODING = "iso-8859-1"
_DELIMITER = ";"
_STATUS_EXECUTED = "Toteutunut"
_STATUS_YES = "Kyllä"
_STATUS_NO = "Ei"


class TransactionReader:
    def __init__(self, file_name: Union[str, Path], header: bool = True):
        self.file_name = Path(file_name)
        self.header = header

    def read_transactions(self) -> List[BankTransaction]:
        """Read transactions from the associated CSV file.

        Returns:
            Parsed list of ``BankTransaction`` objects.

        Raises:
            ValueError: If a row contains an unparseable date or amount.
        """
        transactions = []

        with open(self.file_name, encoding=_ENCODING, newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=_DELIMITER)
            if self.header:
                next(reader, None)
            for row_num, row in enumerate(reader, start=2):
                try:
                    transaction = BankTransaction(
                        date=parse_date(row[0]),
                        category=row[1].strip(),
                        sub_category=row[2].strip(),
                        payee=row[3].strip(),
                        amount=parse_amount_sign_leading(row[4]),
                        balance=parse_amount_sign_leading(row[5]),
                        status=self._resolve_status(row[6], row[7]),
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"Failed to parse row {row_num} in {self.file_name}: {exc}"
                    ) from exc
                transactions.append(transaction)

        return transactions

    @staticmethod
    def _resolve_status(status: str, check: str) -> TransactionStatus:
        """Resolve transaction status from the two Finnish bank status columns.

        Args:
            status: First status column (e.g. ``"Toteutunut"`` or ``"Odottaa"``).
            check: Second status column (``"Kyllä"`` or ``"Ei"``).

        Returns:
            Corresponding ``TransactionStatus``.
        """
        if status == _STATUS_EXECUTED and check == _STATUS_YES:
            return TransactionStatus.RECONCILED
        if status == _STATUS_EXECUTED and check == _STATUS_NO:
            return TransactionStatus.CLEARED
        return TransactionStatus.PENDING
