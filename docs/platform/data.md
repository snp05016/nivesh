---
title: Data & provenance
description: Data sources, point-in-time rules, survivorship and dev-dataset warnings, provenance fields and the legal position.
---

# Data & provenance

<p class="nv-lede">Where the Lab's numbers come from, what the Lab refuses to let you see, and what every response says about its own data.</p>

## Legal position

!!! danger "Read before any public launch"
    - The **NSE Data Usage & Sharing Policy, §7.4** says Market Data "shall not be provided to" platforms engaged in "virtual trading or simulation". The policy's definition of Market Data includes end-of-day and historical data. **§7.3** bars redistribution except under a signed agreement.
    - **SEBI** set a uniform **30-day lag** for price data used in education and awareness (circular dated 08-May-2026, effective **2026-07-01**). The Lab's default `LAB_MIN_DATA_AGE_DAYS = 30` follows it.
    - The research team's reading, **not legal advice**: a public simulator that shows NSE prices needs legal sign-off, both on whether an NSE Data licence is needed or even available for simulation use, and on how the 30-day rule applies.

    For these reasons the backend's `research_lab` feature flag (`FEATURE_RESEARCH_LAB`) defaults to **off**.
    Full citations: [Verified facts §3](research/verified-facts.md#3-data-sources).

## Sources

| Source | Used for | Notes |
|---|---|---|
| **Curated store** (`research.marketdata.store`, `source="store"`) | Simulations and experiments, preferred | NSE bhavcopy panel: raw exchange OHLCV, `turnover_inr`, `trades`, an adjusted index `px_idx`, and an `event` column from which corporate actions are derived. Share counts are real. Keyed by a stable `entity_id`, so a renamed company stays one instrument |
| **Dev CSV** (`source="local_csv"`) | Development and demos only | Today's Nifty 50, **pre-adjusted** prices. Every response built from it carries both warnings below |
| **NIFTY 50 index** (`store.load_index`) | Benchmark `^NSEI` | A yfinance cache of the price index. If missing, a warning is added and benchmark comparisons are unavailable |
| `india_charges.json` | [Costs](costs.md) | Every row has a source id |
| `scenarios.json` | [Scenario library](time-machine.md#scenario-library) | Every scenario has sources and a verification status |

`RESEARCH_PANEL_SOURCE` (`auto`, `store` or `local_csv`) selects the source. `auto` uses the store
when it has rows for the window, and the dev CSV otherwise.

## Point-in-time rules

1. **`PITView(asof)`** is the only way to read data in the simulator and autopsy. A request for later data raises `LookaheadError`.
2. **Decisions happen after the close**, so an order fills on a later bar at the earliest.
3. **The FDL compiler** rejects any feature known after the decision slot, and any `future` (label) field.
4. **Labels start at the next close** in the Hypothesis Lab, which adds one full session of delay.
5. **Universes are ranked by trailing liquidity** on each date (60 sessions), not taken from today's index lists.
6. **The data-age embargo:** simulations must end at least `LAB_MIN_DATA_AGE_DAYS` (default 30) before today.
7. **Unadjusted prices plus explicit events:** splits and bonuses change share counts on the ex-date. They are not hidden in a back-adjusted series.

## Survivorship and the dev dataset

!!! warning "Dev-dataset warnings (exact text in `loaders.DEV_WARNINGS`)"
    - "Development dataset: prices are pre-adjusted for corporate actions, so share counts and per-share prices differ from what traded on the exchange."
    - "Development dataset: the universe is today's Nifty 50 members, which hides companies that fell out of the index (survivorship bias)."

The consequences are written into the code:

- In the **simulator**, corporate-action events are dropped for the dev CSV, so adjusted prices are not adjusted a second time.
- In the **Hypothesis Lab**, a survivorship warning makes the Data Quality Investigator a **critical fail**. No result on this dataset can be `supported` ([why](hypothesis-lab.md#the-skeptic-panel)).
- The [experiment log](experiments/index.md) is labelled as showing how the lab *behaves*, not findings about Indian markets.

## Provenance fields

Every simulator, autopsy and timeline response includes `provenance`:

| Field | Meaning |
|---|---|
| `source` | `store` or `local_csv` |
| `warnings` | Dataset caveats (dev warnings, missing benchmark) |
| `benchmark` | Description of the benchmark series, or null |
| `rows` | Panel rows loaded |
| `window` | `[first, last]` dates loaded, including the 400-day lookback before `start` |

Hypothesis reports carry the panel's `source`, `warnings`, `rows`, `first` and `last`, plus the
program **fingerprint**, the score's **lineage** (base fields used), its **warm-up** and its
**availability** slot. Fills carry the charge `sources`.

## Fields not yet available

Delivery quantities (`DELIV_QTY`, MTO), sector labels, fundamentals and earnings revisions are **not
in the lab panel yet**. The `/hypothesis/templates` response says so in `unavailable_fields_note`.
The sources that could provide some of them, and their depth and licensing, are listed in
[Verified facts §3](research/verified-facts.md#3-data-sources).
