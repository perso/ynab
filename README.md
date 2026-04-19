# YNAB

![CI](https://github.com/perso/ynab/actions/workflows/ci.yml/badge.svg)

Converts Finnish bank CSV exports into YNAB-compatible import CSVs. The Finnish bank format uses `;`-delimited fields, `iso-8859-1` encoding, `dd.mm.yyyy` dates, and comma decimal separators — this tool handles all of that and outputs the `Date,Payee,Memo,Amount` format that YNAB expects. Optionally uploads transactions directly to YNAB via the REST API, and optionally fetches existing transactions first to filter out duplicates.

**API reference:** <https://api.ynab.com>

## Quick start

1. Install dependencies:
   ```bash
   poetry install
   source .venv/bin/activate
   ```

2. Place bank export CSVs in `data/input/`. Filenames must follow the format `<account_no>_<anything>.csv`.

3. Copy `accounts.toml.example` to `accounts.toml` and fill in your accounts:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   ```

4. Run the converter:
   ```bash
   poetry run python -m ynab.main
   ```
   Output CSVs are written to `data/output/`.

5. *(Optional)* Enable direct upload to YNAB — see **Direct upload** below.

6. *(Optional)* Enable duplicate filtering — see **Deduplication** below.

## Direct upload

When `YNAB_UPLOAD_ENABLED=true` the tool POSTs transactions directly to the
YNAB API after processing, eliminating the manual CSV import step in the YNAB
app. Output CSVs are still written as before.

Each transaction is assigned a deterministic `import_id` derived from its date,
amount, payee, and running balance. YNAB uses this to silently skip duplicates
if the tool is run again with the same input, making repeated runs safe.

**Configuration:**

1. Add your YNAB API token to `~/.config/ynab/credentials`.

2. Copy `.env.example` to `.env` and set:
   ```
   YNAB_UPLOAD_ENABLED=true
   ```

3. Add `budget_id` and `account_id` to each account in `accounts.toml`:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   budget_id   = "<budget-uuid>"   # optional if YNAB_BUDGET_ID is set
   account_id  = "<account-uuid>"
   ```

   Accounts missing `account_id` or a resolvable `budget_id` are skipped with
   a warning and their CSV output is still written.

> **Recommended:** enable **Deduplication** alongside direct upload. Without it,
> transactions entered manually in YNAB may be imported again because
> `import_id` only guards against re-runs of this tool, not against duplicates
> from other sources.

## Deduplication

When `YNAB_DEDUP_ENABLED=true` the tool fetches transactions from the YNAB API
before writing each output file and removes any bank rows that already appear in
YNAB (whether imported previously or entered manually).

Match rule: same amount and date within a configurable tolerance (default ±3 days).
Each YNAB transaction can match at most one bank row (1:1 consumption). The YNAB
API is always queried from the bank file's earliest transaction date minus the
tolerance, making each run idempotent for the same input data.

**Configuration:**

1. Add your YNAB API token to `~/.config/ynab/credentials`.

2. Copy `.env.example` to `.env` and set:
   ```
   YNAB_BUDGET_ID=<your-budget-uuid>
   YNAB_DEDUP_ENABLED=true
   ```

3. Add `budget_id` and `account_id` to each account in `accounts.toml`:
   ```toml
   [accounts.FI1234567890]
   budget_name = "MyBudget"
   budget_id   = "<budget-uuid>"   # optional if YNAB_BUDGET_ID is set
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
| `ynab/bank/transaction.py` | `BankTransaction` NamedTuple and `TransactionStatus` enum |
| `ynab/bank/transaction_reader.py` | `TransactionReader` — parses Finnish bank CSVs into `BankTransaction` lists |
| `ynab/bank/transaction_writer.py` | `TransactionWriter` — writes YNAB import CSVs |
| `ynab/bank/transaction_filters.py` | `filter_unchecked_transactions` — keeps only CLEARED transactions |
| `ynab/bank/duplicate_filter.py` | `filter_already_in_ynab` — removes bank rows already present in YNAB |
| `ynab/bank/transaction_uploader.py` | `to_api_payloads` — converts `BankTransaction` lists to YNAB API payloads |
| `ynab/utilities/parse_util.py` | Date and amount parsing helpers for the Finnish CSV format |
| `ynab/utilities/fs_util.py` | `form_file_paths` — maps input files to output paths via the account map |
| `ynab/utilities/config_util.py` | `read_credentials_file`, `read_accounts_config` — credentials and TOML config loading |
| `ynab/ynab_api/ynab_api_client.py` | `YnabApiClient` — fetches transactions from the YNAB REST API |
| `ynab/main.py` | Entry point |

## Running tests

```bash
poetry run pytest tests/
```

With coverage report:

```bash
poetry run pytest tests/ --cov=ynab --cov-report=term-missing
```

## Linting

Check for issues:

```bash
poetry run ruff check .
```

Fix auto-fixable issues:

```bash
poetry run ruff check --fix .
```

## Type checking

```bash
poetry run mypy ynab/
```