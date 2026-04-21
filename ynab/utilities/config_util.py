"""Credential and configuration loading utilities."""

import os
from pathlib import Path
from typing import Dict, NamedTuple, Optional, Union

try:
    import tomllib
except ImportError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]

_DEFAULT_CREDENTIALS = Path.home() / ".config" / "ynab" / "credentials"


def read_credentials_file(file_path: str = str(_DEFAULT_CREDENTIALS)) -> str:
    """Return the YNAB API token.

    Checks ``YNAB_ACCESS_TOKEN`` env var first; falls back to reading
    *file_path* (default ``~/.config/ynab/credentials``).

    Raises:
        ValueError: If neither the env var nor the credentials file is present.
    """
    token = os.environ.get("YNAB_ACCESS_TOKEN", "").strip()
    if token:
        return token

    path = Path(file_path)
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        raise ValueError(
            "YNAB credentials not found. Set the YNAB_ACCESS_TOKEN environment "
            f"variable or create the credentials file at {path}."
        )


class TrackingAccountConfig(NamedTuple):
    """Configuration for a YNAB tracking account (investment, mortgage, loan, etc.)."""

    name: str
    budget_id: str
    account_id: str


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


def read_tracking_accounts_config(path: Union[str, Path]) -> Dict[str, TrackingAccountConfig]:
    """Read tracking account configuration from a TOML file.

    Expected format::

        [tracking_accounts.nordnet]
        name       = "Nordnet Investments"
        budget_id  = "ynab-budget-uuid"
        account_id = "ynab-account-uuid"

    All three keys are required for each tracking account.

    Args:
        path: Path to the TOML config file (same file as ``read_accounts_config``).

    Returns:
        Mapping of slug to ``TrackingAccountConfig``, preserving TOML order.
        Empty dict if the ``[tracking_accounts]`` section is absent.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If any required key is missing from a tracking account entry.
    """
    p = Path(path)
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Accounts config file not found at {p}")

    tracking = data.get("tracking_accounts", {})
    result: Dict[str, TrackingAccountConfig] = {}
    for slug, cfg in tracking.items():
        for required in ("name", "budget_id", "account_id"):
            if required not in cfg:
                raise ValueError(
                    f"Tracking account '{slug}' is missing required key '{required}'"
                )
        result[slug] = TrackingAccountConfig(
            name=cfg["name"],
            budget_id=cfg["budget_id"],
            account_id=cfg["account_id"],
        )
    return result