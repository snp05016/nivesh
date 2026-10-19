---
title: Costs & charges
description: Effective-dated Indian cash-equity delivery charges used by the Time Machine and the Hypothesis Lab.
---

# Costs & charges

<p class="nv-lede">Every fill in the Time Machine, and every round trip in the Hypothesis Lab, is charged the
statutory and exchange fees that applied <em>on that date</em>. Rates live in
<code>ml-engine/lab/india_charges.json</code>, and every row has a source. <code>ml-engine/lab/costs.py</code> only does the arithmetic.</p>

!!! info "Authority"
    The JSON is the machine-readable authority. The readable summary, with links to the circulars,
    is [Verified facts §1](research/verified-facts.md#1-statutory-and-exchange-charges-nse-cash-equity).
    Rows marked :material-alert-outline: are **UNVERIFIED** representative values.

## The formula for one fill

For a delivery fill of value \(V\) (₹) on trading day \(d\), with each rate taken from the row in
effect on \(d\):

\[
\begin{aligned}
\text{brokerage} &= \min(\text{flat},\ \text{pct}\cdot V) \quad(\text{default } \min(₹20,\ 0.03\%\cdot V))\\
\text{STT} &= V\cdot r_{\text{STT}}^{\text{side}}\\
\text{exchange} &= V\cdot r_{\text{NSE+IPFT}}\\
\text{SEBI} &= \frac{V}{10^7}\cdot r_{\text{SEBI}}^{₹/\text{cr}}\\
\text{stamp} &= V\cdot r_{\text{stamp}}\ \text{on BUY only}\\
\text{GST} &= r_{\text{GST}}\cdot\!\!\sum_{c\,\in\,\text{applies\_to}}\!\! c
\end{aligned}
\]

`total` is the sum of the six components, each rounded to the paisa. The result also includes
`sources` (the source ids used), so the app can show a contract-note-style breakdown.

!!! note "Brokerage is a parameter, not a statute"
    `Brokerage(flat_inr=20, pct=0.0003)` is a typical discount-broker default. Set both to 0 for
    zero-brokerage delivery. In a session these are `brokerage_flat` and `brokerage_pct` in
    `SimConfig`. DP charges are a flat fee per scrip per sell day that varies by broker, and they are
    **not modelled**.

## Effective-dated schedule

Rendered from `india_charges.json` (version 2026-10-19).

=== "STT"

    | Effective | Delivery buy | Delivery sell | Source |
    |---|---|---|---|
    | 2010-01-01 → 2012-06-30 | 0.125% | 0.125% | `cse_stt_2012` |
    | 2012-07-01 → present | 0.1% | 0.1% | `nse_fatax_73524` |

=== "NSE transaction (+IPFT)"

    | Effective | Rate per side | ₹ per crore | Source |
    |---|---|---|---|
    | 2010-01-01 → 2020-12-31 | 0.00325% | ₹325 | `nse_fa_56129` :material-alert-outline:{ title="UNVERIFIED" } |
    | 2021-01-01 → 2023-03-31 | 0.00345% | ₹345 | `nse_fa_56129` |
    | 2023-04-01 → 2024-03-31 | 0.00335% | ₹335 | `nse_fa_56129` |
    | 2024-04-01 → 2024-09-30 | 0.00332% | ₹332 | `zerodha_apr2024` |
    | 2024-10-01 → 2026-02-28 | 0.00307% | ₹307 | `nse_fa_73061` |
    | 2026-03-01 → present | 0.00307% | ₹307 | `nse_fa_73061` |

=== "SEBI turnover fee"

    | Effective | ₹ per crore, each side | Source |
    |---|---|---|
    | 2010-01-01 → 2015-09-27 | ₹10 | `sebi_fee_2015` :material-alert-outline:{ title="UNVERIFIED" } |
    | 2015-09-28 → 2017-03-31 | ₹10 | `sebi_fee_2015` |
    | 2017-04-01 → 2019-03-31 | ₹15 | `sebi_fee_2017` |
    | 2019-04-01 → 2020-05-31 | ₹10 | `nse_fa_40632` |
    | 2020-06-01 → 2021-03-31 | ₹5 | `nse_fa_44514` |
    | 2021-04-01 → present | ₹10 | `zerodha_charges_live` |

=== "Stamp duty"

    | Effective | Delivery (buy side) | Source |
    |---|---|---|
    | 2010-01-01 → 2020-06-30 | 0.01% | `moneylife_stamp_2019` :material-alert-outline:{ title="UNVERIFIED" } |
    | 2020-07-01 → present | 0.015% | `zerodha_stamp_2020` |

=== "Service tax / GST"

    | Effective | Rate | Levied on | Source |
    |---|---|---|---|
    | 2009-02-24 → 2012-03-31 | 10.3% | brokerage, exchange_txn | `wiki_service_tax` :material-alert-outline:{ title="UNVERIFIED" } |
    | 2012-04-01 → 2015-05-31 | 12.36% | brokerage, exchange_txn | `wiki_service_tax` |
    | 2015-06-01 → 2015-11-14 | 14% | brokerage, exchange_txn | `wiki_service_tax` |
    | 2015-11-15 → 2016-05-31 | 14.5% | brokerage, exchange_txn | `wiki_service_tax` |
    | 2016-06-01 → 2017-06-30 | 15% | brokerage, exchange_txn | `taxguru_st_2016` |
    | 2017-07-01 → present | 18% | brokerage, exchange_txn, sebi_fee | `zerodha_charges_live` |


??? quote "Sources cited in the schedule"

    - `nse_fatax_73524`: [NSE/FATAX/73524 (31-Mar-2026): Changes in relation to rates of Securities Transaction Tax (Finance Act 2026)](https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf)
    - `cse_stt_2012`: [CSE notice 20-Jun-2012: STT rates revised w.e.f. 01-07-2012 (Finance Act 2012)](https://www.cse-india.com/upload/CSE%20Notices%20&%20Circulars/2012/Notice200612.htm)
    - `nse_fa_73061`: [NSE/FA/73061 (27-Feb-2026): Revision in Transaction Charges (IPFT contribution rolled back, w.e.f. 01-Mar-2026)](https://nsearchives.nseindia.com/content/circulars/FA73061.pdf)
    - `nse_fa_56129`: [NSE/FA/56129 (24-Mar-2023): Revision in Transaction Charges (rollback of Dec-2020 hike; IPFT Rs 10/cr; w.e.f. 01-Apr-2023)](https://nsearchives.nseindia.com/content/circulars/FA56129.pdf)
    - `nse_ipft_2021_pr`: [NSE to roll back 6% hike in transaction charges from April 1 (hike was w.e.f. 01-Jan-2021, circular NSE/FA/46730 dated 18-Dec-2020)](https://www.outlookbusiness.com/news/nse-to-roll-back-6-hike-in-transaction-charges-from-april-1-news-273005)
    - `zerodha_apr2024`: [Zerodha bulletin 15-Mar-2024: Revision in NSE transaction charges from April 1, 2024 (0.00325% -> 0.00322%)](https://zerodha.com/marketintel/bulletin/373933/revision-in-nse-transaction-charges-from-april-1-2024)
    - `bs_apr2024`: [Business Standard 12-Mar-2024: NSE to cut cash, derivatives transaction charges by 1% from April 1](https://www.business-standard.com/markets/news/nse-to-cut-cash-derivatives-transaction-charges-by-1-from-april-1-124031200766_1.html)
    - `zerodha_oct2024`: [Zerodha bulletin 28-Sep-2024: Revision in transaction charges from 1st October 2024 (NSE 0.00322% -> 0.00297%)](https://zerodha.com/marketintel/bulletin/391488/revision-in-transactions-charges-from-1st-october-2024)
    - `zerodha_charges_live`: [Zerodha charges page (live, read 2026-10-19): NSE txn 0.00307%, SEBI Rs 10/cr, stamp 0.015%/0.003%, GST 18%](https://zerodha.com/charges)
    - `sebi_fee_2015`: [SEBI (Stock Brokers and Sub-brokers) Regulations Schedule V tables, footnotes: Rs 10/cr w.e.f. 28-09-2015; substituted w.e.f. 01-04-2017](https://www.taxtmi.com/tmi_blog_details?id=554987)
    - `sebi_fee_2017`: [SEBI (Payment of Fees and Mode of Payment) (Amendment) Regulations 2017, No. SEBI/LAD-NRO/GN/2016-17/038: cash 0.00015% (Rs 15/cr), clause in force 01-04-2017](https://taxguru.in/sebi/sebi-payment-of-fees-and-mode-of-payment-amendment-regulations-2017.html)
    - `nse_fa_40632`: [NSE/FA/40632 (02-Apr-2019) enclosing SEBI (Payment of Fees) (Amendment) Regulations 2019: cash 0.00010% (Rs 10/cr) w.e.f. 01-04-2019](https://nsearchives.nseindia.com/content/circulars/FA40632.pdf)
    - `nse_fa_44514`: [NSE/FA/44514 (29-May-2020) enclosing SEBI (Payment of Fees) (Amendment) Regulations 2020: brokers pay 50% of turnover fee 01-06-2020 to 31-03-2021](https://nsearchives.nseindia.com/content/circulars/FA44514.pdf)
    - `zerodha_stamp_2020`: [Zerodha Z-Connect: Uniform stamp duty from 1 July 2020 (buy side only; old state rates on both sides)](https://zerodha.com/z-connect/zerodha/announcements/uniform-stamp-duty)
    - `upstox_stamp_2020`: [Upstox: Revision in stamp duty rates on 1st July 2020 (deferred from 09-Jan-2020 and 01-Apr-2020)](https://upstox.com/announcements/updates/revision-in-stamp-duty-rates-on-1st-july-2020/)
    - `moneylife_stamp_2019`: [Moneylife 13-Dec-2019: pre-2020 state stamp duty (Maharashtra 0.01% delivery; most states Rs 200-300/cr intraday)](https://mas360.moneylife.in/article/share-transfers-will-be-more-expensive-from-january-next-year/3299.html)
    - `wiki_service_tax`: [Wikipedia: Service tax (India) rate history 2009-2017](https://en.wikipedia.org/wiki/Service_tax)
    - `taxguru_st_2016`: [TaxGuru: Service tax rate chart w.e.f. 01-06-2016 (15% incl. SBC + KKC)](https://taxguru.in/service-tax/service-tax-rate-chart-effect-01062016.html)
    - `gst_rollout`: [BankBazaar: service tax replaced by GST from 1 July 2017](https://cobrand.bankbazaar.com/tax/new-service-tax.html)
    - `sebi_t2_2003`: [SEBI Circular No. 19 (04-Mar-2003): T+2 rolling settlement w.e.f. 01-Apr-2003](https://www.sebi.gov.in/legal/circulars/mar-2003/circular-no-19-calendar-for-the-implementation-of-t-2-rolling-settlement-w-e-f-april-1-2003-_15830.html)
    - `t1_joint_pr`: [Joint MII press release: phased T+1 implementation from 25-Feb-2022 (bottom 100 by market cap first)](https://nsdl.co.in/downloadables/pdf/Press%20Release%20-%20Joint%20Press%20Release%20for%20implementation%20of%20T+1%20Settlement.pdf)
    - `t1_final`: [Motilal Oswal: T+1 settlement for all stocks from 27 January 2023](https://www.motilaloswal.com/learning-centre/2023/1/t-plus-1-settlement-for-stocks-kicks-in-from-27-january-2023)
    - `sebi_mwcb_2001`: [SEBI SMDRPD/Policy/Cir-37/2001 (28-Jun-2001): index-based market-wide circuit breaker](https://www.sebi.gov.in/legal/circulars/jun-2001/index-based-market-wide-circuit-breaker-in-compulsory-rolling-settlement_17986.html)
    - `nse_cmtr_24709`: [NSE/CMTR/24709 (11-Oct-2013): index-based market-wide circuit filter w.e.f. 14-Oct-2013 (daily levels, 15-min pre-open after halt)](https://nsearchives.nseindia.com/content/circulars/CMTR24709.pdf)
    - `nse_mwcb_page`: [NSE: Equity market circuit breakers (price bands, MWCB)](https://www.nseindia.com/products-services/equity-market-circuit-breakers)
    - `zerodha_tick_2024`: [Zerodha bulletin 25-May-2024: NSE tick size Rs 0.01 for stocks below Rs 250 from 10-Jun-2024](https://zerodha.com/marketintel/bulletin/380460/change-in-tick-size-of-nse-stocks-and-fo-contracts-trading-below-250)
    - `nse_cas_2026`: [NSE circular (Jul-2026): Closing Auction Session in equity cash segment live from 03-Aug-2026 (per secondary summaries; PDF not text-verified)](https://nsearchives.nseindia.com/content/circulars/CMTR75479.pdf)

## Worked example: ₹1 lakh delivery round trip

A buy and a sell of ₹1,00,000 each on **2026-09-15**, with default brokerage. These figures come from
running `costs.charges()` itself, not from hand arithmetic.

| Component | BUY | SELL | How |
|---|---:|---:|---|
| Brokerage | 20.00 | 20.00 | min(₹20, 0.03% × 1,00,000 = ₹30) |
| STT | 100.00 | 100.00 | 0.1% each side (since 2012-07-01) |
| Exchange txn + IPFT | 3.07 | 3.07 | 0.00307% (₹307/crore) |
| SEBI fee | 0.10 | 0.10 | ₹10/crore |
| Stamp duty | 15.00 | 0.00 | 0.015%, buyer only (since 2020-07-01) |
| GST | 4.17 | 4.17 | 18% × (20 + 3.07 + 0.10) |
| **Total** | **142.34** | **127.34** | |

**Round trip: ₹269.68, or 0.27% of the traded value.** With zero brokerage it would be
₹118.74 + ₹103.74 = ₹222.48. Note that STT alone is ₹200 of the round trip, so on delivery trades the
tax, not the brokerage, sets the cost floor.

=== "Python"

    ```python
    from datetime import date
    from lab.costs import charges, Brokerage

    buy = charges("BUY", 100_000, date(2026, 9, 15))   # (1)!
    sell = charges("SELL", 100_000, date(2026, 9, 15))
    buy["total"] + sell["total"]                         # 269.68
    charges("BUY", 100_000, date(2026, 9, 15), Brokerage(0, 0))["total"]  # 118.74
    ```

    1.  The result includes `sources`: `nse_fa_73061`, `nse_fatax_73524`, `zerodha_charges_live`, `zerodha_stamp_2020`.

=== "In the Hypothesis Lab"

    `hypothesis._round_trip_cost(spec.end)` charges a ₹1,00,000 buy and sell on the experiment's end
    date and adds an assumed **10 bps of slippage per side**:

    \[
    c_{\text{rt}} = \frac{\text{charges}_{\text{BUY}} + \text{charges}_{\text{SELL}}}{1{,}00{,}000} + 2\times 0.0010
    \]

    On 2026-09-15 that is 0.2697% + 0.20% ≈ **0.47%**. Each period's top-quantile return is reduced by
    `turnover × c_rt`.

## Known gaps

!!! note "Boundary days"
    `effective_to` is **inclusive** (the last day a rate applied). Where ranges share a boundary day, the later row wins. A test resolves every calendar day from 2010-01-01 to today against the real schedule.

- **Stamp duty before 2020-07-01** was generally charged on both sides and varied by state. The code
  charges the representative buy-side rate only (see the note on the stamp-duty row).
- **Exchange slabs:** before 2024-10-01 NSE charged by slab. The table uses the first-slab rate that retail brokers generally passed on.
- **Intraday and F&O rates** are in the JSON but not used, because the simulator is delivery-only.
