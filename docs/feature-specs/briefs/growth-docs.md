# Feature package growth-docs: Billing runbook with the decision record, SEBI RA decision memo, B2B pilot playbook, share-card re-entry spec

Cluster: growth (Monetization, growth and bold bets); area: docs
Features covered: 38 I43 Real billing with StoreKit 2, 41 I44 Honest tiering and a working paywall funnel, 63 I45 Share card, public web pages, referrals, 65 I49 SEBI RA registration path, 66 I50 B2B research co-pilot for RAs and IAs

## Files (create or modify)
- docs/billing/RUNBOOK.md
- docs/proposals/sebi-ra-registration-path.md
- docs/proposals/b2b-research-copilot.md
- docs/proposals/share-card-reentry.md

## Dependencies
- Feature packages (integrated before you start): none
- Declared in the plan: ENG:docs-research. FIX:/ENG: items may or may not be on the tip yet: check the code; where one is missing, build against the documented interface behind the flag and report it.

## Description
Four internal docs; no code. Rules for all four:
- None may claim SEBI registration.
- Every regulatory or tax figure not confirmed from a primary source carries [verify].
- Cross-link docs/research/COMPLIANCE.md.

1. docs/billing/RUNBOOK.md (features 38 and 41).
(a) Status.
- Wave 1 has shipped:
  - mock purchase routes deleted;
  - PRO catalog = sector_rotation, technical_picks, ideas_for_profit;
  - legacy calibration dashboards admin-only;
  - valuation and risk-signal routes auth-only;
  - before launch, gates use the stored tier.
- Wave 2 (the App Store store) is not built until §f records the PRO catalog decision as 'sell the tools' and an engine Stage 3 date. If the decision is 'tools free', wave 2 is not built.
- v1 limits once wave 2 is built:
  - refunds take effect only when the revoked transaction reaches the server;
  - a pre-refund JWS keeps access for at most one paid period, and is a no-op once the refund is recorded;
  - Family Sharing and grace period are off;
  - Sandbox is accepted in production and recorded per row.
(b) BILLING_ENABLED flip checklist:
- engine Stage 3 with legacy retired (enforced in code);
- /healthz billing.effective is true;
- C1 golden path green;
- in-app account deletion live (FINSEC-03 / I06);
- the §f legal sign-offs: catalog not research for consideration; paywall and product copy; tool outputs under the 30-day lag; the I07 NSE data-licence decision;
- a TestFlight sandbox pass.
Subsection 'First IAP submission':
- Why it matters: App Review reviews a first auto-renewable subscription together with a binary whose purchase UI is reachable. Reviewers buy in Sandbox against the production server, so billing must be effective, with Sandbox allowed, during review.
- Step 1: attach the product to the version and submit both.
- Step 2: choose one option and record it in §f:
  (a) Flip BILLING_ENABLED at submission. Production users cannot buy until approval, so PRO tools stay paywalled for them. While the comp is off, nothing changes for them, because the tools are already locked. If the comp is on, the flip ends it for everyone at once, so post an in-app notice first.
  (b) Keep the flag off and submit with review notes and a TestFlight screen recording. Do this only if App Review confirms in advance that it accepts it; otherwise expect a rejection for an unreachable purchase flow.
- No code change either way.
(c) App Store Connect setup:
- agreements, banking and tax, Small Business Program;
- subscription group 'Nivesh PRO' and the product id naming;
- council price target ₹299/month, with an optional ₹2,499/year product added through APPLE_IAP_PRODUCTS;
- Family Sharing and grace period off;
- a product description that lists only the enforced tools;
- sandbox testers;
- App Review notes: a demo account; PRO is account-based, so sign in before purchase; where Restore lives.
(d) Env var table, with default and effect for each: BILLING_ENABLED, APPLE_BUNDLE_ID, APPLE_IAP_PRODUCTS, APPLE_ALLOWED_ENVIRONMENTS, APPLE_ROOT_CA_PATH, NIVESH_TERMS_URL, NIVESH_PRIVACY_URL. These come from growth-billing-be and are documented ahead of wave 2.
(e) Sandbox test script: purchase; replay; restore on a second device; sandbox refund followed by a replay of the pre-refund JWS (no-op); 409 on a second account.
(f) Decision record. The owner fills in date, decision and rationale for each item:
  1. PRO catalog: the blocking gate for wave 2 (HUMAN:pro-catalog-decision).
     - Option A (proposed): sell the three enforced tools. This deviates from the council, which prefers tools free with monthly fresh-run credits. Credits are rejected because the engine makes reports free and charging for research raises RA 'consideration' risk.
     - Option B (council): tools free. Wave 2 is not built. After the tool-output review below, a follow-up removes the three require_entitlement dependencies together with their keys; FIX:AUTH-14 makes a missing key fail at import.
  2. Beta comp (HUMAN:beta-comp-decision).
     - Default OFF: before launch, gates use the stored tier, so PRO tools are locked.
     - To turn it on: complete the tool-output review, then a reviewed PR uncomments the line in entitlement_service.entitled_tier and updates BetaPlanNotice and test_prelaunch_uses_stored_tier.
     - If it is ON, record its end date and the user communication before the flip.
  3. Engine Stage 3 date (HUMAN:engine-stage3-scheduled).
  4. The First IAP submission choice from §b.
  PRO catalog policy:
  - Only tools may be sold; stock reports are always free.
  - Each of these needs legal review of the paywall copy and of the tool outputs: adding a FEATURE_MIN_TIER key, turning on the comp, and option B.
  - The review starts with the sector rotation quadrant labels (Leading, Improving, Weakening, Lagging), which services/sector_rotation.py computes from recent prices. They can read as a sector signal under the 30-day price-data lag rule for unregistered persons.
  - After the review, update test_entitlement_policy.
  - Portfolio outcomes from the money cluster are future candidates, through the same review.
