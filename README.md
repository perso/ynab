# YNAB

Converts Finnish bank CSV exports into YNAB-compatible import CSVs. The Finnish bank format uses `;`-delimited fields, `iso-8859-1` encoding, `dd.mm.yyyy` dates, and comma decimal separators — this tool handles all of that and outputs the `Date,Payee,Memo,Amount` format that YNAB expects. Optionally fetches existing transactions from the YNAB REST API to filter out duplicates before writing output.

**API reference:** <https://api.ynab.com>

## Quick start

1. Install dependencies:
   ```bash
   source .venv/bin/activate
   poetry install
   ```

2. Place bank export CSVs in `data/input/`. Filenames must follow the format `<account_no>_<anything>.csv`.

3. Set the account → budget mapping via environment variable (or in `.env`):
   ```
   YNAB_ACCOUNTNO_BUDGET_MAP={"FI1234567890": {"budget_name": "MyBudget"}}
   ```

4. Run the converter:
   ```bash
   python -m ynab.main
   ```
   Output CSVs are written to `data/output/`.

5. *(Optional)* Enable duplicate filtering — see **Deduplication** below.

## Deduplication

When `YNAB_DEDUP_ENABLED=true` the tool fetches transactions from the YNAB API
before writing each output file and removes any bank rows that already appear in
YNAB (whether imported previously or entered manually).

Match rule: same amount and date within ±3 days. Each YNAB transaction can match
at most one bank row (1:1 consumption).

**Configuration:**

1. Add your YNAB API token to `~/.config/ynab/credentials`.

2. Extend the account map with `budget_id` and `account_id` for each account:
   ```
   YNAB_ACCOUNTNO_BUDGET_MAP={"FI1234567890": {"budget_name": "MyBudget", "budget_id": "<uuid>", "account_id": "<uuid>"}}
   YNAB_DEDUP_ENABLED=true
   ```

On the first run the tool fetches all transactions from the bank file's earliest
date. Subsequent runs use YNAB's delta-sync mechanism (`last_knowledge_of_server`)
to fetch only changes, keeping requests well within the 200/hour rate limit.
Knowledge marks are cached at `~/.cache/ynab/server_knowledge.json`.

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
| `ynab/utilities/parse_util.py` | Date and amount parsing helpers for the Finnish CSV format |
| `ynab/utilities/fs_util.py` | `form_file_paths` — maps input files to output paths via the account map |
| `ynab/utilities/config_util.py` | `read_credentials_file`, `parse_accountno_budget_map` |
| `ynab/utilities/knowledge_cache.py` | Persists YNAB delta-sync knowledge marks to disk |
| `ynab/ynab_api/ynab_api_client.py` | `YnabApiClient` — fetches transactions from the YNAB REST API |
| `ynab/main.py` | Entry point |

## Running tests

```bash
pytest tests/
```

With coverage report:

```bash
pytest tests/ --cov=ynab --cov-report=term-missing
```

## Linting

Check for issues:

```bash
ruff check .
```

Fix auto-fixable issues:

```bash
ruff check --fix .
```