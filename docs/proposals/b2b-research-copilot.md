# B2B research co-pilot for RAs and IAs (rejected, docs only)

Feature 66 (I50), council verdict: Reject (4 reject, 1 defer). See also the
[SEBI path memo](sebi-ra-registration-path.md), the [billing runbook](../billing/RUNBOOK.md) and
[compliance notes](../research/COMPLIANCE.md). Regulatory points are tagged [verify] where not
confirmed from a primary source.

## Why it is rejected

- It is a second product, with a different buyer, support and sales motion.
- Serving data to businesses redistributes licensed data. NSE website terms grant no redistribution
  rights, so B2B needs a licensed vendor [verify].
- It needs a web front end; the app is iOS only.
- It needs multi-tenancy (orgs, seats, keys) before retail retention is proven.
- It is a distraction from retail retention, the metric that gates everything else.

No data model and no flag exist, on purpose: a flag with no reader is scaffolding.

## What must not be built until re-entry

- tenant, org and seat tables;
- partner API keys;
- a web app;
- bulk exports;
- any research produced by Nivesh for a business client.

## Interview guide (10 questions)

1. How many clients do you serve, and how do you produce research for them today?
2. Which step takes most of your week?
3. Which data sources do you pay for, and what do they cost?
4. How do you keep records for audits and how long [verify]?
5. What would make you trust a computed number from a tool?
6. Which of Nivesh's tools would you open weekly (sector rotation, backtester, options payoff)?
7. What do you need that a retail app cannot give you?
8. Who signs off on anything you send to a client?
9. What would you pay monthly for it, and who approves the spend?
10. What would make you stop using it?

## Manual-pilot rules

- Pilot users are ordinary retail accounts.
- Nivesh provides tools and support, not research.
- No bulk data delivery and no custom data pulls.
- No claims about performance, and no registration claims.
- Written notes of each session; stop on any request that needs licensed data.

## Pilot scorecard

| Pilot | Weekly active | Tools used | Paid? | Renewed? | Blocker |
|---|---|---|---|---|---|
| | | | | | |

## Re-entry criteria

- The I47 retail retention threshold is met, and
- two paid manual pilots renew.

## Groundwork a later API could reuse

The versioned `research.v1` engine contract and the entitlement catalog (`FEATURE_MIN_TIER`).
