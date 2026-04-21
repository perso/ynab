"""CLI entry point for the YNAB bank import tool."""

import argparse
import logging
from importlib.resources import files

from ynab.converter import _CONFIG_DIR, convert_bank_transactions
from ynab.tracking_updater import run_tracking_update

log = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the ``ynab`` CLI.

    :returns: Configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        description="Convert Finnish bank CSV exports to YNAB import CSVs.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("init", help="set up ~/.config/ynab/ with default files and directories")

    upload = subparsers.add_parser(
        "upload",
        help="convert bank CSVs and upload transactions to YNAB",
    )
    upload.add_argument(
        "input_dir", nargs="?", default=str(_CONFIG_DIR / "input"), metavar="PATH",
        help=f"CSV file or directory of CSV files to import (default: {_CONFIG_DIR / 'input'})",
    )
    upload.add_argument(
        "--output-dir", default=str(_CONFIG_DIR / "output"), metavar="PATH",
        help=f"directory for YNAB import CSVs (default: {_CONFIG_DIR / 'output'})",
    )
    upload.add_argument(
        "--no-dedup", dest="dedup", action="store_false", default=True,
        help="skip fetching existing YNAB transactions (duplicate filtering is on by default)",
    )
    upload.add_argument(
        "--approve", action="store_true",
        help="mark uploaded transactions as approved in YNAB (skips manual approval step)",
    )
    upload.add_argument(
        "--no-reconcile", dest="reconcile", action="store_false", default=True,
        help="skip balance reconciliation check (reconciliation is on by default)",
    )
    upload.add_argument(
        "--clean", action="store_true",
        help="delete input files after successful upload (only files with valid account config are deleted)",
    )

    tracking = subparsers.add_parser(
        "tracking",
        help="manage YNAB tracking accounts (investments, mortgage, loans, etc.)",
    )
    tracking_sub = tracking.add_subparsers(dest="tracking_command")
    tracking_sub.add_parser(
        "update",
        help=(
            "interactively update balances of all configured tracking accounts "
            "and post adjustment transactions to YNAB"
        ),
    )

    return parser


def run_init() -> None:
    """Create the ``~/.config/ynab/`` directory structure and a starter ``accounts.toml``.

    Skips writing ``accounts.toml`` if it already exists.
    """
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (_CONFIG_DIR / "input").mkdir(exist_ok=True)
    (_CONFIG_DIR / "output").mkdir(exist_ok=True)

    accounts_path = _CONFIG_DIR / "accounts.toml"
    if accounts_path.exists():
        log.info("Already set up. Configuration directory: %s", _CONFIG_DIR)
        log.info("Edit %s to update your accounts.", accounts_path)
        log.info("Run: ynab upload")
    else:
        template = files("ynab.templates").joinpath("accounts.toml.example").read_text(encoding="utf-8")
        accounts_path.write_text(template)
        log.info("Configuration directory ready: %s", _CONFIG_DIR)
        log.info("Next steps:")
        log.info("  1. Edit %s", accounts_path)
        log.info("  2. Place bank export CSVs in %s", _CONFIG_DIR / "input")
        log.info("  3. Run: ynab upload")


def run_app() -> None:
    """Parse CLI arguments and dispatch to :func:`run_init` or :func:`~ynab.converter.convert_bank_transactions`."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "init":
        run_init()
    elif args.command == "upload":
        convert_bank_transactions(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            dedup_enabled=args.dedup,
            upload_enabled=True,
            approve_enabled=args.approve,
            reconcile_enabled=args.reconcile,
            clean_enabled=args.clean,
        )
    elif args.command == "tracking":
        if getattr(args, "tracking_command", None) == "update":
            run_tracking_update()
        else:
            parser.parse_args(["tracking", "--help"])
    else:
        parser.print_help()
