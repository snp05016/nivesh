# Money feature flags

The money cluster ships every new surface behind a server-side flag. The server owns the truth
(`backend/core/feature_flags.py`, served by `GET /api/v1/features`, no auth); the iOS app caches
the last answer and treats an unknown or never-fetched flag as off. A flag that is off hides the
route (`404 FEATURE_DISABLED`) and the iOS row.

## How to switch a flag

1. Edit `backend/.env` on the server: `FEATURE_MONEY_<NAME>=true` (or `false`). Accepted values:
   `1`, `true`, `yes`, `on` / `0`, `false`, `no`, `off`. Anything else logs a warning and uses the default.
2. Restart the backend service. Flags are read on every call, but the restart keeps the process
   environment and `.env` in step.
3. Open the app (or wait up to 10 minutes) for the iOS cache to refresh.

## The flags

| Key | Environment variable | Default | What it shows |
|---|---|---|---|
| `money_holding_detail` | `FEATURE_MONEY_HOLDING_DETAIL` | on | "My position" page for a holding (`GET /api/v1/me/holdings/{ticker}`). Off: the old stock-report screen, except funds, which always open My position. |
| `money_xirr_card` | `FEATURE_MONEY_XIRR_CARD` | on | Portfolio and per-holding XIRR next to the same cash flows in the Nifty 50. |
| `money_journal_scoring` | `FEATURE_MONEY_JOURNAL_SCORING` | on (engine-gated) | Decision journal entries compared with the Nifty 50 over 21 and 63 sessions. Numbers appear only while the research engine mode is `on`. |
| `money_cas_import` | `FEATURE_MONEY_CAS_IMPORT` | **off** | CAMS/KFintech CAS import as fund balances, "Your imports" and undo. |
| `money_xray` | `FEATURE_MONEY_XRAY` | **off** | Portfolio X-ray across stocks and funds. |
| `money_commission_drag` | `FEATURE_MONEY_COMMISSION_DRAG` | **off** | "Regular-plan costs" card inside the X-ray. |
| `money_tax_report` | `FEATURE_MONEY_TAX_REPORT` | **off** | Financial-year capital-gains working (JSON and CSV) for listed shares. |
| `money_crisis_replay` | `FEATURE_MONEY_CRISIS_REPLAY` | **off** | COVID-2020 replay card inside the X-ray. |

## Enable and deferral conditions

Do not turn a deferred flag on until every condition for it is met.

### `money_cas_import` (verdict: Defer; the smaller "fund balances snapshot" is built)

- Audit fixes landed: AUTH-01, AUTH-02, AUTH-19, ARCH-02, SILENT-09, FINSEC-06.
- The account-erasure job (DB-06) is live, backups (OPS-03) are running, and the platform privacy-center export (I06) is live.
- `data-instruments` and `data-amfi-backend` are live (fund names, NAV and categories).
- `money-mf-isolation` has landed, and an App Store build containing `money-ios-mf-aware` is live. The backend serves fund rows only to builds that send `X-Client-Features: asset_class`.
- `money_holding_detail` is on.
- `scripts/reconcile_ledger.py` reports clean on production (see LEDGER.md).
- Legal has signed off notice `cas-v1`, its language(s) and the privacy policy, and the App Store privacy label is updated (see CAS_IMPORT_PRIVACY.md).
- The reverse-proxy body limit is 15 MB for `POST /api/v1/me/imports/cas/preview`, and the server has about 1 GB of headroom for two parse children.
- On staging, a real Detailed CAS parses under `MONEY_CAS_PARSE_MEM_MB=512` (raise the knob if valid statements fail), and the `casparser` wheel and `pypdfium2` install on the production image and CPU architecture.

### `money_xray`

The conditions of `money_cas_import`, or an explicit owner decision to show the X-ray to stock-only users.

### `money_commission_drag`

`money_cas_import` is on, `money-commission-drag` is built, `backend/data/mf_ter_large_amcs.csv` is populated from AMC/AMFI disclosures and less than 45 days old, and compliance has reviewed the copy. The card hides itself when the file is empty or stale. The file ships header-only; never invent values. AMFI's expense-ratio page has no bulk download, so the owner fills the large AMCs by hand and refreshes monthly.

### `money_tax_report`

A chartered accountant has signed off `TAX_METHODOLOGY.md` (target mid-February 2027, otherwise keep it off until FY 2027-28), `reconcile_ledger.py` is clean, and the research engine is at Stage 3 with a backfill covering 31 Jan 2018 (needed for the grandfathering price). Decide the fair-market-value policy for dual-listed shares (NSE high, or the higher of NSE and BSE).

### `money_crisis_replay`

The engine backfill covers 19 Feb to 23 Mar 2020, the engine is at Stage 3, and `money_xray` is on.

### `money_journal_scoring`

On by default, but scores appear only when `services.research.config.CONFIG.mode == 'on'` (engine Stage 3, NSE end-of-day licence confirmed). Otherwise the stats response carries `market.available = false` with a reason (`flag_off`, `engine_not_live`, `engine_unreachable`).

## I36 Family portfolios: not built, Phase 3 per council (Reject)

No flag is registered: a flag with no reader is scaffolding.

**Rejected risk.** Holding other adults' financial data under one login without their consent
breaches the data-principal rules of the DPDP Act, and managed-profile entities add bloat. Even
named groups for the user's own accounts need per-group ledger state, which would change the
(user, ticker) replay semantics and could freeze holdings whose history has mixed `group_id`.

**Groundwork that exists.** The `PortfolioGroup` model and the single default group per user.

**Constraints for any future version.**

- Own transactions only.
- No member, profile or relation entities and no identity fields for other people.
- Copy steers family members to their own accounts.
- A migration that reconciles `group_id` across the ledger must come before any per-group replay.
- Moving a transaction between groups must not create a tax event.

## Note on the commission card

The X-ray's regular-plan costs card waits for CAS import: without imported funds there is nothing
to compare. It stays hidden until `money_commission_drag` is on and the TER file is fresh.
