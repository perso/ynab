"""Orchestrates the bank CSV → YNAB conversion pipeline."""

import logging
from pathlib import Path
from typing import Callable, List, Optional

from ynab.bank.duplicate_filter import DEFAULT_DATE_TOLERANCE_DAYS, derive_since_date, filter_already_in_ynab
from ynab.bank.transaction import BankTransaction
from ynab.bank.transaction_filters import filter_unchecked_transactions
from ynab.bank.transaction_reader import read_transactions
from ynab.bank.transaction_writer import write_transactions
from ynab.budget_service import BudgetService
from ynab.summary import AccountSummary, print_summary
from ynab.utilities.config_util import read_accounts_config, read_credentials_file
from ynab.utilities.fs_util import form_file_paths
from ynab.ynab_api.ynab_api_client import TransactionsResponse
from ynab.ynab_api.ynab_budget_service import YnabBudgetService

log = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "ynab"


def convert_bank_transactions(
    source_factory: Callable[[str], List[BankTransaction]] = read_transactions,
    budget_service_factory: Callable[[str], BudgetService] = YnabBudgetService,
    input_dir: str = str(_CONFIG_DIR / "input"),
    output_dir: str = str(_CONFIG_DIR / "output"),
    dedup_enabled: bool = False,
    upload_enabled: bool = False,
    approve_enabled: bool = False,
    reconcile_enabled: bool = False,
    clean_enabled: bool = False,
    global_budget_id: Optional[str] = None,
) -> None:
    """Convert Finnish bank CSV exports to YNAB import CSVs.

    Reads all ``*.csv`` files from ``input_dir``, converts them, and writes
    YNAB import CSVs to ``output_dir``.  Input filenames must follow the
    format ``<account_no>_<suffix>.csv``.  Account configuration is always
    read from ``~/.config/ynab/accounts.toml``.

    Set ``dedup_enabled=True`` to fetch existing YNAB transactions and filter
    out bank rows that already appear in the budget.  Set ``upload_enabled=True``
    to POST transactions directly to the YNAB API.  Set ``reconcile_enabled=True``
    to compare the bank's last known balance against YNAB's cleared balance.
    All three require ``account_id`` per account in ``accounts.toml``, and a
    budget ID from either ``budget_id`` in that file or ``global_budget_id``.

    ``source_factory`` and ``budget_service_factory`` can be overridden in
    tests without modifying this function.
    """
    account_configs = read_accounts_config(str(_CONFIG_DIR / "accounts.toml"))
    need_api = dedup_enabled or upload_enabled or reconcile_enabled
    token: Optional[str] = read_credentials_file() if need_api else None
    budget_service: Optional[BudgetService] = budget_service_factory(token) if need_api else None  # type: ignore[arg-type]

    mappings = form_file_paths(
        input_dir=input_dir,
        output_dir=output_dir,
        accountno_budget_map={k: v.budget_name for k, v in account_configs.items()},
    )

    summaries: List[AccountSummary] = []

    for mapping in mappings:
        log.info("\n%s  →  %s", mapping.account_no, Path(mapping.output_path).name)
        all_transactions = source_factory(mapping.input_path)
        n_read = len(all_transactions)

        transactions_with_balance = [t for t in all_transactions if t.balance is not None]
        last_bank_balance: Optional[float] = (
            max(transactions_with_balance, key=lambda t: t.date).balance
            if transactions_with_balance else None
        )
        transactions = filter_unchecked_transactions(all_transactions)
        n_cleared = len(transactions)

        cfg = account_configs[mapping.account_no]
        effective_budget_id = cfg.budget_id or global_budget_id
        upload_config_ok = bool(effective_budget_id and cfg.account_id)

        if dedup_enabled and transactions:
            if not effective_budget_id or not cfg.account_id:
                raise ValueError(
                    f"--dedup requires complete config for account '{mapping.account_no}': "
                    f"set 'account_id' and 'budget_id' in accounts.toml."
                )
            tolerance = cfg.date_tolerance_days if cfg.date_tolerance_days is not None else DEFAULT_DATE_TOLERANCE_DAYS
            since = derive_since_date(transactions, tolerance)
            api_response: TransactionsResponse = budget_service.get_transactions(  # type: ignore[union-attr]
                effective_budget_id, since
            )
            transactions = filter_already_in_ynab(
                transactions, api_response.transactions, account_id=cfg.account_id,
                date_tolerance_days=tolerance,
            )

        transactions = sorted(set(transactions))
        n_deduped = n_cleared - len(transactions)

        write_transactions(mapping.output_path, transactions, memo_template=cfg.memo_template)

        n_uploaded: Optional[int] = None
        if upload_enabled:
            n_uploaded = 0
            if transactions:
                if not effective_budget_id or not cfg.account_id:
                    log.warning(
                        "  Upload skipped: missing account_id or budget_id in config for '%s'",
                        mapping.account_no,
                    )
                else:
                    n_uploaded = budget_service.create_transactions(  # type: ignore[union-attr]
                        effective_budget_id, cfg.account_id, transactions,
                        approved=approve_enabled, memo_template=cfg.memo_template,
                    )

        balance_ok: Optional[bool] = None
        balance_diff: Optional[float] = None
        if reconcile_enabled:
            if not effective_budget_id or not cfg.account_id:
                log.warning(
                    "  Reconciliation skipped: missing account_id or budget_id in config for '%s'",
                    mapping.account_no,
                )
            elif last_bank_balance is None:
                log.warning(
                    "  Reconciliation skipped for '%s': no balance found in bank CSV",
                    mapping.account_no,
                )
            else:
                account = budget_service.get_account(  # type: ignore[union-attr]
                    effective_budget_id, cfg.account_id
                )
                ynab_cleared = account.cleared_balance / 1000.0
                diff = last_bank_balance - ynab_cleared
                balance_ok = diff == 0
                balance_diff = diff
                status = "✓" if balance_ok else "✗"
                log.info("  Reconciliation (%s):", account.name)
                log.info("    Bank balance:  %.2f", last_bank_balance)
                log.info("    YNAB cleared:  %.2f", ynab_cleared)
                log.info("    Difference:    %.2f  %s", diff, status)

        if clean_enabled:
            if not upload_config_ok:
                log.warning(
                    "  Clean skipped: missing account_id or budget_id in config for '%s'",
                    mapping.account_no,
                )
            else:
                Path(mapping.input_path).unlink()
                log.info("  Deleted: %s", mapping.input_path)

        summaries.append(AccountSummary(
            account_name=cfg.budget_name,
            read=n_read,
            pending=n_read - n_cleared,
            deduped=n_deduped,
            uploaded=n_uploaded,
            balance_ok=balance_ok,
            balance_diff=balance_diff,
            bank_balance=last_bank_balance if balance_ok is not None else None,
        ))

    print_summary(summaries)
