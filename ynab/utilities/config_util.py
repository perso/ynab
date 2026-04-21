"""Credential and configuration loading utilities."""

from pathlib import Path
from typing import Dict, NamedTuple, Optional, Union

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

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
        return path.read_text().strip()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Required credentials file not found at {path}"
        )


class AccountConfig(NamedTuple):
    """Per-account configuration for YNAB integration."""

    budget_name: str
    budget_id: Optional[str]
    account_id: Optional[str]
    date_tolerance_days: Optional[int] = None
    memo_template: Optional[str] = None


def read_accounts_config(path: Union[str, Path]) -> Dict[str, AccountConfig]:
    """Read account configuration from a TOML file.

    Expected format::

        [accounts.FI0000000000000001]
        budget_name = "MyAccount"
        budget_id   = "ynab-budget-uuid"
        account_id  = "ynab-account-uuid"

        [accounts.FI0000000000000002]
        budget_name = "MasterCard"

    ``budget_id`` and ``account_id`` are optional; required only when
    ``YNAB_DEDUP_ENABLED=true``.

    Args:
        path: Path to the TOML config file.

    Returns:
        Mapping of account number to ``AccountConfig``.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the TOML is malformed or ``budget_name`` is missing.
    """
    p = Path(path)
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Accounts config file not found at {p}")

    accounts = data.get("accounts", {})
    result: Dict[str, AccountConfig] = {}
    for account_no, cfg in accounts.items():
        if "budget_name" not in cfg:
            raise ValueError(
                f"Account '{account_no}' is missing required key 'budget_name'"
            )
        result[account_no] = AccountConfig(
            budget_name=cfg["budget_name"],
            budget_id=cfg.get("budget_id"),
            account_id=cfg.get("account_id"),
            date_tolerance_days=cfg.get("date_tolerance_days"),
            memo_template=cfg.get("memo_template"),
        )
    return result