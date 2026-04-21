# YNAB

![CI](https://github.com/perso/ynab/actions/workflows/ci.yml/badge.svg)

Converts Finnish bank CSV exports into YNAB-compatible import CSVs. The Finnish bank format uses `;`-delimited fields, `iso-8859-1` encoding, `dd.mm.yyyy` dates, and comma decimal separators — this tool handles all of that and outputs the `Date,Payee,Memo,Amount` format that YNAB expects. Optionally uploads transactions directly to YNAB via the REST API, and optionally fetches existing transactions first to filter out duplicates.

**API reference:** <https://api.ynab.com>

## Configuration directory

All configuration and data files live under `~/.config/ynab/`:

```
~/.config/ynab/
├── accounts.toml       # account number → budget name mapping
├── credentials         # YNAB API token (one line)
├── input/              # place bank export CSVs here
└── output/             # converted YNAB import CSVs are written here
```

## Quick start

1. Install dependencies:
   ```bash
   poetry install
   ```

2. Run the init command to create the configuration directory and a starter `accounts.toml`:
   ```bash
   poetry run ynab init
   ```

3. Edit `~/.config/ynab/accounts.toml` and fill in your accounts:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   ```

4. Place bank export CSVs in `~/.config/ynab/input/`. Filenames must follow the format `<account_no>_<anything>.csv`.

5. Run the upload command:
   ```bash
   poetry run ynab upload
   ```

   Pass a path to use a different input location — either a directory or a single file:
   ```bash
   poetry run ynab upload ~/Downloads
   poetry run ynab upload ~/Downloads/FI1234567890_export.csv
   ```

   Converted CSVs are written to `~/.config/ynab/output/`. Override with `--output-dir` if needed.

6. *(Optional)* Enable direct upload to YNAB — see **Direct upload** below.

## CLI reference

```
usage: ynab <command> [options]

commands:
  init                  create ~/.config/ynab/ with directories and a starter accounts.toml
  upload [PATH]         convert bank CSVs and upload transactions to YNAB

ynab upload options:
  PATH               CSV file or directory of CSV files to import
                     (default: ~/.config/ynab/input)
  --output-dir PATH  directory for YNAB import CSVs
                     (default: ~/.config/ynab/output)
  --no-dedup         skip duplicate filtering (deduplication is on by default)
  --approve          mark uploaded transactions as approved (skips manual approval step)
  --no-reconcile     skip balance reconciliation check (reconciliation is on by default)
  --clean            delete input files after successful upload
                     (only files with a matching account config entry are deleted)
```

## Direct upload

The `upload` command POSTs transactions directly to the YNAB API after
processing, eliminating the manual CSV import step in the YNAB app.
Output CSVs are still written as before.

Each transaction is assigned a deterministic `import_id` derived from its date,
amount, payee, and running balance. YNAB uses this to silently skip duplicates
if the tool is run again with the same input, making repeated runs safe.

**Configuration:**

1. Add your YNAB API token to `~/.config/ynab/credentials`.

2. Add `budget_id` and `account_id` to each account in `accounts.toml`:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   budget_id   = "<budget-uuid>"
   account_id  = "<account-uuid>"
   ```

   Accounts missing `account_id` or `budget_id` are skipped with a warning and
   their CSV output is still written.

## Deduplication

Enabled by default. The tool fetches transactions from the YNAB API before
writing each output file and removes any bank rows that already appear in YNAB
(whether imported previously or entered manually). Pass `--no-dedup` to skip.

Match rule: same amount and date within a configurable tolerance (default ±3 days).
Each YNAB transaction can match at most one bank row (1:1 consumption). The YNAB
API is always queried from the bank file's earliest transaction date minus the
tolerance, making each run idempotent for the same input data.

**Configuration:**

1. Add your YNAB API token to `~/.config/ynab/credentials`.

2. Add `budget_id` and `account_id` to each account in `accounts.toml`:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   budget_id   = "<budget-uuid>"
   account_id  = "<account-uuid>"
   ```

**Per-account date tolerance:**

Credit cards often post transactions several days after the purchase date. Set
`date_tolerance_days` per account to widen the matching window:

```toml
[accounts.FI1234567890]
budget_name         = "Visa"
account_id          = "<account-uuid>"
date_tolerance_days = 7
```

## Authentication

The tool uses a **personal access token** stored at `~/.config/ynab/credentials`.
This is appropriate for a single-user development workstation.

For multi-user or production deployments, **OAuth 2.0** should be used instead.
YNAB supports the Authorization Code flow; see
<https://api.ynab.com/#oauth-applications> for details. Token-based auth is not
removed but OAuth support is left as future work.

## Modules

| Module | Description |
| --- | --- |
| `ynab/converter.py` | `convert_bank_transactions` — top-level pipeline orchestration |
| `ynab/cli.py` | Argument parsing (`build_parser`), `run_init`, `run_app` — CLI entry point |
| `ynab/budget_service.py` | `BudgetService` protocol (interface for the YNAB API layer) |
| `ynab/bank/transaction.py` | `BankTransaction` NamedTuple and `TransactionStatus` enum |
| `ynab/bank/transaction_reader.py` | Parses Finnish bank CSVs into `BankTransaction` lists |
| `ynab/bank/transaction_writer.py` | Writes YNAB import CSVs |
| `ynab/bank/transaction_filters.py` | `filter_unchecked_transactions` — keeps only CLEARED transactions |
| `ynab/bank/duplicate_filter.py` | `filter_already_in_ynab` — removes bank rows already present in YNAB |
| `ynab/ynab_api/transaction_uploader.py` | `to_api_payloads` — converts `BankTransaction` lists to YNAB API payloads |
| `ynab/ynab_api/ynab_api_client.py` | `YnabApiClient` — fetches and creates transactions via the YNAB REST API |
| `ynab/ynab_api/ynab_budget_service.py` | `YnabBudgetService` — `BudgetService` implementation backed by `YnabApiClient` |
| `ynab/utilities/parse_util.py` | Date and amount parsing helpers for the Finnish CSV format |
| `ynab/utilities/fs_util.py` | `form_file_paths` — maps input files to output paths via the account map |
| `ynab/utilities/config_util.py` | `read_credentials_file`, `read_accounts_config` — credentials and TOML config loading |

## Running tests

```bash
poetry run pytest tests/
```

With coverage report:

```bash
poetry run pytest tests/ --cov=ynab --cov-report=term-missing
```

## Linting

```bash
poetry run ruff check .
poetry run ruff check --fix .
```

## Type checking

```bash
poetry run mypy ynab/
```