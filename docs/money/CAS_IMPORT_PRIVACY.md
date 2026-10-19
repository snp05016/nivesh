# CAS import: privacy notice and data handling

Status: draft for legal review. Do not enable `money_cas_import` before sign-off.

## Notice `cas-v1` (shown verbatim in the app)

> **What Nivesh keeps:** for each fund in your statement, its name, ISIN, units, cost value and the statement's valuation date and NAV.
>
> **What Nivesh doesn't keep:** the PDF, its password, your PAN, name, address, email, phone, folio numbers, nominee details or transactions. The file is read in memory and discarded.
>
> **Why:** to show these funds with your holdings and in your Portfolio X-ray. Imported funds are never sent to AI features.
>
> **Your control:** undo any import from "Your imports". You can download or erase your data from Settings.
>
> [ ] This statement is mine. [ ] I agree to Nivesh keeping these fund balances for these purposes.

Both boxes must be ticked before a file can be chosen. The app sends `consent_notice_version = "cas-v1"`
and `attest_own_statement = true`; the server rejects anything else (`CONSENT_REQUIRED`).

## Data flow

1. The app reads the PDF and uploads it as base64 JSON over HTTPS (`POST /api/v1/me/imports/cas/preview`). The body is read as a stream and refused above 15 MB; the decoded PDF may be at most 10 MB.
2. The bytes stay in memory. A short-lived `spawn` child process parses them with `casparser` under an address-space cap (`MONEY_CAS_PARSE_MEM_MB`, default 512) and a 30-second kill; at most two parses run at once.
3. PII is stripped inside the child. Only the normalized fund list returns to the API process.
4. The API stores that list as `preview_json` on an `import_batches` row for at most 24 hours and shows the user a preview.
5. On "Add to portfolio" the preview becomes ledger rows (one balance per fund) and `preview_json` is cleared.

Neither the PDF nor the password is written to disk, the database or the logs. Parse and password
errors are logged by exception class name only.

## What is kept and what is discarded

| Kept | Discarded in the child |
|---|---|
| Fund name, ISIN, AMFI code, fund house | Investor name, PAN, email, address, mobile |
| Closing units, valuation date, NAV, value, cost | KYC status, nominees, advisor / ARN |
| Statement period, source (CAMS/KFintech) and type | Folio numbers |
| Batch row: consent version, consent time, counts, status | Every transaction line, the PDF and its password |

## No AI processors

Imported funds are never sent to AI features. The ORM guard hides fund rows from every non-money
reader, so copilot, analysis, the morning brief and research contexts cannot see them
(`tests/test_mf_isolation.py` checks the guard and that `services/money_*.py` import no LLM client).

## Retention

- Previews (`parsing`, `previewed`, `failed`, `cancelled` batches): purged after 24 hours at the next preview.
- Committed batches and their ledger rows: until the user undoes the import or erases their account.
- A cancelled preview is kept as a terminal row so the daily quota (10 attempts per 24 hours) holds.

## Purpose limitation

Imported balances are used only to show the user's own funds with their holdings and in the X-ray,
and to value them at the AMFI NAV. They are not used for advice, ranking, marketing or model training.

## DPDP Act 2023 / Rules 2025 mapping

| Obligation | How it is met |
|---|---|
| Consent, specific and informed | Per batch, with notice version and time stored (`consent_notice_version`, `consented_at`) |
| Erasure | `erase_user` (DB-06) deletes `import_batches` and the imported ledger rows |
| Access and export | The platform privacy center export reads Core tables, which include fund rows and `import_batches` |
| Breach logging | Handled by the platform track |
| Withdrawal | "Your imports" undo removes the batch and its rows |

## Items for legal sign-off

- Whether the notice must also be offered in an Eighth Schedule language before enabling. Version 1 is English, in line with the engine's English-only decision.
- The privacy policy update: fund balances are stored; the PDF, password, PAN, contact details, folio numbers and transactions are not; funds are never sent to AI features.
- The App Store privacy label: Financial Info, linked to the user.

## Versioning

The notice text is fixed. Any change, however small, needs a new version (`cas-v2`) and a change of
`NOTICE_VERSION` in `backend/services/money_cas_import.py` and `CASNotice.version` on iOS, so that
stored consents always name the text the user actually saw.
