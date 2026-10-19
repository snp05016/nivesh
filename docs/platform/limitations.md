---
title: Limitations
description: An honest list of what the Lab does not do, does approximately, or cannot yet verify.
---

# Limitations

<p class="nv-lede">This page lists what the Lab does not do, does only approximately, or cannot yet verify. If something here gets fixed, update this page in the same change.</p>

## Simulation fidelity

- [ ] **Daily bars only.** There is no intraday path, queue position or opening auction. Fills follow the conservative rules in [`ASSUMPTIONS`](time-machine.md#every-assumption-assumptions).
- [ ] **Delivery (CNC) only.** No intraday product, no short selling, no leverage, and **no F&O** in the simulator.
- [ ] **The participation cap uses the same day's volume.** This is mildly optimistic, because that volume was not knowable at order time.
- [ ] **Spreads are assumed** from liquidity buckets, not measured. The impact coefficient (0.7) is a default, not a calibration.
- [ ] **Circuit-locked days** are detected only when `high == low`. A partly locked day with some range can still fill.
- [ ] **Market-wide halts are not modelled.** Stop orders can still trigger in the day's range on a halt day.
- [ ] **Dividends** are credited gross on the ex-date: no TDS, no record-date eligibility. Rights issues and buybacks are not modelled.
- [ ] **DP charges** and broker-specific fees beyond flat/percentage brokerage are not charged.
- [ ] **Stamp duty before 2020-07-01** is charged on the buy side only, at a representative rate.

## Data

- [ ] **The dev dataset is survivorship-biased and pre-adjusted.** Results on it show how the Lab behaves, not findings. The Hypothesis Lab cannot return `supported` on it.
- [ ] **The curated bhavcopy panel** has to be populated before older scenarios (2008–2016) become playable.
- [ ] **No delivery data, sectors, fundamentals or earnings revisions** in the lab panel yet.
- [ ] **Point-in-time index constituents** are not available from an official source. Universes are rebuilt from trailing liquidity instead.
- [ ] **Some charge rows are UNVERIFIED** (pre-2021 exchange charges, the pre-2015 SEBI fee, pre-2020 state stamp duty, service-tax applicability). See [Costs](costs.md#effective-dated-schedule).
- [x] ~~**Charge lookup on the last day of a rate range** raised an error.~~ Fixed: `effective_to` is inclusive, and a test resolves every day from 2010. See [Costs: known gaps](costs.md#known-gaps).

## Statistics

- [ ] The Hypothesis Lab's DSR assumes normal per-period returns (\(\gamma_3 = 0, \gamma_4 = 3\)), and uses \(1/T\) as the variance of Sharpe ratios across trials.
- [ ] The DSR is only as honest as the **trials ledger**. Ideas tried outside the Lab are not counted.
- [ ] Rebalancing is non-overlapping from the first session, so results can depend on the start offset.
- [ ] A slippage of 10 bps per side is assumed for every experiment, whatever the stock's liquidity.

## Product and process

- [ ] **Legal review is pending** on the NSE data policy (§7.4 simulation clause) and on the SEBI 30-day rule. The `research_lab` flag stays off until then. See [Data](data.md#legal-position).
- [ ] **Backend tests cannot be run locally** in this environment. Backend changes have not been verified by a local test run.
- [ ] **The iOS Lab screens have been driven only against a local dev gateway**, not the real backend. See [Status](status.md#ios-verification).
- [ ] **Some scenario write-ups mention a market-wide halt** (for example January 2008). The simulator does not model halts yet, so that lesson cannot happen in the replay.
- [ ] **The mentor's LLM mode** depends on the global LLM switch, the user's consent and budget. It falls back to rules.
- [ ] **Behaviour flags are heuristics** with fixed thresholds. They are observations, not diagnoses.
