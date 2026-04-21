# Feature Ideas

Ranked by value-to-effort ratio: quick wins and correctness fixes first,
YNAB API integrations in the middle, big architectural changes last.

---

## 1. Credentials via environment variable

Support `YNAB_ACCESS_TOKEN` as an alternative to `~/.config/ynab/credentials`.

**Why first:** One-line change, zero new dependencies. Immediately enables running
the tool from cron jobs, Docker containers, and CI pipelines without writing a
credentials file to disk. Also pairs naturally with the `tracking update` command
added recently.

**Behaviour:** If the env var is set, use it. If not, fall back to the credentials
file as today. Error only if neither is present.

---

## 2. Non-interactive one-shot for tracking

```
ynab tracking set nordnet 45230.50
ynab tracking set mortgage -- -185000.00
```

**Why second:** Tiny effort — it is the same code path as `tracking update` but
skips the prompt loop. Makes tracking updates scriptable and cron-friendly,
especially once credentials come from an env var (idea #1).

**Behaviour:** Look up the account by slug, fetch its current YNAB balance, post
the adjustment. Exit non-zero if the slug is not in config.

---

## 3. Summary report

Print a concise per-account table at the end of `ynab upload`:

```
Account         Read   Pending   Deduped   Uploaded   Balance check
──────────────────────────────────────────────────────────────────
Checking          12        1         3          8     ✓  8 234.50
Visa               5        0         1          4     ✗  diff -2.30
```

**Why third:** No new API calls, just aggregation of data already in memory.
High motivational value — you see the full picture in one glance instead of
parsing log lines.

---

## 4. Budget dashboard

A new `ynab status` command that calls `GET /budgets/{id}/months/current` and
renders a spending summary for the current month:

```
Category                 Budgeted    Spent    Remaining
────────────────────────────────────────────────────────
Groceries                  400.00   -312.40       87.60
Dining out                 150.00   -187.20      ⚠ -37.20
Transport                  100.00    -44.00       56.00
```

**Why fourth:** One read-only API call surfaces the information most useful for
day-to-day budget decisions. Overspent categories are flagged immediately without
opening the YNAB web app.

**Scope:** Read-only. Budget ID(s) read from `accounts.toml` as usual. Could
filter to a configurable list of categories to avoid a wall of text.

---

## 5. Goal progress after tracking update

After `ynab tracking update` posts balance adjustments, fetch
`GET /budgets/{id}/months/current` and read `goal_percentage_complete` for any
categories configured with a savings goal. Print alongside the net worth summary:

```
────────────────────────────────────────
Net worth change:  +1 230.50
Emergency fund:    73% ████████░░
Holiday savings:   41% ████░░░░░░
```

**Why fifth:** Zero extra complexity — the API call can be shared with the
dashboard (idea #4). Seeing goal progress right after updating investments or
paying down a mortgage is exactly the motivational feedback that makes manual
tracking worthwhile.

**Config:** A new optional `goal_category_ids` list per tracking account, or a
separate `[goals]` section in `accounts.toml`.

---

## 6. Auto-categorize on upload

`GET /budgets/{id}/payees` returns all known payees, each with a
`last_used_category_id`. Before POSTing bank transactions, look up each payee
name against the YNAB payee list and, when a match is found, include
`category_id` in the transaction payload.

**Why sixth:** Transactions land in the right category immediately and bypass
the YNAB inbox entirely, which is the biggest remaining source of manual work
after upload. YNAB's own UI does this same lookup automatically — this brings
it to the CLI.

**Caveat:** Matching bank payee strings (often raw uppercase with codes) to YNAB
payee names requires either exact match after normalisation or fuzzy matching.
Combining with payee harmonization (idea #7) first would improve hit rate
significantly.

---

## 7. Payee harmonization

Map raw bank payee strings to clean names before writing CSVs or uploading.

```toml
[payee_rules]
"ZETTLE\\*TMI BARBER.*"  = "Barber"
"K-CITYMARKET.*"         = "K-Citymarket"
"IF VAKUUTUS.*"          = "If Vakuutus"
```

**Why seventh:** Raw Finnish bank payees are often uppercase noise with terminal
codes appended. Cleaning them up makes YNAB's own auto-categorisation much more
effective and the transaction list more readable. Also a prerequisite for
reliable auto-categorization (idea #6).

**Design questions to settle before implementing:**
- Regex match or prefix/contains? (Regex is more flexible but heavier to configure.)
- Global rules vs. per-account rules?
- Applied before or after dedup? (Probably before, so dedup sees the clean name.)
- Should the original payee be preserved in the memo?

---

## 8. Nordnet API integration

Auto-fetch the current portfolio value from Nordnet and pre-fill the answer in
`tracking update` (or set it automatically in `tracking set`).

**Why eighth:** Would remove the most tedious manual step for users with a Nordnet
account. Nordnet exposes a public API, but it requires OAuth / session token
setup, which adds non-trivial configuration and a new dependency. Worth doing
once the simpler items above are stable.

**Scope:** Read-only — just fetch the total portfolio value. Posting transactions
to Nordnet is out of scope.

---

## 9. Multiple bank format support

Allow `accounts.toml` to declare the CSV format per account:

```toml
[accounts.FI0000000000000001]
budget_name = "Checking"
format      = "danske_fi"   # default, current behaviour
```

**Why last:** The reader is tightly coupled to Danske Bank Finland's format
(8 columns, Finnish headers, `iso-8859-1`, `;` delimiter, `dd.mm.yyyy` dates,
comma decimals). Supporting other formats — OP, Nordea, S-Pankki, OmaSp — is
the biggest architectural change on this list and is only worth doing once the
tool is stable and used across multiple banks.

**Current bank:** Danske Bank Finland.
