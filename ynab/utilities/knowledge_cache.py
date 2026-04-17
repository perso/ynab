"""Persistence for YNAB API server_knowledge values (delta sync support)."""

import json
from pathlib import Path
from typing import Optional

_DEFAULT_CACHE = Path.home() / ".cache" / "ynab" / "server_knowledge.json"


def _cache_key(budget_id: str, account_id: str) -> str:
    return f"{budget_id}:{account_id}"


def load_server_knowledge(
    budget_id: str,
    account_id: str,
    cache_path: Path = _DEFAULT_CACHE,
) -> Optional[int]:
    """Return the stored server_knowledge for this budget/account, or None."""
    try:
        data = json.loads(cache_path.read_text())
        value = data.get(_cache_key(budget_id, account_id))
        return int(value) if value is not None else None
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


def save_server_knowledge(
    budget_id: str,
    account_id: str,
    knowledge: int,
    cache_path: Path = _DEFAULT_CACHE,
) -> None:
    """Persist server_knowledge for this budget/account."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(cache_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[_cache_key(budget_id, account_id)] = knowledge
    cache_path.write_text(json.dumps(data))
