# Share card re-entry spec

Feature 63 (I45), council verdict: Reject. See also the [SEBI path memo](sebi-ra-registration-path.md),
the [billing runbook](../billing/RUNBOOK.md) and [compliance notes](../research/COMPLIANCE.md).

## Status

Not built. Only the legacy "Share as Image" export of saved AI analyses was deleted, and
`scripts/ios_static_checks.sh` fails if it comes back. No card, public pages or referrals exist.

## Why

- The council verdict is Reject.
- The 30-day price-data lag rule: education-only persons may not use price data from the preceding 30
  days to name or signal securities. It has been in force since 1 Jul 2026 (engine/india-data-costs-regulation.md,
  lines 146 and 201) [verify]. Any card that names a security with metrics computed through the latest
  close breaks it.
- Max drawdown is a peak-to-trough return, so it is itself a return metric.
- A `nivesh://` link does nothing for people without the app and cannot be tapped in WhatsApp.

## Re-entry conditions (all four required)

1. A written legal opinion on the 30-day lag for a card that names a security, or RA registration
   ([sebi-ra-registration-path.md](sebi-ra-registration-path.md)).
2. No drawdown or any other return metric.
3. The I07 data-rights decision (exchange-data redistribution).
4. Engine Stage 3.

After that: a server-side flag that defaults OFF, and an https link (a universal link or the App Store
URL) instead of the custom scheme.

## Design sketch to reuse

- Allow-listed engine fact ids, rendered with the server label and display strings, for example
  `risk.vol_pctl` and `risk.beta.raw` computed on data at least 30 days old, with the as-of date shown.
- The disclaimer: "Nivesh is not registered with SEBI as a research analyst or investment adviser.
  Educational information from public market data, not investment advice."
- A 1080x1350 image rendered with `ImageRenderer` behind `ShareLink`.
- A policy test over the engine contract fixtures.
- The `ResearchCopyLexiconTests` word list.

## Pages and referrals

Both stay rejected. Re-entry needs I07, I03, I48 and a legal opinion. Rewards may only use Apple offer
codes (App Store guideline 3.1.1).
