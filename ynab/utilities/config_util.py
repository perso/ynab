"""Credential loading utilities."""

from pathlib import Path

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
