# Capital-gains working: methodology (listed shares, v1)

Rules version `in-cg-2026.1`. **For review by a chartered accountant before `money_tax_report` is
enabled.** The report is an informational working from the user's Nivesh transactions. It is not tax
advice and not a filing.

## Scope

- Listed equity shares only, from the user's own ledger. **Mutual funds are not covered in v1**: fund tax needs the full purchase and sale history, and CAS import brings balances only.
- Per financial year (April to March), `fy` between 2018-19 and the current year.
- Not applied: set-off of losses, carry-forward, surcharge, cess, slab-rate income, advance tax, Securities Transaction Tax as a deduction.
- FIFO is applied per (user, ticker) across the user's whole ledger, not per demat account.

## Legal basis (to be confirmed by the reviewer)

- Short-term and long-term definition: listed shares held for more than 12 months are long-term.
- Rates: STCG 15% and LTCG 10% for sales before 23 Jul 2024; STCG 20% and LTCG 12.5% for sales on or after 23 Jul 2024 (Finance (No. 2) Act 2024).
- Exemption on long-term gains: Rs 1,00,000 up to FY 2023-24 and Rs 1,25,000 from FY 2024-25, applied by financial year of sale.
- Sections: 111A (short-term) and 112A (long-term) for sales before 1 Apr 2026; sections 196 and 198 of the Income-tax Act 2025 from 1 Apr 2026.
- Grandfathering, section 55(2)(ac): for shares acquired on or before 31 Jan 2018, cost of acquisition is the higher of actual cost and the lower of the fair market value on 31 Jan 2018 and the sale value.
- The 112A / 198 benefit assumes STT was paid on acquisition; the notified exceptions are not modelled (see below).

## Method

1. **Rows.** Equity ledger rows (BUY, SELL, SPLIT, BONUS, ADJUST); dividends are ignored.
2. **Lots.** BUY creates a lot at (quantity x price + fees) / quantity per share, dated by the Indian trade date. SPLIT scales lots (quantity x ratio, unit cost / ratio). BONUS creates a nil-cost lot dated at the bonus. A no-op ADJUST is ignored; an ADJUST to zero clears the lots; any other ADJUST makes one lot with an uncertain date.
3. **Matching.** A SELL consumes the oldest lots first. Sale fees are split across the lots by quantity. Selling more than the lots hold marks that sale "not computed".
4. **Term.** Long-term when the sale date is after the acquisition date plus 12 calendar months (month-end clamped).
5. **Grandfathering.** For lots acquired on or before 31 Jan 2018: fair market value = the raw (unadjusted) NSE high on 31 Jan 2018, or on the last earlier trading day, divided by the cumulative split ratios after that date. One batched request per report.
6. **Gain.** Sale value minus cost used minus transfer expenses (the sale-side fees).
7. **Summary.** Gains by term and by rate period (before / on or after 23 Jul 2024). "Above the exemption" is net long-term gain minus the exemption limit, floored at zero, with no set-off against short-term losses.

## Not-computed reasons