(g) Config problems after launch:
- the paywall shows 'unavailable';
- App Store entitlements keep working, and nobody gets free PRO;
- renewals are still verified, unless the problem is the root CA, bundle id, products or the legacy gate; then POST returns 503 and StoreKit retries;
- /healthz lists the problems; fix them within the paid period.
Turning BILLING_ENABLED off after launch is for emergencies only. Gates fall back to the pre-launch policy, and renewals are not verified while it is off. Subscribers then lapse at the end of their period while Apple keeps charging them. Turn the comp on first, or tell subscribers to cancel.
(h) Full-version follow-ups and their triggers:
- follow-ups: Notifications V2 webhook, App Store Server API, Family Sharing, grace period, annual SKU;
- triggers: the first refund or abuse, 100 paying subscribers, or a decision to enable sharing or grace.
If wave 2 is cancelled, delete the iOS Debug-only mock purchase code (growth-billing-ios-ui steps 2, 6 and 7) as a standalone change.
(i) How to read subscription_events to reconcile with App Store Connect reports.

2. docs/proposals/sebi-ra-registration-path.md (feature 65, Defer).
- Status and decision owner.
- What registration would unlock: engine RESEARCH_SEBI_RA_REG_NO, validated tier text, cohort_frequency, a public track record, PaRRVA eligibility [verify], partner and AA conversations.
- Numbered questions for counsel:
  - does a paid tools-only tier make the free descriptive reports 'research services for consideration';
  - individual vs non-individual vs part-time RA, and the principal or compliance officer;
  - NISM certifications;
  - the deposit scaled by client count;
  - BASL enlistment and fees;
  - fee caps and advance-fee limits [verify];
  - disclosures and report format;
  - record retention [verify, 5 years assumed];
  - grievance redressal (SCORES/ODR) and the investor charter;
  - the annual compliance audit;
  - AI-use disclosure under the 2024 amendment;
  - whether the 30-day price-data lag for education-only persons (in force since 1 Jul 2026 per the engine notes) covers the PRO tool outputs and any future share card;
  - the NSE data licence for derived analytics.
- A cost and staffing table, all [verify].
- If YES, in this order:
  1. raise research report retention in ENG prune_reports (30 days on-demand and 400 days universe today) to the legal period;
  2. legal supplies RA_DISCLAIMER_TEXT through a reviewed PR;
  3. add a registration disclosure screen: registration number, registered name, BASL number, validity, principal officer contact, grievance channels, and the standard line that registration does not guarantee performance;
  4. set RESEARCH_SEBI_RA_REG_NO;
  5. enable RESEARCH_TRACK_RECORD_PUBLIC and cohort display only after PaRRVA verification;
  6. add a client agreement and KYC if research is charged.
- If NO: keep the engine flags unset, keep the PRO catalog tripwire, keep the share card unbuilt, and never claim registration.
- A board decision record template: date, attendees, decision, rationale, next review.

3. docs/proposals/b2b-research-copilot.md (feature 66, Reject).
- Why it is rejected: a second product; licensed-data redistribution (NSE terms grant no redistribution rights); a web front end; multi-tenancy; distraction; unproven retail retention.
- What must not be built until re-entry: tenant, org and seat tables; partner API keys; a web app; bulk exports.
- A 10-question interview guide for RAs and IAs.
- Manual-pilot rules: pilot users are ordinary retail accounts; Nivesh provides tools and support, not research; no bulk data delivery.
- A pilot scorecard.
- Re-entry criteria: the I47 retail retention threshold is met, and two paid manual pilots renew.
- Groundwork a later API could reuse: the research.v1 versioned contract and the entitlement catalog.

