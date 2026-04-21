"""Filesystem helpers for mapping bank export files to YNAB import paths."""

import logging
from pathlib import Path
from typing import Dict, List, NamedTuple

log = logging.getLogger(__name__)


class FilePathMapping(NamedTuple):
    account_no: str
    input_path: str
    output_path: str


def form_file_paths(
    input_dir: str,
    output_dir: str,
    accountno_budget_map: Dict[str, str],
) -> List[FilePathMapping]:
    """Map bank export CSVs in ``input_dir`` to YNAB import paths in ``output_dir``.

    Input filenames must follow the format ``<account_no>_<suffix>.csv``.
    The output filename becomes ``<budget_name>_<suffix>.csv``.

    Args:
        input_dir: Directory containing bank export CSV files.
        output_dir: Directory for the generated YNAB import CSV files.
        accountno_budget_map: Mapping of account number to YNAB budget name.

    Returns:
        List of ``FilePathMapping`` namedtuples (account_no, input_path, output_path).
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    file_paths = []

    for csv_file in input_path.glob("*.csv"):
        parts = csv_file.stem.split("_", maxsplit=1)
        if len(parts) != 2:
            log.warning("Skipping '%s': filename does not match '<account_no>_<suffix>.csv'", csv_file.name)
            continue
        account_no, suffix = parts
        if account_no not in accountno_budget_map:
            log.warning("Skipping '%s': account number '%s' not found in accounts.toml", csv_file.name, account_no)
            continue
        budget_name = accountno_budget_map[account_no]
        output_file = output_path / f"{budget_name}_{suffix}.csv"
        file_paths.append(FilePathMapping(account_no, str(csv_file), str(output_file)))

    return file_paths
