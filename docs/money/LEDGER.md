# Money ledger

## Single writer

`portfolio_transactions` is the only source of truth for holdings. The `portfolio` table is a
read model recomputed from it by `services/ledger_service.py`; nothing else writes shares or
average cost. Writes for one (user, ticker) are serialised with a Postgres advisory lock.

## Transaction types and replay

The ledger is replayed per (user, ticker) in (date, id) order, using a weighted-average position:

| Type | Effect |
|---|---|
| BUY | shares += quantity; cost += quantity x price + fees |
| SELL | cost reduced pro rata; shares -= quantity; selling more than held raises `LedgerError` |
| SPLIT | shares x ratio (cost unchanged) |
| BONUS | shares += quantity at zero cost |
| DIVIDEND | no effect on the position (kept for income and returns) |
| ADJUST | restates the position to exactly `quantity` at `price` per unit |

Automatic corporate-action SPLIT rows (notes start `auto: corporate action`) apply at most once per
(date, ratio) in the replay, so one row per group or a re-run never double-applies a split.

## Opening balances and legacy rows

A BUY whose notes start (case-insensitive) with `opening balance` or `legacy migration backfill`
stands for a holding that existed before the ledger. It is dated at the moment the user entered it,
not when they bought. Returns and tax therefore re-date it from the holding's entered purchase date
(`approximate_start`, reason `user_entered_date`); with no parsable date the holding's return is
unavailable (`start_date_unknown`) and its sales are "not computed" for tax.

A fully sold holding loses its `portfolio` row, and with it the entered purchase date, so a sold
opening-balance position cannot be dated afterwards.

## ADJUST kinds

`ledger_service.adjust_kinds` classifies each ADJUST against the running replay:

- **noop**: same shares (within 1e-6) and same per-unit cost (within 0.006), for example an edit of the target or notes. Ignored by returns and tax.
- **close**: restates to zero shares. History before it is dropped; a later BUY starts fresh.
- **restate**: a real edit. Returns restart at the edit date valued at that day's close (`since_edit`) or are unavailable; tax treats the result as one lot with an uncertain acquisition date.

An ADJUST that carries `import_batch_id` (a CAS balance) makes returns unavailable
(`imported_without_history`).

## Asset classes and the ORM guard

`asset_class` is `EQ` or `MF` on both tables. Fund tickers are ISINs. `database.py` registers a
`do_orm_execute` listener that adds `Portfolio.asset_class == 'EQ'` to every ORM SELECT unless the
statement sets `execution_options(include_mf=True)`, so every non-money reader (copilot, analysis,
red flags, exports, research symbols, harvesters, charts, admin) sees stocks only and ISINs never
reach yfinance, the research engine or an LLM. Core table selects, `text()` and bulk DELETE are not
filtered, so erasure and the privacy export still see every row.

Only these may opt in (a test enforces it): `services/ledger_service.py`, `services/money_*.py`,
`scripts/reconcile_ledger.py`, `routers/portfolio.py`, `services/portfolio_snapshot.py`. The
`services/money_*.py` modules must not import an LLM client. The raw-SQL reader
`services/ticker_matcher.py` filters `COALESCE(asset_class, 'EQ') = 'EQ'` itself.

**Where funds show in v1.** The Portfolio screen (when the app sends `X-Client-Features:
asset_class`), My position, the X-ray and "Your imports". Home, net worth, the morning brief, the
widget and every AI feature show stocks only.

## CAS balance rows

Each imported fund is one restating ADJUST per ISIN, dated at the statement end, with
`import_batch_id` set and an idempotency key `casbal:<sha256(isin|statement_to|units 3dp)[:48]>` in
`client_request_id`. Units are the statement's closing units; cost per unit is cost / units, or the
statement NAV with the flag `cost_unknown`. A later statement restates; an older one is skipped.
Undoing a batch deletes its rows and replays what is left, so the earlier restatement returns. An
undo that would leave a later SELL short is refused (`UNDO_WOULD_OVERSELL`).

Full transaction history import is phase 2 (it is what mutual-fund tax and per-fund returns need).

## multi_asset_transactions

The separate `multi_asset_transactions` table was not merged into the ledger. Its POST returns
`410 ENDPOINT_RETIRED`; one writer, one table.

## Float storage

Amounts are stored as Float (audit item DB-25 keeps it); services compute with `Decimal(str(x))`.

## reconcile_ledger.py runbook

`backend/scripts/reconcile_ledger.py` compares the ledger replay with the displayed `portfolio` row.
It reports by default and changes nothing.

1. Restore the latest production backup to a scratch database and run the script there. Review the CSV it writes (`--out` names the file).
2. Take a fresh backup of production (OPS-03).
3. Run the script on production in report mode; compare with step 1.
4. Only after reviewing, run with `--apply`.

What `--apply` does per finding:

| Finding | Fix |
|---|---|
| `row_without_ledger` | writes an opening balance through the fix-track helper |
| `ledger_without_row` | writes ADJUST(0, 0), so the user sees no holding |
| `quantity_mismatch` / `cost_mismatch` | writes an ADJUST to the displayed row |
| `duplicate_auto_split` | recomputes only: the deduplicated replay is right and the displayed row was wrong |
