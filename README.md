# YNAB

Converts Finnish bank CSV exports into YNAB-compatible import CSVs. The Finnish bank format uses `;`-delimited fields, `iso-8859-1` encoding, `dd.mm.yyyy` dates, and comma decimal separators — this tool handles all of that and outputs the `Date,Payee,Memo,Amount` format that YNAB expects. Includes an optional YNAB API client for reading existing transactions.

## Quick start

1. Install dependencies:
   ```bash
   source .venv/bin/activate
   poetry install
   ```

2. Place bank export CSVs in `data/input/`. Filenames must follow the format `<account_no>_<anything>.csv`.

3. Edit the account → budget mapping in `ynab/main.py`:
   ```python
   _ACCOUNTNO_BUDGET_MAP = {
       "111222_ABC": "AccountNameOne",
       "333444_DEF": "AccountNameTwo",
   }
   ```

4. Run the converter:
   ```bash
   python -m ynab.main
   ```
   Output CSVs are written to `data/output/`.

5. *(Optional)* To use the YNAB API client, put your API token in `~/.config/ynab/credentials` and set `_BUDGET_ID` in `ynab/main.py`.

## Modules

| Module | Description |
| --- | --- |
| `ynab/bank/transaction.py` | `BankTransaction` NamedTuple and `TransactionStatus` enum |
| `ynab/bank/transaction_reader.py` | `TransactionReader` — parses Finnish bank CSVs into `BankTransaction` lists |
| `ynab/bank/transaction_writer.py` | `TransactionWriter` — writes YNAB import CSVs |
| `ynab/bank/transaction_filters.py` | `filter_unchecked_transactions` — keeps only CLEARED transactions |
| `ynab/utilities/parse_util.py` | Date and amount parsing helpers for the Finnish CSV format |
| `ynab/utilities/fs_util.py` | `form_file_paths` — maps input files to output paths via the account map |
| `ynab/utilities/config_util.py` | `read_credentials_file` — loads the YNAB API token from disk |
| `ynab/ynab_api/ynab_api_client.py` | `YnabApiClient` — fetches transactions from the YNAB REST API |
| `ynab/main.py` | Entry point; configuration lives here |

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