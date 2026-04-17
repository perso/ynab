# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a Python tool that reads bank transaction exports (Finnish bank CSV format) and converts them into YNAB-compatible CSV imports, with an optional YNAB API client for fetching existing transactions.

**Data flow:**
1. `TransactionReader` reads Finnish bank CSVs (`;`-delimited, `iso-8859-1` encoded, `dd.mm.yyyy` dates, comma-decimal amounts) into `BankTransaction` named tuples
2. `filter_unchecked_transactions` drops PENDING transactions
3. `TransactionWriter` writes YNAB import CSVs (`Date,Payee,Memo,Amount`)
4. `fs_util.form_file_paths` maps input files to output files using account number → budget name mapping (filename format: `<account_no>_<anything>.csv`)

**Key domain details:**
- `BankTransaction.status` is derived from two CSV columns: Finnish "Toteutunut"/"Kyllä" → RECONCILED, "Toteutunut"/"Ei" → CLEARED, otherwise PENDING
- YNAB API amounts are in milliunits (1000 = $1.00); bank CSV amounts are plain floats
- Credentials are read from `~/.config/ynab/credentials`

**Module layout:**
- `ynab/bank/` — transaction model, reader, writer, filters
- `ynab/ynab_api/` — YNAB REST API client (read transactions)
- `ynab/utilities/` — CSV/date/amount parsing, filesystem helpers, credentials loader
- `tests/` — mirrors `ynab/` structure

## Workflow rules

After making ANY code changes, always:
1. Run `pytest tests/` and fix all failures before stopping
2. Run `ruff check .` and fix all warnings
3. Run `mypy src/` and fix type errors
4. Only tell me you're done after all three pass cleanly

Never present code as finished if tests are failing.
If you cannot fix a failure, stop and explain the problem
to me instead of leaving broken code.

## How to run this project
- Install deps: `pip install -e ".[dev]"`
- Run tests: `pytest tests/`
- Run single test: `pytest tests/test_filename.py::test_name`
- Lint: `ruff check .`
- Type check: `mypy src/`

## Critical file rules

**NEVER modify, delete, or overwrite any files in `data/input/`.**
This directory contains source data that must always be preserved.
It is read-only. You may only read from it.

All output must go to `data/output/` only.
If you are ever unsure which directory to write to, ask me first.