"""Credential and configuration loading utilities."""

import os
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Union

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
    negative: bool = False


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
            negative=bool(cfg.get("negative", False)),
        )
    return result


def read_payee_rules(path: Union[str, Path]) -> Dict[str, str]:
    """Read payee harmonization rules from the ``[payee_rules]`` section of a TOML file.

    Returns an ordered dict of ``{regex_pattern: replacement_name}``, preserving
    TOML insertion order so first-match-wins semantics hold.  Returns an empty
    dict when the section is absent or the file does not exist (rules are optional;
    ``read_accounts_config`` is the authoritative check for file existence).

    Args:
        path: Path to the TOML config file (same file as ``read_accounts_config``).
    """
    p = Path(path)
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return {}
    return dict(data.get("payee_rules", {}))

class BufferScenario(NamedTuple):
    """An income-loss scenario: reduced net income for a number of months."""

    name: str
    net_income: float
    months: float
    income_delay_months: float = 0.0


class BufferConfig(NamedTuple):
    """Configuration for the ``ynab buffer`` emergency fund estimate."""

    budget_id: str
    category: str
    scenarios: List[BufferScenario]
    keep: Dict[str, float]
    history_months: int = 12
    floor_months: float = 3.0
    last_resort: List[str] = []
    market_drop: float = 0.3


def _parse_scenario(name: str, cfg: Dict[str, Any]) -> BufferScenario:
    for required in ("net_income", "months"):
        if required not in cfg:
            raise ValueError(f"Buffer scenario '{name}' is missing required key '{required}'")
    return BufferScenario(
        name=name,
        net_income=float(cfg["net_income"]),
        months=float(cfg["months"]),
        income_delay_months=float(cfg.get("income_delay_months", 0.0)),
    )


def _parse_keep(raw: Dict[str, Any]) -> Dict[str, float]:
    keep = {key: float(value) for key, value in raw.items()}
    for key, value in keep.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Buffer keep ratio for '{key}' must be between 0 and 1, got {value}")
    return keep


def read_buffer_config(path: Union[str, Path]) -> Optional[BufferConfig]:
    """Read the ``[buffer]`` section of a TOML file.

    Expected format::

        [buffer]
        budget_id = "ynab-budget-uuid"
        category  = "Emergency Fund"

        [buffer.keep]
        "Savings" = 0.0
        "Regular: Groceries" = 0.85

        [buffer.scenarios.unemployed]
        net_income = 2200
        months     = 6

    ``last_resort`` lists tracking account slugs shown below the target,
    valued after a ``market_drop`` (default 0.3) fall.

    Returns ``None`` when the section is absent.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If a required key is missing, no scenario is defined,
            or a keep ratio or ``market_drop`` is outside 0–1.
    """
    p = Path(path)
    try:
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Accounts config file not found at {p}")

    buffer = data.get("buffer")
    if buffer is None:
        return None
    for required in ("budget_id", "category"):
        if required not in buffer:
            raise ValueError(f"[buffer] is missing required key '{required}'")
    scenarios = [_parse_scenario(n, c) for n, c in buffer.get("scenarios", {}).items()]
    if not scenarios:
        raise ValueError("[buffer] needs at least one [buffer.scenarios.NAME] section")
    market_drop = float(buffer.get("market_drop", 0.3))
    if not 0.0 <= market_drop <= 1.0:
        raise ValueError(f"[buffer] market_drop must be between 0 and 1, got {market_drop}")
    return BufferConfig(
        budget_id=buffer["budget_id"],
        category=buffer["category"],
        scenarios=scenarios,
        keep=_parse_keep(buffer.get("keep", {})),
        history_months=int(buffer.get("history_months", 12)),
        floor_months=float(buffer.get("floor_months", 3.0)),
        last_resort=list(buffer.get("last_resort", [])),
        market_drop=market_drop,
    )
