"""Parsing utilities for Finnish bank CSV fields."""

from datetime import date, datetime
from typing import Optional

_DATE_FORMAT = "%d.%m.%Y"
_DECIMAL_SEPARATOR = ","


def parse_date(date_string: str) -> date:
    """Parse a Finnish bank date string (``dd.mm.yyyy``) into a ``date`` object."""
    try:
        return datetime.strptime(date_string, _DATE_FORMAT).date()
    except ValueError:
        raise ValueError("Invalid date format. Must be in the format 'dd.mm.yyyy'.")


def parse_required_amount(float_string: str) -> float:
    """Parse a required Finnish amount string (comma decimal) into a float; raises ValueError if empty."""
    if float_string == "":
        raise ValueError("Amount field must not be empty.")
    result = parse_amount_sign_leading(float_string)
    assert result is not None
    return result


def parse_amount_sign_leading(float_string: str) -> Optional[float]:
    """Parse a Finnish amount string (comma decimal, optional sign/spaces) into a float, or None if empty."""
    if float_string == "":
        return None
    return float(float_string.replace(_DECIMAL_SEPARATOR, ".").replace(" ", ""))
