# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a Python tool that reads bank transaction exports (Finnish bank CSV format) and converts them into YNAB-compatible CSV imports. Optionally uploads transactions directly to YNAB via the REST API, and optionally fetches existing transactions first to filter out duplicates. Also supports updating YNAB tracking accounts (investments, mortgages, loans) interactively or non-interactively.

**Data flow:**
1. `TransactionReader` reads Finnish bank CSVs (`;`-delimited, `iso-8859-1` encoded, `dd.mm.yyyy` dates, comma-decimal amounts) into `BankTransaction` named tuples
2. `filter_unchecked_transactions` drops PENDING transactions
3. `TransactionWriter` writes YNAB import CSVs (`Date,Payee,Memo,Amount`)
4. `fs_util.form_file_paths` maps input files to output files using account number → budget name mapping (filename format: `<account_no>_<anything>.csv`)

**Key domain details:**
- `BankTransaction.status` is derived from two CSV columns: Finnish "Toteutunut"/"Kyllä" → RECONCILED, "Toteutunut"/"Ei" → CLEARED, otherwise PENDING
- YNAB API amounts are in milliunits (1000 = $1.00); bank CSV amounts are plain floats
- Credentials are read from the `YNAB_ACCESS_TOKEN` env var (preferred) or `~/.config/ynab/credentials`

**Dedup flow (on by default, disable with `--no-dedup`):**
- `since_date` is derived from the earliest bank transaction date minus the effective `date_tolerance_days` (idempotent for the same input)
- `YnabBudgetService` fetches transactions and `filter_already_in_ynab` removes matching rows
- `date_tolerance_days` defaults to `DEFAULT_DATE_TOLERANCE_DAYS` (3) but can be overridden per account in `accounts.toml` (useful for credit cards with posting lag)

**Upload flow (`upload` subcommand):**
- Runs after filter/dedup; calls `YnabBudgetService.create_transactions` for each account that has `budget_id` and `account_id` configured (skips with a warning otherwise)
- `to_api_payloads` in `transaction_uploader.py` converts `BankTransaction` objects to API dicts; each gets a deterministic `import_id` = `sha256("{date}|{milliunits}|{payee}|{balance_milliunits}").hexdigest()[:36]`
- `import_id` makes repeated runs idempotent: YNAB silently skips transactions it has already seen
- Output CSVs are still written regardless of upload status
- Credentials are read once when either dedup or upload is enabled
- `--clean` deletes input files after successful upload (only files with a matching, fully-configured account entry)

**Tracking flow (`tracking` subcommand):**
- `ynab tracking update` — interactive loop: fetches current balance for each tracking account, prompts user for new value, posts an adjustment transaction
- `ynab tracking set SLUG AMOUNT` — non-interactive: sets one named tracking account to a specific balance
- Tracking accounts are configured in `[tracking_accounts.SLUG]` sections of `accounts.toml`
- `to_adjustment_payload` in `transaction_uploader.py` builds the API payload; `import_id` = `sha256("adj|{date}|{account_id}|{balance}").hexdigest()[:36]`

**Module layout:**
- `ynab/converter.py` — `convert_bank_transactions`, top-level pipeline orchestration
- `ynab/cli.py` — argument parsing (`build_parser`), `run_init`, `run_app` — CLI entry point
- `ynab/budget_service.py` — `BudgetService` protocol
- `ynab/summary.py` — `AccountSummary` dataclass, `print_summary` — per-account upload summary table
- `ynab/tracking_updater.py` — `update_tracking_accounts`, `set_tracking_account` — tracking account balance management
- `ynab/bank/` — transaction model, reader, writer, filters, duplicate filter
- `ynab/ynab_api/` — YNAB REST API client, `YnabBudgetService`, API payload conversion (`transaction_uploader.py`)
- `ynab/utilities/` — CSV/date/amount parsing, filesystem helpers, credentials and TOML config loading
- `tests/` — mirrors `ynab/` structure

## YNAB API reference

Always fetch the latest specs directly — do not rely on locally copied files.

- **API introduction & concepts** (auth, milliunits, rate limits, delta requests): `https://api.ynab.com`
- **OpenAPI spec** (all endpoints, request/response schemas): `https://api.ynab.com/papi/open_api_spec.yaml`
- **Rendered endpoint reference**: `https://api.ynab.com/v1`

## Workflow rules

After making ANY code changes, always:
1. Run `pytest tests/` and fix all failures before stopping
2. Run `ruff check .` and fix all warnings
3. Run `mypy ynab/` and fix type errors
4. Only tell me you're done after all three pass cleanly

Never present code as finished if tests are failing.
If you cannot fix a failure, stop and explain the problem
to me instead of leaving broken code.

## How to run this project
- Install deps: `poetry install`
- Activate venv: `source .venv/bin/activate`
- Run tests: `pytest tests/`
- Run single test: `pytest tests/test_filename.py::test_name`
- Run tests with coverage: `pytest tests/ --cov=ynab --cov-report=term-missing`
- Lint check: `ruff check .`
- Lint fix: `ruff check --fix .`
- Type check: `mypy ynab/`

## Critical file rules

**NEVER modify, delete, or overwrite any files in `data/input/`.**
This directory contains source data that must always be preserved.
It is read-only. You may only read from it.

All output must go to `data/output/` only.
If you are ever unsure which directory to write to, ask me first.

## Python environment

Dependencies are managed with Poetry. The virtual environment is at `.venv/`.

Activate it before running commands:
```bash
source .venv/bin/activate
```

Or prefix individual commands with `poetry run`:
```bash
poetry run pytest tests/
poetry run mypy ynab/
```

Never use bare `python`, `pytest`, `pip`, or `ruff` commands —
they may point to the wrong environment.

## Dependency management

If a module or package is missing, do NOT install it automatically.
Stop and tell me exactly what command you would run, then wait
for my approval before running it.

When I approve, add dependencies using Poetry:
- Runtime dep: `poetry add <package>`
- Dev dep: `poetry add --group dev <package>`

Never use pip to install project dependencies.
