# DPDP runbook

For the owner and legal. This is operating guidance, not legal advice; have it reviewed before it is relied on.

## Scope and dates

- The Digital Personal Data Protection Act, 2023, and the DPDP Rules, 2025 (G.S.R. 846(E), notified 13 Nov 2025).
- Rules 3, 5 to 16, 22 and 23 (including Rules 6, 7, 8 and 14) fall in the 18-month tranche and apply from 13 May 2027.
- MeitY has proposed shortening that window. A 12-month window would mean 13 Nov 2026. Nothing has been notified as of Oct 2026, so confirm in the Gazette before relying on either date.

## Rights handling

| Right | How it is handled |
|---|---|
| Access (s.11) | In-app: Settings, Your Data, "Prepare my data file" (`GET /api/v1/compliance/my-data`, 5 per 24 h). Manual fallback: the user emails the grievance contact and the owner runs the export for that user id. |
| Correction | Profile edit in the app. |
| Erasure | In-app delete account (FINSEC-03): a 7-day grace period, then `compliance_service.erase_user`. Consent records, audit rows and forum posts are retained without the IP address; the user row stays as a tombstone. Backups rotate out after 14 days. |
| Consent withdrawal | Toggles are enforced by the server immediately. Withdrawing `product_analytics` erases the user's usage events right away, and the daily retention job deletes any left behind. |
| Grievance | Contact: **to be filled in by the owner**. Acknowledge within **to be filled in** and resolve within **to be filled in**. The Data Protection Board is the escalation. |

## Breach response (Rule 7)

1. Detect: ops alerts (`OPS_ALERT_WEBHOOK_URL`), `job_runs`, `journalctl -u nivesh`, user reports.
2. Contain: rotate secrets, revoke tokens (bump `token_version`), disable the affected surface with its feature flag.
3. Assess: what data, how many users, since when, what the likely impact is.
4. Tell affected users without delay, in plain language, through the in-app inbox or push.
5. Tell the Data Protection Board without delay.
6. Send the Board a detailed report within 72 hours of becoming aware: nature, extent, timing, location, likely impact, causes, mitigation, findings on the responsible party, and the notices sent.

Incident log template:

```
Incident id:
Became aware (UTC/IST):
Reported by / detected by:
Systems and data involved:
Users affected (count, how identified):
Nature, extent, timing, location:
Likely impact:
Cause:
Mitigation and containment (with times):
Users notified (when, how):
Board notified without delay (when) / detailed report sent within 72 h (when):
Findings on the responsible party:
Follow-up actions and owner:
```

## Rule 8(3) retention decision

What the rule says: a fiduciary keeps personal data, associated traffic data and processing logs for at least one year from processing, for the Seventh Schedule purposes, and then erases them unless another law requires retention. Commentators read it two ways.

- **Narrow reading.** The one-year floor binds only processing for Seventh Schedule purposes (State uses, legal obligations, assessments of significant data fiduciaries). Usage events keep `USER_EVENTS_RETENTION_DAYS=180` and are erased on withdrawal. This is what is built.
- **Broad reading.** A one-year floor for all personal data and logs. Set `USER_EVENTS_RETENTION_DAYS=365`. Change `kyc_consent_service.on_consent_withdrawn` to set `event_name` to `withdrawn` (and `props` to null) instead of deleting, exclude those rows from ingestion counts, `daily_counts` and `docs/analytics/QUERIES.md`, and delete them once a year has passed.

Either way, `audit_log_entries` and access logs are kept for at least one year, including the rows of users erased under FINSEC-03. Never purge audit rows younger than one year, and keep journald and logrotate retention long enough.

Decision: reading ______ ; date ______ ; signed ______ (owner) / ______ (legal).

## Retention schedule

| Data | Kept |
|---|---|
| `user_events` | `USER_EVENTS_RETENTION_DAYS` (180 days by default); erased on withdrawal |
| `job_runs` | 90 days |
| news articles | 90 days |
| backups | 14 days |
| `audit_log_entries` and access logs | at least 1 year (Rules 6 and 8(3)) |
| `kyc_consents` | kept as consent evidence |

## Processors

Mirrors `services/privacy_export.PROCESSORS`, which is also in every data export.

| Processor | Country | Purpose | Data | Basis |
|---|---|---|---|---|
| DeepSeek | PRC | AI text for AI features, only with the AI processing consent | tickers, company names, percentage moves, chat text | consent |
| Anthropic | USA | same as DeepSeek | same as DeepSeek | consent |
| Apple Push Notification service | USA | push delivery | device token, notification text | consent |
| Operations alert relay (owner-chosen) | depends on the relay; a self-hosted relay keeps it in India | alerting the operator when a scheduled job fails | scrubbed error text only, at most 300 characters | not applicable: no personal data is intended |

Confirm with legal whether DeepSeek remains acceptable for portfolio-related prompts.