4. docs/proposals/share-card-reentry.md (feature 63, Reject).
- Status: not built. Only the legacy 'Share as Image' export was deleted.
- Why:
  - the council verdict is Reject;
  - the 30-day price-data lag rule: education-only persons may not use price data from the preceding 30 days to name or signal securities. It has been in force since 1 Jul 2026 (engine/india-data-costs-regulation.md:146, 201). Any card that names a security with metrics computed through the latest close breaks it;
  - max drawdown is a peak-to-trough return;
  - a nivesh:// link does nothing for people without the app and cannot be tapped in WhatsApp.
- Re-entry conditions, all required:
  1. a written legal opinion on the 30-day lag for a card that names a security, or RA registration (sebi-ra-registration-path.md);
  2. no drawdown or any other return metric;
  3. the I07 data-rights decision;
  4. engine Stage 3.
  After that: a server-side flag that defaults OFF, and an https link (a universal link or the App Store URL) instead of the custom scheme.
- Design sketch to reuse:
  - allow-listed engine fact ids, rendered with the server label and display strings, for example risk.vol_pctl and risk.beta.raw computed on data at least 30 days old, with the as-of date shown;
  - the disclaimer 'Nivesh is not registered with SEBI as a research analyst or investment adviser. Educational information from public market data, not investment advice.';
  - a 1080x1350 image rendered with ImageRenderer behind ShareLink;
  - a policy test over the engine contract fixtures;
  - the ResearchCopyLexiconTests word list.
- Pages and referrals stay rejected. Re-entry needs I07, I03, I48 and a legal opinion, and rewards may only use Apple offer codes (3.1.1).

## Acceptance checks
1. The four files exist, each at most about 250 lines.
2. grep finds no 'SEBI registered' or 'SEBI-registered' claim about Nivesh.
3. Every unverified regulatory or tax figure is tagged [verify].
4. RUNBOOK.md contains:
- the exact env var names from growth-billing-be;
- the flip checklist;
- the 'First IAP submission' subsection;
- the §f decision record, with the PRO catalog decision marked as the blocking gate for wave 2 and the beta comp default OFF.
5. The SEBI memo names the prune_reports retention change as a prerequisite to setting RESEARCH_SEBI_RA_REG_NO.
6. share-card-reentry.md lists the four re-entry conditions: a legal opinion on the 30-day lag, no drawdown or other return metric, I07, engine Stage 3.

## Cluster spec
docs/feature-specs/spec_growth.md holds the reviewed spec for the whole cluster (data model, API contracts, iOS states, flags, copy, tests) and the coverage table. Read the parts for your features and files; the contract written there is binding for both the backend and the iOS package of a feature.

## Constraints (hard rules)
- Fix track and engine: the audit-fix track and the Research Engine are integrated (or integrating) on the same line. Build on their code; never re-implement what they already do. If a dependency is not in the code yet, do not stub or duplicate it: build your part against the documented interface behind the feature flag, and report it.
- Research Engine decisions win: every number is computed by validated code; DeepSeek only phrases computed facts behind the grounding validator; no buy/sell/hold, price targets or stock-level probabilities; English-only v1; legacy analysis routes are retired (410); track record and cohort display only when RESEARCH_SEBI_RA_REG_NO is set. Where a feature conflicts, the engine decision is the default and the feature sits behind a flag that is off.
- Compliance: no advice, recommendations, ratings or targets; no performance claims in marketing or share content; never claim SEBI registration; DPDP Act 2023 / Rules 2025 (consent, purpose limitation, erasure, export, breach logging); App Store rules (5.1.1 account deletion, StoreKit for digital goods, privacy manifest).
- Engineering: ORM models only in backend/models/db_models.py; schema changes only via a new Alembic revision with a RANDOM 12-hex id chained to the current single head; DB access through get_session(); thin routers, logic in services/; Lakhs/Crores; iOS colours only Theme.* tokens, stripEmoji on AI text, no GeometryReader inside ScrollView/HStack, no nested NavigationStack, ViewBuilder helpers over 5 lines become View structs; free, terms-respecting data sources only (AMFI NAV files, NSE/BSE public files, yfinance) with an honest User-Agent (contact https://github.com/snp05016/nivesh); no new third-party dependency unless the brief names one; every new surface behind a server-side feature flag (reuse the project's flag mechanism) that degrades gracefully; every feature with tests.
- Backend code cannot be executed here: static checks plus hermetic tests that are correct by construction. iOS: swiftc -parse only. ml-engine code can be executed and its tests must pass.

## Local test commands
- ml-engine: cd <your worktree>/ml-engine && PYTHONDONTWRITEBYTECODE=1 backend/venv/bin/python -m pytest -p no:cacheprovider -q <tests>
- backend: static checks only (pycheck, pyright_delta); tests hermetic and correct by construction.
- iOS: swiftc -parse only; verify every symbol you use by grepping its declaration.
