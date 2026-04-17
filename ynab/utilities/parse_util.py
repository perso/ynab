"""Parsing utilities for Finnish bank CSV fields."""

from datetime import date, datetime
from typing import Optional

_DATE_FORMAT = "%d.%m.%Y"
_DECIMAL_SEPARATOR = ","


def parse_date(date_string: str) -> date:
    """Parse a Finnish bank date string into a date object.

    Args:
        date_string: Date in ``dd.mm.yyyy`` format.

    Returns:
        Parsed date.

    Raises:
        ValueError: If the string does not match the expected format.
    """
    try:
        return datetime.strptime(date_string, _DATE_FORMAT).date()
    except ValueError:
        raise ValueError("Invalid date format. Must be in the format 'dd.mm.yyyy'.")


def parse_required_amount(float_string: str) -> float:
    """Parse a required Finnish bank amount string into a float.

    Args:
        float_string: Amount with comma decimal separator and optional spaces.

    Returns:
        Parsed amount.

    Raises:
        ValueError: If the string is empty or cannot be parsed.
    """
    if float_string == "":
        raise ValueError("Amount field must not be empty.")
    result = parse_amount_sign_leading(float_string)
    assert result is not None
    return result


def parse_amount_sign_leading(float_string: str) -> Optional[float]:
    """Parse a Finnish bank amount string into a float.

    Args:
        float_string: Amount with comma decimal separator, optional spaces, and
            optional leading ``+``/``-`` sign. Empty string returns ``None``.

    Returns:
        Parsed amount, or ``None`` for an empty string.
    """
    if float_string == "":
        return None
    return float(float_string.replace(_DECIMAL_SEPARATOR, ".").replace(" ", ""))
