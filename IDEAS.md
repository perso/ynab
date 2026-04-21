# Feature Ideas

Ranked by value-to-effort ratio: quick wins and correctness fixes first,
integrations in the middle, big architectural changes last.

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

## 4. Deduplication on payee

Use payee name as an additional match criterion when filtering bank transactions
already in YNAB.

**Why fourth:** This is a real correctness gap. Currently two transactions on the
same day for the same amount from different payees are treated as duplicates of
each other. The fix is optional and per-account (e.g. `dedup_match_payee = true`
in `accounts.toml`) because YNAB sometimes renames payees on import, which would
cause false negatives if payee matching is always on.

**Note:** The existing sort key already includes payee for determinism, so the
data is available — it just is not used in the match condition today.

**Danger:** The payee name is not guaranteed to match between bank and YNAB.

---

## 5. Payee harmonization

Map raw bank payee strings to clean names before writing CSVs or uploading.

```toml
[payee_rules]
"ZETTLE\\*TMI BARBER.*"  = "Barber"
"K-CITYMARKET.*"         = "K-Citymarket"
"IF VAKUUTUS.*"          = "If Vakuutus"
```

**Why fifth:** Raw Finnish bank payees are often uppercase noise with terminal
codes appended. Cleaning them up makes YNAB's own auto-categorisation much more
effective and the transaction list more readable.

**Design questions to settle before implementing:**
- Regex match or prefix/contains? (Regex is more flexible but heavier to configure.)
- Global rules vs. per-account rules?
- Applied before or after dedup? (Probably before, so dedup sees the clean name.)
- Should the original payee be preserved in the memo?

---

## 6. Nordnet API integration

Auto-fetch the current portfolio value from Nordnet and pre-fill the answer in
`tracking update` (or set it automatically in `tracking set`).

**Why sixth:** Would remove the most tedious manual step for users with a Nordnet
account. Nordnet exposes a public API, but it requires OAuth / session token
setup, which adds non-trivial configuration and a new dependency. Worth doing
once the simpler items above are stable.

**Scope:** Read-only — just fetch the total portfolio value. Posting transactions
to Nordnet is out of scope.

---

## 7. Multiple bank format support

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
