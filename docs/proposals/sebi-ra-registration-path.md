# SEBI research analyst registration path (decision memo)

Feature 65 (I49), council verdict: Defer. Related: [billing runbook](../billing/RUNBOOK.md),
[compliance notes](../research/COMPLIANCE.md). Every regulatory or cost figure below that is not
confirmed from a primary source is tagged [verify].

Nivesh is **not** registered with SEBI as a research analyst (RA) or investment adviser. Nothing in the
app, marketing or store listing may say or imply otherwise.

## Status and owner

- Status: deferred. No code until the answer is yes; no duplicate flag is created.
- Decision owner: the founder, with counsel's written opinion.
- The switch already exists in the research engine: `RESEARCH_SEBI_RA_REG_NO` (INH plus 9 digits), unset
  by default and fail-closed. `RA_DISCLAIMER_TEXT = None` makes any registration number invalid config.

## What registration would unlock

- `RESEARCH_SEBI_RA_REG_NO` and the engine's validated-tier text;
- `cohort_frequency` and a public track record (after PaRRVA verification [verify]);
- PaRRVA eligibility [verify];
- partner and Account Aggregator conversations.

## Questions for counsel

1. Does a paid tools-only tier make the free descriptive reports "research services for consideration"?
2. Individual vs non-individual vs part-time RA, and the principal or compliance officer.
3. NISM certifications required [verify].
4. The deposit, scaled by client count [verify].
5. BASL enlistment and fees [verify].
6. Fee caps and advance-fee limits [verify].
7. Disclosures and report format.
8. Record retention [verify, 5 years assumed].
9. Grievance redressal (SCORES/ODR) and the investor charter.
10. The annual compliance audit.
11. AI-use disclosure under the 2024 amendment [verify].
12. Whether the 30-day price-data lag for education-only persons (in force since 1 Jul 2026 per the
    engine notes) covers the PRO tool outputs and any future share card.
13. The NSE data licence for derived analytics (I07).

## Cost and staffing (all [verify])

| Item | Estimate | Note |
|---|---|---|
| Counsel opinion | [verify] | one-off |
| NISM certification | [verify] | principal and analysts |
| Deposit / net worth | [verify] | scales with clients |
| BASL fees | [verify] | annual |
| Principal or compliance officer | [verify] | may be part-time |
| Annual compliance audit | [verify] | recurring |
| PaRRVA verification | [verify] | for any track record |

## If YES, in this order

1. Raise research report retention in the engine's `prune_reports` (30 days on-demand, 400 days
   universe today) to the legal period (5 years assumed [verify]). **This is a prerequisite to setting
   `RESEARCH_SEBI_RA_REG_NO`.**
2. Legal supplies `RA_DISCLAIMER_TEXT` through a reviewed PR.
3. Add a registration disclosure screen: registration number, registered name, BASL number, validity,
   principal officer contact, grievance channels, and the standard line that registration does not
   guarantee performance.
4. Set `RESEARCH_SEBI_RA_REG_NO`.
5. Enable `RESEARCH_TRACK_RECORD_PUBLIC` and cohort display only after PaRRVA verification.
6. Add a client agreement and KYC if research is charged.

## If NO

Keep the engine flags unset, keep the PRO catalog tripwire test, keep the share card unbuilt, and never
claim registration.

## Deferral triggers

Revisit when counsel says the tools tier or free reports need registration, when paid users exceed a
level the founder sets, or when a partner requires it.

## Board decision record

| Date | Attendees | Decision | Rationale | Next review |
|---|---|---|---|---|
| | | | | |
