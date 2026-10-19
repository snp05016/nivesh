# Verified facts: Indian cash-equity costs, market rules, data sources

*Version 2026-10-19. All sources were accessed on 2026-10-19.*

The machine-readable version of the cost schedule is `ml-engine/lab/india_charges.json`. In that file, every `*_rate` is a decimal fraction of traded value (`0.001` = 0.1%). The SEBI fee is given in rupees per crore (₹1 crore = ₹10,000,000) and is charged on each side of a trade. Date ranges are inclusive. This page is a readable summary of the same data. Where the two disagree, the JSON is the authority.

!!! info "How to read this page"
    **Verified** means the figure was read from a primary document (an NSE/SEBI circular or regulation text) or from at least two consistent broker or exchange publications. Anything labelled **UNVERIFIED** is a representative value. The simulator should flag it in output.

---

## 1. Statutory and exchange charges (NSE cash equity)

### 1.1 Securities Transaction Tax (STT)

| Effective | Delivery buy | Delivery sell | Intraday buy | Intraday sell | Source |
|---|---|---|---|---|---|
| ≤ 2012-06-30 (covered from 2010-01-01) | 0.125% | 0.125% | — | 0.025% | [CSE notice 20-Jun-2012](https://www.cse-india.com/upload/CSE%20Notices%20&%20Circulars/2012/Notice200612.htm) |
| 2012-07-01 → today | 0.1% | 0.1% | — | 0.025% | [NSE/FATAX/73524, 31-Mar-2026](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf) |

- **Finance Act 2012** cut delivery STT from 0.125% to 0.1% on each side. The cut applied from 2012-07-01. *(Wikipedia gives 2013 for this cut. That is wrong; the primary circular says 2012.)*
- **Budget 2024** raised STT on F&O only, from 2024-10-01: options went from 0.0625% to 0.1% of premium and futures from 0.0125% to 0.02%. **Cash-equity rates did not change.**
- **Budget 2026 / Finance Act 2026** (assented 2026-03-30, effective 2026-04-01) also raised F&O only: options premium to 0.15%, exercised options to 0.15%, futures to 0.05%. The NSE circular marks the cash-equity rates (delivery 0.1%/0.1%, intraday sell 0.025%) as **"No Change"**.

### 1.2 NSE exchange transaction charge (plus NSE IPFT contribution)

The JSON `rate` is the **total per-side exchange outflow**: transaction charge plus the IPFT contribution. The rate is the same for delivery and intraday.

| Effective | Txn charge (₹/lakh) | IPFT (₹/crore) | Total rate | Source |
|---|---|---|---|---|
| ≤ 2020-12-31 | 3.25 (first slab) | 0.01 | 0.00325% | Inferred from [NSE/FA/56129](https://nsearchives.nseindia.com/content/circulars/FA56129.pdf), **UNVERIFIED before 2020** |
| 2021-01-01 | 3.45 (first slab, +6%) | 0.01 | 0.00345% | [NSE/FA/56129](https://nsearchives.nseindia.com/content/circulars/FA56129.pdf); [Outlook Business](https://www.outlookbusiness.com/news/nse-to-roll-back-6-hike-in-transaction-charges-from-april-1-news-273005) |
| 2023-04-01 | 3.25 (first slab) | 10 | 0.00335% | [NSE/FA/56129](https://nsearchives.nseindia.com/content/circulars/FA56129.pdf) |
| 2024-04-01 | 3.22 | 10 | 0.00332% | [Zerodha bulletin](https://zerodha.com/marketintel/bulletin/373933/revision-in-nse-transaction-charges-from-april-1-2024), [Business Standard](https://www.business-standard.com/markets/news/nse-to-cut-cash-derivatives-transaction-charges-by-1-from-april-1-124031200766_1.html) |
| **2024-10-01** | **2.97 (flat, no slabs)** | 10 | **0.00307%** | [Zerodha bulletin](https://zerodha.com/marketintel/bulletin/391488/revision-in-transactions-charges-from-1st-october-2024), [NSE/FA/73061](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |
| **2026-03-01** | **3.0699** | **0.01** | **0.00307%** | [NSE/FA/73061, 27-Feb-2026](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf) |

- Before 2024-10-01, NSE charged **slab-wise**, based on each member's monthly turnover. The 2021–2023 slabs ran from ₹3.45 down to ₹3.20 per lakh, and 2023–2024 from ₹3.25 down to ₹3.00. Retail brokers generally passed on the first-slab rate.
- From **2024-10-01**, SEBI circular SEBI/HO/MRD/TPD-1/P/CIR/2024/92 required **uniform, non-slab** charges. NSE moved to ₹297/crore.
- From **2026-03-01**, the IPFT contribution went back to ₹0.01/crore and the transaction charge became ₹306.99/crore. The total stays at ₹307/crore, so the client cost did not change; only the split moved. This matches Zerodha's live charges page (0.00307%).

!!! warning "UNVERIFIED: NSE transaction charges 2010–2020"
    I did not find a primary NSE circular covering 2010–2020. The 0.00325% value comes from the 2023 circular, which reversed the Dec-2020 hike back to "pre-hike" levels, and from broker charge sheets that give no dates. Earlier slab revisions in 2010–2020 may exist.

### 1.3 SEBI turnover fee

| Effective | ₹ per crore | Source |
|---|---|---|
| 2010-01-01 → 2015-09-27 | 10 *(UNVERIFIED)* | — |
| 2015-09-28 | 10 | [Schedule V (2015 amendment)](https://www.taxtmi.com/tmi_blog_details?id=554987) |
| 2017-04-01 | 15 | [SEBI Payment of Fees Amendment 2017](https://taxguru.in/sebi/sebi-payment-of-fees-and-mode-of-payment-amendment-regulations-2017.html) |
| 2019-04-01 | 10 | [NSE/FA/40632 (SEBI notification 22-Mar-2019)](https://nsearchives.nseindia.com/content/circulars/FA40632.pdf) |
| 2020-06-01 → 2021-03-31 | 5 (50% COVID relief) | [NSE/FA/44514 (SEBI notification 08-May-2020)](https://nsearchives.nseindia.com/content/circulars/FA44514.pdf) |
| 2021-04-01 → today | 10 | [Zerodha charges (live)](https://zerodha.com/charges) |

!!! warning "UNVERIFIED: SEBI fee before 2015-09-28"
    The January 2017 SEBI board decision was reported as cutting broker fees "from Rs 20 to Rs 15 per crore". That conflicts with the regulation text, which gives ₹10/crore from 2015-09-28. The pre-2015 rate was not found. Either value is under 0.0002% of turnover, so the effect on backtests is small.

### 1.4 Stamp duty

| Effective | Delivery | Intraday | Side | Source |
|---|---|---|---|---|
| ≤ 2020-06-30 | ~0.01% (Maharashtra) | ~0.002–0.003% | **both sides**, set by each state | [Moneylife Dec-2019](https://mas360.moneylife.in/article/share-transfers-will-be-more-expensive-from-january-next-year/3299.html), [Zerodha](https://zerodha.com/z-connect/zerodha/announcements/uniform-stamp-duty) |
| 2020-07-01 → today | 0.015% (₹1,500/crore) | 0.003% (₹300/crore) | **buyer only** | [Zerodha](https://zerodha.com/z-connect/zerodha/announcements/uniform-stamp-duty), [Upstox](https://upstox.com/announcements/updates/revision-in-stamp-duty-rates-on-1st-july-2020/) |

- The uniform national rate came from the Indian Stamp Act 1899 as amended by Finance Act 2019. Its start was postponed from 2020-01-09 to 2020-04-01, then to **2020-07-01**. The exchanges and depositories now collect it.

!!! warning "UNVERIFIED: stamp duty before 2020-07-01"
    Before July 2020 each state set its own rate, some with per-contract-note caps. The rates were generally charged on both buy and sell. The JSON field is named `*_buy_rate`, but for this period the simulator should also apply it on the sell side. These are representative values, not a state-by-state table.

### 1.5 Service tax, then GST

| Effective | Rate | Applies to | Source |
|---|---|---|---|
| 2009-02-24 | 10.30% service tax | brokerage, exchange txn | [Wikipedia](https://en.wikipedia.org/wiki/Service_tax) |
| 2012-04-01 | 12.36% | same | same |
| 2015-06-01 | 14% | same | same |
| 2015-11-15 | 14.5% (+ Swachh Bharat Cess) | same | same |
| 2016-06-01 | 15% (+ Krishi Kalyan Cess) | same | [TaxGuru](https://taxguru.in/service-tax/service-tax-rate-chart-effect-01062016.html) |
| 2017-07-01 | **18% GST** | brokerage, exchange txn, SEBI fee | [Zerodha charges](https://zerodha.com/charges) |

The rates you gave in the brief (12.36%, 14%, 14.5%, 15%, 18%) are **all confirmed**. One period was missing from that list: 10.30% from 2009 to 2012-03-31.

GST is **not** charged on STT or stamp duty. Brokers differ on GST for the SEBI fee. Zerodha charges it; Motilal Oswal says it depends on how the invoice is structured. The GST 2.0 rate changes of 2025-09-22 are reported to have left broking at 18%, but this comes from a secondary source only.

!!! warning "UNVERIFIED"
    Whether service tax (before 2017) was charged on the SEBI turnover fee.

### 1.6 Not modelled as statutory

- **DP charges:** a flat fee per scrip per day, charged on delivery sells only. It varies by broker and depository; Zerodha charges ₹15.34 including GST in 2026. Make it a user-configurable setting.
- **Brokerage:** varies by broker. Use a user-configurable default.

### 1.7 Rates that changed in 2024–2026 (cash equity)

| Date | Change |
|---|---|
| 2024-04-01 | NSE transaction charge 0.00325% → 0.00322% |
| 2024-10-01 | NSE transaction charge → flat 0.00297% (total 0.00307% with IPFT) |
| 2026-03-01 | IPFT moved into the transaction charge (₹306.99 + ₹0.01 per crore). **No change to the total.** |
| 2024-10-01, 2026-04-01 | STT changed for **F&O only**. Cash-equity STT is unchanged since 2012-07-01. |

---

## 2. Market rules

### 2.1 Settlement cycle

| Effective | Cycle | Source |
|---|---|---|
| 2003-04-01 | T+2 | [SEBI Circular No. 19, 2003](https://www.sebi.gov.in/legal/circulars/mar-2003/circular-no-19-calendar-for-the-implementation-of-t-2-rolling-settlement-w-e-f-april-1-2003-_15830.html) |
| 2022-02-25 → 2023-01-26 | Phased move to T+1, starting with the bottom 100 stocks by market cap | [Joint MII press release](https://nsdl.co.in/downloadables/pdf/Press%20Release%20-%20Joint%20Press%20Release%20for%20implementation%20of%20T+1%20Settlement.pdf) |
| **2023-01-27** | **T+1 for all equities** (final batch included Nifty 50) | [Motilal Oswal](https://www.motilaloswal.com/learning-centre/2023/1/t-plus-1-settlement-for-stocks-kicks-in-from-27-january-2023), [Cleartax](https://news.cleartax.in/t1-settlement-cycle-comes-into-effect-from-jan-27-2023/8922/amp) |

The final-phase date of 2023-01-27 is **confirmed** by several sources. Reports disagree on the size of each batch between 2022-02 and 2023-01. Per-stock switch dates are **not** included here. Optional same-day (T+0) settlement started on 2024-03-28 as a beta for a limited set of stocks; the simulator ignores it.

### 2.2 Market-wide index circuit breaker (10/15/20%)

The trigger is a move in either the Nifty 50 or the Sensex, whichever is breached first.

| Trigger | Before 13:00 | 13:00–14:30 (10%) / 13:00–14:00 (15%) | Later |
|---|---|---|---|
| 10% | halt 1 h | halt 30 min | no halt (at/after 14:30) |
| 15% | halt 2 h | halt 1 h | closed for the day (at/after 14:00) |
| 20% | closed for the day | closed for the day | closed for the day |

- **2001-07-02 to 2013-10-13** ([SEBI 28-Jun-2001](https://www.sebi.gov.in/legal/circulars/jun-2001/index-based-market-wide-circuit-breaker-in-compulsory-rolling-settlement_17986.html)): the trigger levels were fixed points for each quarter. They were based on the previous quarter-end close and rounded to the nearest 25 points.
- **From 2013-10-14** ([NSE/CMTR/24709](https://nsearchives.nseindia.com/content/circulars/CMTR24709.pdf)): levels are recalculated every day from the previous close and rounded to the tick. Total halt lengths are the same as before, but the last 15 minutes of each halt is now a pre-open call auction (e.g. 45 min halt + 15 min pre-open). All outstanding orders are cancelled when a halt starts.
- No 2025–2026 change to the breaker was found.

### 2.3 Price bands, tick size, closing price

- **Price bands:** non-F&O stocks have fixed bands of 2%, 5%, 10% or 20%. F&O stocks have **dynamic** bands, starting at 10% and flexing in 5% steps. NSE tightened the flex conditions in 2024. The per-stock band history is **not** in the JSON; NSE publishes separate daily band-change files.
- **Tick size:** ₹0.05 until 2024-06-09. From **2024-06-10**, stocks below ₹250 (based on the prior month-end close) trade in ₹0.01 ticks, reviewed monthly ([Zerodha bulletin](https://zerodha.com/marketintel/bulletin/380460/change-in-tick-size-of-nse-stocks-and-fo-contracts-trading-below-250)).
- **Closing price:** the VWAP of the last 30 minutes of trading. **From 2026-08-03**, a Closing Auction Session (15:15–15:35) sets the close for stocks that have derivatives ([SEBI circular 16-Jan-2026; NSE circulars](https://nsearchives.nseindia.com/content/circulars/CMTR75479.pdf)). This creates a break in what "close" means within the series.

!!! warning "UNVERIFIED"
    - The Closing Auction Session go-live date (2026-08-03) comes from secondary summaries; the NSE PDF text was not read.
    - Any 2025–2026 tick-size slab changes: none found.
    - SEBI's reported April 2026 proposal for uniform dynamic bands.

---

## 3. Data sources

!!! danger "Regulatory constraint that bears directly on a trading simulator"
    - **NSE Data Usage & Sharing Policy, §7.4** ([PDF, created 2024-10-01](https://nsearchives.nseindia.com/web/sites/default/files/inline-files/NSE_Data_Sharing%26Usage_Policy.pdf)): Market Data "shall not be provided to individuals/entities/platforms/apps/websites etc., engaging in online gaming, **virtual trading or simulation**, fantasy games…". §7.3 bans redistribution except under a signed agreement. The policy defines Market Data to include **end-of-day and historical data**.
    - **SEBI price-data lag rules:** SEBI circular SEBI/HO/MRD/MRD-PoD-3/P/CIR/2024/56 (24-May-2024) limited sharing of real-time prices with third parties. Circular HO/47/17/12(11)2025-MRD-POD3/I/11107/2026 (08-May-2026, effective **2026-07-01**) sets a uniform **30-day lag** for using price data in education and awareness. NISM's simulation lab is allowed a 1-day lag. ([TaxGuru summary](https://taxguru.in/sebi/norms-sharing-usage-price-data-educational-purposes.html))
    - **Implication (my reading, not legal advice):** a public simulator that shows NSE prices needs a legal review. The questions are (a) whether a licence from NSE Data & Analytics is needed and is even available for a "simulation" use, and (b) whether replaying data more recent than 30 days counts as an "educational" use under the 2026 circular. **Get legal sign-off before launching publicly.**

| Source | What's free | Licensing / redistribution | History depth (probed 2026-10-19) |
|---|---|---|---|
| **NSE CM bhavcopy (old format)** `content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip` | Daily OHLC, volume, turnover by symbol and series | Downloading from nseindia.com is free. Redistribution and commercial use need an NSE Data licence (policy above). Automated scraping is barred by the NSE Data portal terms. | HTTP 200 for 1994-11-03 and 2024-07-05. HTTP 404 for 2024-08-01: **discontinued w.e.f. 2024-07-08** |
| **NSE CM UDiFF bhavcopy** `content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip` | Same data with ISIN, `FinInstrmId`, new column names (`TckrSymb`, `ClsPric`, `TtlTradgVol`, …) | Same | HTTP 200 for 2024-01-01 onward. 404 for 2023-12-28/29, so UDiFF files at this path start in **2024** |
| **NSE `sec_bhavdata_full`** `products/content/sec_bhavdata_full_DDMMYYYY.csv` | OHLC + `DELIV_QTY`, `DELIV_PER` (delivery data) | Same | HTTP 200 from **2019-09-30**. 404 for every date tested from 2014 to 2019-09-27 |
| **NSE MTO** (security-wise delivery position) `archives/equities/mto/MTO_DDMMYYYY.DAT` | Traded qty, deliverable qty, % delivery | Same | HTTP 200 for 2010-01-04 and 2026-10-15. Covers the full 2010+ window. |
| **NSE index closes** `content/indices/ind_close_all_DDMMYYYY.csv` | All NSE index OHLC for one day | Same. Index *data* is owned by NSE Indices Ltd. | HTTP 200 for 2026-10-15; earliest date not probed |
| **NSE historical index constituents** | Only the **current** list ([niftyindices `ind_nifty50list.csv`](https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv)). Past changes are announced in NSE Indices press releases (usually semi-annual, plus ad-hoc). | No official point-in-time constituent file was found. | **UNVERIFIED.** A forum reports archived constituent files from 2013 that stopped updating after 2020. Point-in-time membership has to be rebuilt from press releases. |
| **NSE corporate actions** | Corporate-actions listing on nseindia.com (dividends, splits, bonus, rights) with ex-dates | Same NSE policy | **UNVERIFIED:** depth and bulk download not tested (the site needs browser cookies) |
| **NSE equity master** `content/equities/EQUITY_L.csv` | Current listed securities, ISIN, listing date | Same | Current snapshot only (delisted names missing, so survivorship bias) |
| **BSE bhavcopy** `download/BhavCopy/Equity/…` | Daily OHLC; UDiFF `BhavCopy_BSE_CM_0_0_0_YYYYMMDD_F_0000.CSV` since mid-2024; older `EQDDMMYY_CSV.ZIP` | BSE terms of use (**UNVERIFIED**; not read) | HTTP 200 for `EQ040110_CSV.ZIP` (2010-01-04) and UDiFF 2026-10-15. BSE moved to UDiFF w.e.f. 2024-07-08 ([BSE UDiFF page](https://bseindia.com/static/members/udiff.aspx)) |
| **RBI DBIE** (moved to [data.rbi.org.in](https://data.rbi.org.in) in June 2024) | Macro time series (rates, money, FX, prices) as Excel/CSV/PDF; public since 2004 ([RBI brochure](https://dbieold.rbi.org.in/DBIE/doc/Brochure%20on%20DBIE%20%202022%20English.pdf)) | **UNVERIFIED:** formal reuse licence and API not found. RBI describes the data as "reusable" for research. | Decades for most series; varies by series |
| **SEBI** (sebi.gov.in) | Circulars, regulations, bulletins, FPI and MF statistics | Public regulatory documents | Circulars back to the 1990s |

!!! warning "UNVERIFIED: data sources"
    - Exact BSE website terms on redistribution.
    - Whether NSE's free website files fall under the §7.4 "simulation" restriction, or only data licensed through NSE Data.
    - Whether `sec_bhavdata_full` is published under another path before 2019-09-30. The NSE "Security-wise archive" UI may go further back.
    - A source for historical index constituents.

The file availability above was tested with direct HTTP GET requests on 2026-10-19 (status code only). That shows which files exist; it says nothing about whether we are licensed to use them.