| Code | Meaning |
|---|---|
| `acquisition_date_uncertain` | The lot comes from an edited holding (restating ADJUST) or an opening balance with no entered purchase date |
| `etf_category_unverified` | The name contains "ETF" or the symbol ends BEES / IETF; ETF tax category is not decided |
| `fmv_unavailable` | Bought before 1 Feb 2018 and the 31 Jan 2018 price could not be fetched (or the engine's numbers may not be shown yet) |
| `ledger_inconsistent` | The ledger sells more than it holds |

## Review reasons (the row is computed but should be checked)

| Code | Meaning |
|---|---|
| `fmv_nse_high` | Cost uses the NSE high on 31 Jan 2018 |
| `corporate_action_review` | An automatic split from market data was applied |
| `possible_intraday` | A purchase of the same share on the sale date: may be business income |
| `user_entered_date` | The acquisition date is the purchase date the user entered for an opening balance |
| `stt_on_acquisition_unverified` | A bonus lot or opening balance: payment of STT on acquisition is not known |

## Known limitations

- No loss set-off, surcharge, cess or slab-rate income.
- No mutual funds in v1.
- FIFO across all of the user's demat accounts together.
- Fair market value uses the NSE high only (no BSE comparison for dual-listed shares). Decision needed: NSE high, or the higher of NSE and BSE.
- Bonus shares are nil-cost lots dated at the bonus; splits scale lots without changing the acquisition date. The reviewer should confirm this treatment.
- Opening-balance purchase dates are user-entered. A fully sold opening-balance holding loses its entered date and is not computed.
- The STT-on-acquisition condition for 112A / 198 and its notified exceptions (for example off-market and pre-listing acquisitions) are not modelled; the review flag asks the user to check.
- Intraday and F&O trades are not separated beyond the `possible_intraday` flag.

## Worked examples (sign-off checklist)

Each is a test in `backend/tests/test_money_tax_report.py` or `test_money_tax_rules.py`.

| # | Inputs | Expected |
|---|---|---|
| 1 | BUY 10 @ 1,000 + fees 20 on 10 May 2025; SELL 10 @ 1,200 + fees 15 on 1 Dec 2025 (FY 2025-26) | Short-term, section 111A, rate period from 23 Jul 2024. Sale 12,000; cost 10,020; expenses 15; gain 1,965 |
| 2 | BUY 10 on 1 Mar 2024; SELL on 1 Mar 2025, then on 2 Mar 2025 | 1 Mar 2025: short-term. 2 Mar 2025: long-term |
| 3 | 31 Jan 2024 plus one month | 29 Feb 2024 (month-end clamp) |
| 4 | Sale on 22 Jul 2024 vs 23 Jul 2024 | Rates 15% / 10% vs 20% / 12.5% |
| 5 | ITC: BUY 100 @ 500 on 1 Jun 2017; NSE high on 31 Jan 2018 = 800; SELL 100 @ 1,000 in FY 2025-26 | Cost used 80,000 (the FMV), gain 20,000, review `fmv_nse_high` |
| 6 | As 5 but the 31 Jan 2018 value of the 100 shares (Rs 2,00,000) is above the sale value (Rs 1,00,000) | Cost used is capped at the sale value, so no artificial loss |
| 7 | BUY 100 @ 500 in 2017; 2-for-1 split in 2019; high 2,400; SELL 200 @ 1,500 | FMV per share 1,200; cost used 2,40,000; gain 60,000 |
| 8 | BUY 10 @ 100 (Jan 2023); BONUS 10 (Aug 2025); SELL 20 @ 200 (Dec 2025) | Two rows: long-term (cost 1,000) and short-term (nil cost) with `stt_on_acquisition_unverified` |
| 9 | Position that exists only as a restating ADJUST, then a SELL | Not computed: `acquisition_date_uncertain` |
| 10 | Opening-balance BUY with purchase date 3 Feb 2022 entered, then a SELL in FY 2025-26 | Computed as long-term, reviews `user_entered_date` and `stt_on_acquisition_unverified`. Without the date: not computed |
| 11 | Sale on 15 Apr 2026 | Sections 196 (short-term) and 198 (long-term) |
| 12 | LTCG of Rs 1,45,000 in FY 2023-24 vs FY 2024-25 | Above the exemption: 45,000 (limit 1,00,000) vs 20,000 (limit 1,25,000) |
| 13 | Three grandfathered tickers in one report | One batched price request |
| 14 | Engine numbers not shown yet | `fmv_unavailable`, no row computed for grandfathered lots |

CSV: first line `# Nivesh capital gains working FY <fy> (rules in-cg-2026.1). Listed shares only. Informational only; verify with a chartered accountant.`, then the header, computed rows, then not-computed rows with an empty gain.
