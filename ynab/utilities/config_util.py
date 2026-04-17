"""Credential and configuration loading utilities."""

import json
from pathlib import Path
from typing import Dict, NamedTuple, Optional

_DEFAULT_CREDENTIALS = Path.home() / ".config" / "ynab" / "credentials"


def read_credentials_file(file_path: str = str(_DEFAULT_CREDENTIALS)) -> str:
    """Read the YNAB API token from a credentials file.

    Args:
        file_path: Path to the credentials file. Defaults to
            ``~/.config/ynab/credentials``.

    Returns:
        File contents as a string.

    Raises:
        FileNotFoundError: If the credentials file does not exist.
    """
    path = Path(file_path)
    try:
        return path.read_text()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Required credentials file not found at {path}"
        )


class AccountConfig(NamedTuple):
    """Per-account configuration for YNAB integration."""

    budget_name: str
    budget_id: Optional[str]
    account_id: Optional[str]


def parse_accountno_budget_map(raw: str) -> Dict[str, AccountConfig]:
    """Parse YNAB_ACCOUNTNO_BUDGET_MAP JSON into typed AccountConfig values.

    Accepts both the legacy flat shape::

        {"FI123": "BudgetName"}

    and the current nested shape::

        {"FI123": {"budget_name": "BudgetName", "budget_id": "uuid", "account_id": "uuid"}}

    Legacy entries produce ``AccountConfig`` with ``budget_id`` and ``account_id``
    set to ``None``.

    Args:
        raw: Raw JSON string.

    Returns:
        Mapping of account number to ``AccountConfig``.

    Raises:
        ValueError: If the JSON is malformed or a nested entry is missing
            ``budget_name``.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in account map: {exc}") from exc

    result: Dict[str, AccountConfig] = {}
    for account_no, value in data.items():
        if isinstance(value, str):
            result[account_no] = AccountConfig(
                budget_name=value,
                budget_id=None,
                account_id=None,
            )
        elif isinstance(value, dict):
            if "budget_name" not in value:
                raise ValueError(
                    f"Account '{account_no}' is missing required key 'budget_name'"
                )
            result[account_no] = AccountConfig(
                budget_name=value["budget_name"],
                budget_id=value.get("budget_id"),
                account_id=value.get("account_id"),
            )
        else:
            raise ValueError(
                f"Account '{account_no}' value must be a string or object, got {type(value).__name__}"
            )
    return result
