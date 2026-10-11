import Foundation

enum TermCategory: String, Codable, CaseIterable {
    case valuation = "Valuation"
    case risk = "Risk & Volatility"
    case charts = "Chart Indicators"
    case fundamentals = "Fundamentals"
    case aiAnalysis = "AI Analysis"
    case macro = "Macro Economy"
    case ownership = "Ownership"
    case marketMechanics = "Market Mechanics"
    case portfolio = "Portfolio"
}

/// A single financial term with its definition, real-world example, category, and related terms.
struct FinanceTerm: Codable {
    let term: String
    let definition: String
    let example: String
    let category: TermCategory
    let relatedTerms: [String]
}

/// Singleton dictionary of financial terms used across the app.
/// Keys are lowercase, whitespace-normalized for fuzzy matching.
final class FinanceTerms {
    static let shared = FinanceTerms()

    private let dict: [String: FinanceTerm]

    private init() {
        var d: [String: FinanceTerm] = [:]

        func add(_ t: String, _ def: String, _ ex: String, _ cat: TermCategory, _ related: [String] = []) {
            let key = t.lowercased().trimmingCharacters(in: .whitespaces)
            d[key] = FinanceTerm(term: t, definition: def, example: ex, category: cat, relatedTerms: related)
        }

        // ── Technical Indicators ──────────────────────────────────────
        add("RSI",
            "Relative Strength Index — a momentum oscillator measuring speed and magnitude "
            + "of recent price changes. Ranges 0–100.",
            "RSI above 70 = overbought (price may pull back). RSI below 30 = oversold "
            + "(price may bounce). RELIANCE RSI at 74 signals caution.", .charts)

        add("MACD",
            "Moving Average Convergence Divergence — tracks the relationship between two "
            + "exponential moving averages (12-day and 26-day) of a stock's price.",
            "When the MACD line crosses above the signal line, it's a bullish signal. "
            + "TCS showed a MACD crossover on 3 Jan, rose 8% over the next 3 weeks.", .charts)

        add("SMA",
            "Simple Moving Average — the arithmetic mean of a stock's closing prices over "
            + "N days. Smooths out short-term noise.",
            "50-day SMA for RELIANCE = ₹2,760. Price currently ₹2,847 = trading above its "
            + "50-day average, which is a bullish sign.", .charts)

        add("EMA",
            "Exponential Moving Average — like SMA but gives more weight to recent prices, "
            + "reacting faster to price changes.",
            "12-day EMA responds faster to new prices than 50-day SMA. MACD is built from "
            + "the difference between 12-day EMA and 26-day EMA.", .charts)

        // ── Valuation Metrics ──────────────────────────────────────────
        add("P/E Ratio",
            "Price-to-Earnings ratio — how much investors pay per rupee of annual profit. "
            + "Higher P/E = investors expect faster growth.",
            "HDFCBANK trades at P/E 18×. If it earns ₹100/share, the stock costs ₹1,800. "
            + "NIFTY 50 average P/E is ~22×.", .valuation)

        add("P/E",
            "Price-to-Earnings ratio — how much investors pay per rupee of annual profit. "
            + "Higher P/E = investors expect faster growth.",
            "HDFCBANK trades at P/E 18×. If it earns ₹100/share, the stock costs ₹1,800. "
            + "NIFTY 50 average P/E is ~22×.", .valuation)

        add("EPS",
            "Earnings Per Share — the company's net profit divided by total shares outstanding. "
            + "Higher EPS means more profit for each share you hold.",
            "TCS EPS ₹122 this quarter. If you hold 10 shares, TCS earned ₹1,220 on your behalf.", .valuation)

        add("ROE",
            "Return on Equity — how efficiently a company uses shareholder money to generate "
            + "profit. Expressed as a percentage.",
            "HDFCBANK ROE 16% means: for every ₹100 of shareholder equity, it earns ₹16 profit. "
            + "Above 15% is generally considered strong.", .valuation)

        add("EBITDA",
            "Earnings Before Interest, Taxes, Depreciation and Amortisation — a proxy for "
            + "operating cash flow before financing and accounting decisions.",
            "RELIANCE EBITDA ₹1.8L Cr means its core businesses generated that much operating "
            + "profit before paying interest and taxes.", .valuation)

        // ── Market Participants ────────────────────────────────────────
        add("FII",
            "Foreign Institutional Investor — overseas funds (pension funds, hedge funds, "
            + "mutual funds) that invest in Indian markets.",
            "FIIs bought ₹8,200 Cr of Indian equities last month. Heavy FII buying often "
            + "signals confidence in India's growth story.", .ownership)

        add("DII",
            "Domestic Institutional Investor — Indian institutions (LIC, mutual funds, banks) "
            + "investing in Indian equities.",
            "When FIIs sell, DIIs often absorb the selling. Say in one month FIIs sell ₹8,000 Cr "
            + "net while DIIs buy ₹12,000 Cr — markets can stay stable.", .ownership)

        // ── Risk & Volatility ──────────────────────────────────────────
        add("Beta",
            "Measures how much a stock moves relative to the market. Beta 1 = moves with "
            + "NIFTY. Beta > 1 = more volatile. Beta < 1 = more stable.",
            "TATAMOTORS Beta 1.4 — if NIFTY falls 5%, TATAMOTORS typically falls ~7%. "
            + "HDFCBANK Beta 0.9 — more defensive.", .risk)

        add("VIX",
            "India VIX — the 'Fear Index'. Measures expected market volatility over the "
            + "next 30 days derived from NIFTY options prices.",
            "VIX at 12 = calm markets. VIX spiking to 25+ = panic buying of puts, expect "
            + "large NIFTY swings. Historically, VIX spikes are buying opportunities.", .risk)

        // ── Returns & Performance ──────────────────────────────────────
        add("CAGR",
            "Compound Annual Growth Rate — the steady annual return rate that would take an "
            + "investment from its starting value to its ending value.",
            "₹1L invested in INFY 5 years ago is now ₹1.95L. CAGR = 14.3% per year. "
            + "Better than FD (6.5% CAGR) but with higher risk.", .portfolio)

        add("XIRR",
            "Extended Internal Rate of Return — the actual annualised return on your "
            + "portfolio accounting for the exact timing of every buy and sell.",
            "Even if a stock is up 40%, your XIRR may be 22% if you added more money at the peak. "
            + "XIRR is the only honest way to measure your personal returns.", .portfolio)

        // ── Fundamental Health ─────────────────────────────────────────
        add("Piotroski Score",
            "A 0–9 scoring system for a company's financial health. Scores 8–9 = financially "
            + "strong. Scores 0–2 = financially weak. Based on profitability, leverage, and "
            + "operating efficiency metrics.",
            "HDFCBANK Piotroski Score 8 — strong earnings, declining debt, growing margins. "
            + "A score of 2 on a stock you hold is a red flag.", .fundamentals)

        // ── Price Benchmarks ───────────────────────────────────────────
        add("52W High",
            "The highest price a stock traded at in the last 52 weeks (1 year).",
            "RELIANCE 52W High ₹3,124. Current price ₹2,847 = trading 8.9% below its yearly "
            + "peak. Some investors see this as a discount entry.", .valuation)

        add("52W Low",
            "The lowest price a stock traded at in the last 52 weeks.",
            "TATAMOTORS 52W Low ₹802. It has rallied 22% from that bottom. Sustained recovery "
            + "above 52W Low suggests the sell-off phase is over.", .valuation)

        add("52-Week High",
            "The highest price a stock traded at in the last 52 weeks (1 year).",
            "RELIANCE 52W High ₹3,124. Current price ₹2,847 = trading 8.9% below its yearly peak.", .valuation)

        add("52-Week Low",
            "The lowest price a stock traded at in the last 52 weeks.",
            "TATAMOTORS 52W Low ₹802. It has rallied 22% from that bottom.", .valuation)

        // ── Market Structure ───────────────────────────────────────────
        add("Market Cap",
            "Total market value of a company — current stock price × total shares outstanding. "
            + "Determines if it's large-cap, mid-cap or small-cap.",
            "RELIANCE Market Cap ₹19.8L Cr = largest listed company in India. NIFTY 50 "
            + "includes only large-cap companies above ~₹20,000 Cr.", .valuation)

        // ── Derivatives ────────────────────────────────────────────────
        add("Open Interest",
            "The total number of outstanding derivative contracts (options or futures) that "
            + "have not been settled. Higher OI = more active participation.",
            "NIFTY 23,000 Call OI rose 8L contracts. This means more traders are betting NIFTY "
            + "will NOT cross 23,000 — acts as a resistance level.", .marketMechanics)

        add("Put/Call Ratio",
            "Total Put open interest divided by total Call open interest. A ratio above 1 "
            + "means more bearish bets. Below 1 means more bullish bets.",
            "PCR 1.3 for BANKNIFTY = more puts than calls, meaning institutional hedges are "
            + "high. Contrarians read this as a bullish signal.", .marketMechanics)

        // ── Market Mechanics ───────────────────────────────────────────
        add("Circuit Breaker",
            "A regulatory halt triggered when a stock moves up or down by a set percentage "
            + "in a single session. Upper circuit = price locked at the limit up.",
            "A small-cap stock hit 20% upper circuit — it cannot trade higher today regardless "
            + "of demand. Check if this is news-driven or operator activity.", .marketMechanics)

        add("Bulk Deal",
            "A single trade of more than 0.5% of a company's total shares in one session. "
            + "Must be disclosed to the exchange on the day of the trade.",
            "LIC bought 1.2% of BAJFINANCE in a bulk deal at ₹6,800. When LIC accumulates, "
            + "it's often read as a long-term confidence signal.", .marketMechanics)

        // ── Balance Sheet ─────────────────────────────────────────────
        add("Debt/Equity",
            "Total debt divided by shareholders' equity. Lower is generally safer. "
            + "Shows how leveraged a company is.",
            "TATAMOTORS D/E 1.8 = it owes ₹1.80 for every ₹1 of equity — highly leveraged. "
            + "INFY D/E 0.02 — virtually debt-free, much safer balance sheet.", .fundamentals)

        add("D/E Ratio",
            "Total debt divided by shareholders' equity. Lower is generally safer. "
            + "Shows how leveraged a company is.",
            "TATAMOTORS D/E 1.8 — highly leveraged. INFY D/E 0.02 — virtually debt-free.", .fundamentals)

        add("Dividend Yield",
            "Annual dividend per share divided by current share price, expressed as a %. "
            + "Shows the cash income you earn just for holding the stock.",
            "ITC pays ₹6.75 dividend. Share price ₹438 → Dividend Yield 1.54%. "
            + "If ITC were a bank FD, you'd compare this to the FD interest rate.", .fundamentals)

        add("Free Cash Flow",
            "Cash a company generates after paying for capital expenditure — the actual "
            + "money left over that can be returned to shareholders or invested.",
            "RELIANCE generated ₹48,000 Cr FCF last year. This funds Jio expansion, retail "
            + "growth AND share buybacks — without needing to borrow.", .fundamentals)

        add("Promoter Pledging",
            "When promoters (founders/major shareholders) pledge their shares as collateral "
            + "for loans. High pledging is a risk — forced selling if stock falls.",
            "If a promoter pledges 60% of their holding and the stock drops sharply, lenders "
            + "can sell those shares, causing further price collapse. Always check.", .ownership)

        add("Promoter",
            "The founders or controlling shareholders of a company. High promoter holding "
            + "signals alignment with minority shareholders.",
            "TCS promoter (Tata Group) holds 72% — strong alignment. Low promoter holding "
            + "below 30% can signal weak commitment.", .ownership)

        add("Institution",
            "Institutional investors — FIIs, DIIs, mutual funds, insurance companies that "
            + "invest large pools of capital with professional management.",
            "High institutional holding (above 40%) indicates professional confidence in the "
            + "stock. But coordinated selling can cause sharp falls.", .ownership)

        add("Confidence Score",
            "A 0–100 score representing the AI model's confidence in its BUY/SELL/HOLD "
            + "recommendation. Higher = more conviction.",
            "Confidence score 85 on a SELL signal = the model is very certain of downside. "
            + "Score 55 on BUY = marginal conviction, more research warranted.", .aiAnalysis)

        add("Upside",
            "The potential percentage gain from the current price to the target price. "
            + "Higher upside = more potential profit, but also typically higher risk.",
            "3-month target ₹3,200 vs current ₹2,847 = 12.4% upside. Long-term 36-month "
            + "target shows the analyst's multi-year view.", .aiAnalysis)

        // ── AI Analysis ──────────────────────────────────────────────
        add("Signal",
            "The final recommendation from the AI analysis — BUY, HOLD, or SELL — "
            + "determined by a multi-agent debate weighing bullish and bearish arguments.",
            "A BUY signal with 75% confidence means the AI's debate produced a buy "
            + "recommendation it's 75% certain about. Always check 'Why this signal?' for reasoning.",
            .aiAnalysis, ["Confidence Score", "Bull Case", "Bear Case"])

        add("Bull Case",
            "The bullish argument — reasons why the stock might go up. Generated by "
            + "the Bull researcher agent during the AI debate.",
            "Bull case: 'Revenue up 15%, expanding margins into new markets.' Always "
            + "read the bear case too before deciding.",
            .aiAnalysis, ["Bear Case", "Signal"])

        add("Bear Case",
            "The bearish argument — reasons why the stock might go down. Generated by "
            + "the Bear researcher agent. Bear findings are weighted 1.5× for safety.",
            "Bear case: 'Input costs rising, FIIs selling, governance flag on related-party deal.'",
            .aiAnalysis, ["Bull Case", "Signal"])

        add("Key Risks",
            "The most important risks identified by the AI analysis that could cause "
            + "the stock to underperform or decline.",
            "Key risk: 'Promoter pledging above 30% — margin-call cascade possible if stock drops 15%.'",
            .aiAnalysis, ["Bear Case"])

        add("Staleness",
            "How old the analysis is and whether it's still reliable. Based on age, "
            + "price movement since analysis, and signal mismatch. Fresh = reliable. Stale = re-run.",
            "Analysis is 3 days old, stock moved 2% = FRESH. Analysis is 20 days old, "
            + "stock moved 12% = STALE, re-run recommended.",
            .aiAnalysis, ["Confidence Score"])

        add("Analysis Tier",
            "The depth of analysis: Standard (fast, 1-round debate), Deep (adds screening "
            + "data), or Extreme (multi-round debate, long-form thesis, most thorough).",
            "Extreme tier uses DeepSeek V4 Pro with 3-round debate and extended thesis — "
            + "best for major investment decisions.",
            .aiAnalysis, ["Signal", "Confidence Score"])

        add("Governance Score",
            "0–100 score for corporate governance quality. Based on promoter activity, "
            + "SEBI actions, insider trading patterns, and pledge levels. Below 30 = red flag.",
            "RELIANCE governance score 78 = strong. 2 flags on related-party transactions "
            + "reduce it from 85.",
            .aiAnalysis, ["Promoter", "Promoter Pledging"])

        add("Target Price",
            "The AI's projected price for the stock at 3-month, 12-month, and 3-year "
            + "horizons. Based on fundamentals, growth trajectory, and market conditions.",
            "3M target ₹3,200 vs current ₹2,847 = 12.4% upside. 12M target ₹3,800 = "
            + "33% upside. These are projections, not guarantees.",
            .aiAnalysis, ["Upside", "Signal"])

        add("What To Watch",
            "Events or data points to monitor that could change the investment thesis — "
            + "earnings dates, regulatory decisions, macro events.",
            "'Watch for Q2 earnings on Oct 15, SEBI ruling on related-party transaction, "
            + "and crude oil price movement.'",
            .aiAnalysis, ["Key Risks"])

        // ── Ownership ─────────────────────────────────────────────────
        add("Promoter Holding",
            "Percentage of company shares held by the founders/promoters. Above 50% "
            + "shows strong commitment. Below 30% raises alignment questions.",
            "TCS promoter holding 72% — Tata Group has skin in the game. If promoter "
            + "holding drops from 55% to 45% in one quarter, investigate why.",
            .ownership, ["Promoter", "Promoter Pledging"])

        add("Institutional Ownership",
            "Percentage of shares held by FIIs, DIIs, mutual funds, and insurance "
            + "companies combined. High institutional interest signals professional confidence.",
            "HDFCBANK has 85% institutional ownership — among the highest in India. "
            + "This means the stock is heavily researched and professionally managed.",
            .ownership, ["FII", "DII", "Institution"])

        add("Pledged Percentage",
            "What portion of the promoter's holding is pledged as loan collateral. "
            + "Above 30% is a warning sign — forced selling risk if stock falls.",
            "Promoter holds 51% but has pledged 40% of it (= 20.4% of company). "
            + "If stock drops 25%, lenders may sell pledged shares, accelerating the fall.",
            .ownership, ["Promoter Pledging", "Promoter"])

        // ── Valuation ─────────────────────────────────────────────────
        add("Book Value",
            "The accounting value of a company — total assets minus total liabilities, "
            + "divided by shares outstanding. Represents liquidation value per share.",
            "SBI book value ₹380, trading at ₹620 = Price/Book 1.63×. A P/B below 1 "
            + "means the market values the company below its accounting value.",
            .valuation, ["P/E Ratio", "EPS"])

        add("Face Value",
            "The nominal value of one share as stated in the company's charter. Mostly "
            + "relevant for stock splits and bonus issues — not the market price.",
            "RELIANCE face value ₹10. Market price ₹2,847. Face value was relevant when "
            + "shares were first issued — now it's a historical artifact.",
            .valuation, ["Book Value", "Market Cap"])

        add("Industry P/E",
            "The average P/E ratio of all companies in the same sector. Used to judge "
            + "if a stock is overvalued or undervalued relative to its peers.",
            "TCS P/E 32 vs IT industry P/E 28 — slightly premium. But TCS is the "
            + "industry leader, so a premium is often justified.",
            .valuation, ["P/E Ratio", "EPS"])

        // ── Fundamentals ──────────────────────────────────────────────
        add("Revenue",
            "Total money a company earns from selling its products/services before any "
            + "costs are deducted. Also called 'top line' or 'sales'.",
            "TCS quarterly revenue ₹62,000 Cr — grew 7.5% from last year. Revenue "
            + "growth is the first sign of business expansion.",
            .fundamentals, ["PAT", "EBITDA"])

        add("PAT",
            "Profit After Tax — the actual profit left after ALL expenses, interest, "
            + "and taxes. Also called 'bottom line' or 'net profit'.",
            "RELIANCE PAT ₹21,000 Cr this quarter vs ₹19,500 Cr last year = 7.7% growth. "
            + "PAT growth is the ultimate measure of business success.",
            .fundamentals, ["Revenue", "EBITDA", "EPS"])

        add("Operating Margin",
            "Operating profit as a percentage of revenue. Shows how efficiently a "
            + "company runs its core business before interest and taxes.",
            "INFY operating margin 24% = it keeps ₹24 of profit for every ₹100 of "
            + "revenue. Margins above 20% indicate strong pricing power.",
            .fundamentals, ["Revenue", "EBITDA"])

        add("Net Profit Margin",
            "Final profit as a percentage of revenue — after ALL costs. The most "
            + "comprehensive profitability ratio.",
            "TCS net margin 19% = for every ₹100 earned, ₹19 is pure profit. Compare "
            + "this across quarters — declining margins need investigation.",
            .fundamentals, ["PAT", "Operating Margin"])

        add("ROCE",
            "Return on Capital Employed — how efficiently a company uses ALL its "
            + "capital (equity + debt) to generate profit. Above 15% is strong.",
            "RELIANCE ROCE 12% means each ₹100 of total capital generates ₹12 profit. "
            + "ROCE should exceed the company's cost of borrowing.",
            .fundamentals, ["ROE", "Debt/Equity"])

        // ── Macro Economy ─────────────────────────────────────────────
        add("MMI",
            "Market Mood Index — a 0–100 composite indicator of Indian market sentiment "
            + "combining FII flows, volatility, momentum, and breadth.",
            "MMI at 72 (Fear zone) = markets are pessimistic. Historically, buying "
            + "when MMI is in Fear zone has produced good long-term returns.",
            .macro, ["VIX", "FII"])

        add("Brent Crude",
            "The global benchmark price for oil. India imports ~85% of its oil, so "
            + "higher Brent = higher inflation, weaker rupee, pressure on oil-dependent stocks.",
            "Brent at $85/barrel is manageable for India. Above $100 = pain for airlines, "
            + "paints, tyres. Below $70 = relief rally in rate-sensitive sectors.",
            .macro, ["USD/INR"])

        add("USD/INR",
            "The exchange rate between the US Dollar and Indian Rupee. A weaker rupee "
            + "helps IT exporters (earn in dollars) but hurts importers (pay more for oil).",
            "USD/INR at 83.5 means ₹83.50 buys 1 US dollar. If rupee weakens to 85, "
            + "IT stocks like TCS/INFY benefit — their dollar revenue is worth more rupees.",
            .macro, ["Brent Crude", "FII"])

        add("Repo Rate",
            "The rate at which RBI lends to banks. Higher repo = higher loan EMIs, "
            + "slower economy. Lower repo = cheaper loans, faster growth.",
            "When RBI cuts the repo rate, bank loans usually get cheaper; rate-sensitive "
            + "sectors such as banks, autos and real estate often benefit.",
            .macro, ["Brent Crude", "MMI"])

        add("IIP",
            "Index of Industrial Production — monthly measure of factory output across "
            + "manufacturing, mining, and electricity. Key indicator of economic health.",
            "IIP growth 5.2% YoY = industrial activity is healthy. Below 2% for 3+ months "
            + "signals a manufacturing slowdown that will hit corporate earnings.",
            .macro, ["MMI"])

        // ── Chart Indicators ──────────────────────────────────────────
        add("50-DMA",
            "50-day moving average — the average closing price over the last 50 trading "
            + "days. Price above 50-DMA = short-term uptrend. Below = downtrend.",
            "RELIANCE at ₹2,847, 50-DMA at ₹2,760 = trading above = bullish short-term. "
            + "If price breaks below 50-DMA, it often tests the 200-DMA next.",
            .charts, ["SMA", "200-DMA"])

        add("200-DMA",
            "200-day moving average — the average closing price over the last 200 "
            + "trading days. The most watched long-term trend indicator.",
            "NIFTY 200-DMA at 21,800. Trading above = structural bull market. "
            + "A break below 200-DMA for 3+ days is a major trend change warning.",
            .charts, ["50-DMA", "SMA"])

        add("Support",
            "A price level where buying interest is strong enough to stop further "
            + "declines. Price tends to bounce off support levels.",
            "TATAMOTORS has support at ₹950 — it bounced here 4 times in 6 months. "
            + "If support breaks, ₹950 becomes new resistance.",
            .charts, ["Resistance", "SMA"])

        add("Resistance",
            "A price level where selling pressure is strong enough to stop further "
            + "rises. Price tends to reverse from resistance levels.",
            "NIFTY facing resistance at 23,000 — it approached 5 times but couldn't "
            + "break through. A close above 23,000 = breakout, bullish for short term.",
            .charts, ["Support", "SMA"])

        add("Volume",
            "Number of shares traded in a given period. High volume confirms a price "
            + "move is 'real.' Low volume moves are less reliable.",
            "RELIANCE up 3% on 2× average volume = strong confirmation of the move. "
            + "Price up 5% on 0.3× volume = lack of conviction, may reverse.",
            .charts, ["Support", "Resistance"])

        // ── Portfolio ─────────────────────────────────────────────────
        add("P&L",
            "Profit & Loss — the total gain or loss on your investments. Positive = "
            + "you made money. Negative = you lost money.",
            "Portfolio P&L +₹45,000 = your investments have gained ₹45,000 since you "
            + "bought them. This includes both realised (sold) and unrealised gains.",
            .portfolio, ["XIRR", "CAGR"])

        add("Absolute Return",
            "Simple percentage gain: (current value - invested) / invested × 100. "
            + "Does NOT account for how long the money was invested.",
            "₹1L invested, now ₹1.3L = 30% absolute return. But if that took 5 years, "
            + "it's only ~5.4% CAGR — barely above FD rates.",
            .portfolio, ["CAGR", "XIRR"])

        add("Unrealized P&L",
            "Profit or loss on stocks you STILL hold — hasn't been locked in yet. "
            + "Paper gains can vanish if the stock drops before you sell.",
            "HDFCBANK bought at ₹1,600, now ₹1,750 = ₹150 unrealized gain per share. "
            + "This is profit on paper — you haven't sold yet.",
            .portfolio, ["P&L", "Realized P&L"])

        add("Realized P&L",
            "Profit or loss on stocks you've ALREADY sold — locked in permanently. "
            + "This is actual money in your account, not paper gains.",
            "Sold TCS at 25% gain = ₹12,500 realized profit. This is taxable under "
            + "capital gains. Realized losses can offset gains for tax purposes.",
            .portfolio, ["P&L", "Unrealized P&L"])

        add("NAV",
            "Net Asset Value — the per-unit value of a mutual fund or your portfolio. "
            + "Total value of all holdings ÷ total units.",
            "Portfolio total ₹5.2L, you hold 520 units = NAV ₹1,000/unit. NAV tracks "
            + "your overall performance independent of individual stock movements.",
            .portfolio, ["XIRR"])

        // ── Quant, Dashboard & Advanced Market Terms ──────────────────
        add("Calibrated Confidence",
            "A confidence score adjusted by statistical calibration so the percentage reflects "
            + "how often similar past setups actually worked.",
            "A raw BUY probability of 78% may become 66% calibrated confidence if similar "
            + "high-volatility setups historically failed more often than expected.",
            .aiAnalysis, ["Confidence Score", "Market Regime", "Conformal Bounds"])

        add("Quantitative Engine",
            "The math-first layer that scores price action, fundamentals, volatility, and "
            + "market regime before AI agents write the final explanation.",
            "If the Quantitative Engine flags weak base probability and high tail risk, the "
            + "AI report should stay cautious even when news sentiment looks positive.",
            .aiAnalysis, ["Base Probability", "Tail Risk", "Calibrated Confidence"])

        add("Base Probability",
            "The starting statistical probability for a signal before macro regime, risk, "
            + "and model-calibration adjustments are applied.",
            "A stock can start with 61% base probability, then fall to 54% after weak market "
            + "regime and high volatility penalties.",
            .aiAnalysis, ["Calibrated Confidence", "Regime Multiplier"])

        add("Conformal Bounds",
            "A statistically derived range around a forecast that shows where the target "
            + "price is expected to land with a defined confidence level.",
            "A 90% conformal range of ₹920 to ₹1,060 means past model errors suggest the "
            + "true outcome often stays inside that band.",
            .aiAnalysis, ["Target Price", "Calibrated Confidence"])

        add("SHAP Drivers",
            "Feature-attribution signals that explain which inputs pushed a model's score "
            + "up or down.",
            "Positive SHAP drivers may include improving ROCE and rising delivery volume; "
            + "negative drivers may include expensive P/E and weak breadth.",
            .aiAnalysis, ["Quantitative Engine", "ROCE", "Delivery Percentage"])

        add("Market Regime",
            "The current broad-market condition, such as risk-on, risk-off, trending, or "
            + "high-volatility. It changes how much confidence a signal deserves.",
            "A bullish stock setup in a risk-off market regime gets lower conviction than "
            + "the same setup during broad index strength.",
            .risk, ["VIX", "Market Pulse", "Regime Multiplier"])

        add("Tail Risk",
            "The risk of an unusually large adverse move that normal volatility metrics may "
            + "understate.",
            "A stock with stable daily moves can still have high tail risk if promoter "
            + "pledging or event risk could trigger a sharp gap down.",
            .risk, ["VIX", "Promoter Pledging", "Conformal Bounds"])

        add("Minskyan Risk",
            "A fragility warning that markets may have become overconfident after a long "
            + "stable period, making leverage and crowded trades dangerous.",
            "Low volatility plus rising leverage can create Minskyan risk: calm conditions "
            + "look safe until one shock causes forced selling.",
            .risk, ["Tail Risk", "VIX"])

        add("Regime Multiplier",
            "A market-condition adjustment that raises or lowers confidence depending on "
            + "whether the broader market favours risk-taking.",
            "In a risk-off regime, a BUY signal may get a 0.85× multiplier; in a strong "
            + "trend regime, it may receive a positive adjustment.",
            .aiAnalysis, ["Market Regime", "Calibrated Confidence"])

        add("PCR",
            "Short for Put/Call Ratio — put option open interest divided by call option "
            + "open interest.",
            "A NIFTY PCR near 0.7 can show aggressive call writing or bullish positioning, "
            + "while extreme readings need confirmation from price action.",
            .marketMechanics, ["Put/Call Ratio", "Open Interest"])

        add("GEX",
            "Gamma exposure — an options-market measure of how dealer hedging can amplify "
            + "or dampen index moves near large option strikes.",
            "High positive GEX around 23,500 can pin NIFTY near that level; negative GEX "
            + "can make intraday moves sharper.",
            .marketMechanics, ["Open Interest", "PCR"])

        add("Delivery Percentage",
            "The share of traded volume that was taken into delivery instead of squared "
            + "off intraday. Higher delivery can indicate stronger accumulation.",
            "A price rise with delivery percentage above 55% is stronger than the same "
            + "move driven mostly by intraday trades.",
            .marketMechanics, ["Volume", "Bulk Deal"])

        add("Advance/Decline Breadth",
            "The number of advancing stocks compared with declining stocks. It shows "
            + "whether index moves are broad or narrow.",
            "If NIFTY is up but only 35% of stocks are advancing, breadth is weak and the "
            + "rally may be fragile.",
            .marketMechanics, ["Market Pulse", "Market Regime"])

        add("Market Pulse",
            "A quick read of current market internals such as index direction, breadth, "
            + "volatility, and sector participation.",
            "A positive Market Pulse combines rising indices, broad advances, lower VIX, "
            + "and leadership from multiple sectors.",
            .marketMechanics, ["Advance/Decline Breadth", "VIX", "Market Regime"])

        add("Momentum Scan",
            "A screen that looks for stocks or sectors with strong recent price movement, "
            + "volume confirmation, and trend quality.",
            "A Momentum Scan may surface stocks above their 50-DMA with rising volume and "
            + "positive relative strength versus NIFTY.",
            .charts, ["SMA", "Volume", "Nifty Benchmark"])

        add("Candlestick",
            "A chart mark showing open, high, low, and close for a period. The body shows "
            + "open-to-close movement; the wick shows the full traded range.",
            "A long lower wick after a sell-off can show buyers stepped in aggressively "
            + "near support.",
            .charts, ["Support", "Resistance", "Volume"])

        add("Period Return",
            "The percentage change between the first and last price in the selected chart "
            + "period.",
            "If a stock rises from ₹900 to ₹990 over the selected 3-month period, its "
            + "period return is +10%.",
            .charts, ["CAGR", "Absolute Return"])

        add("Nifty Benchmark",
            "A normalized NIFTY comparison line used to judge whether a stock is beating "
            + "or lagging the broader market.",
            "If the stock line rises faster than the NIFTY benchmark line, the stock is "
            + "showing relative strength.",
            .charts, ["Market Regime", "Period Return"])

        add("Golden Cross",
            "A bullish moving-average pattern where a shorter average, usually 50-DMA, "
            + "crosses above a longer average, usually 200-DMA.",
            "A 50-DMA crossing above the 200-DMA after months of base-building can confirm "
            + "a stronger medium-term trend.",
            .charts, ["50-DMA", "200-DMA", "SMA"])

        add("Death Cross",
            "A bearish moving-average pattern where a shorter average, usually 50-DMA, "
            + "crosses below a longer average, usually 200-DMA.",
            "A death cross after weak earnings warns that a downtrend may be broadening.",
            .charts, ["50-DMA", "200-DMA", "SMA"])

        add("RRG Quadrant",
            "Relative Rotation Graph quadrant showing whether a sector is leading, "
            + "weakening, lagging, or improving versus a benchmark.",
            "A sector moving from Improving to Leading on an RRG often signals strengthening "
            + "relative momentum.",
            .charts, ["Nifty Benchmark", "Momentum Scan"])

        add("PAT Margin",
            "Profit After Tax as a percentage of revenue. It shows how much final profit "
            + "the company keeps from each rupee of sales.",
            "PAT margin of 14% means the company keeps ₹14 as final profit for every ₹100 "
            + "of revenue after all costs and taxes.",
            .fundamentals, ["PAT", "Revenue", "Net Profit Margin"])

        add("Macro & Alternatives",
            "A dashboard view that combines macro indicators with non-equity signals such "
            + "as oil, currency, gold, bonds, and volatility.",
            "If USD/INR weakens, Brent rises, and bond yields climb together, Macro & "
            + "Alternatives may warn of pressure on import-heavy sectors.",
            .macro, ["Brent Crude", "USD/INR", "VIX"])

        add("Institutional Allocation",
            "How FIIs, DIIs, mutual funds, and other large investors are positioned across "
            + "stocks, sectors, or asset classes.",
            "Rising institutional allocation to banks while reducing IT exposure can signal "
            + "where professional capital expects better risk-adjusted returns.",
            .ownership, ["FII", "DII", "Institutional Ownership"])

        
        // ── Foundational Market Terms (Added for Layman Users) ────────
        add("SEBI",
            "Securities and Exchange Board of India — the regulatory body that oversees the Indian stock market and protects investors.",
            "If a company commits fraud or insider trading, SEBI is the authority that investigates and issues penalties.",
            .marketMechanics)

        add("Demat Account",
            "Dematerialised account — a digital account used to hold your shares and securities electronically instead of physical paper certificates.",
            "When you buy Reliance shares, the actual digital shares are credited to your Demat Account via depositories like NSDL or CDSL.",
            .marketMechanics)

        add("Trading Account",
            "An account with a stockbroker used to place buy and sell orders in the stock market.",
            "You use your Trading Account to place the order, and the shares are then stored in your Demat Account.",
            .marketMechanics)

        add("IPO",
            "Initial Public Offering — when a private company sells its shares to the public for the first time to raise capital.",
            "When a startup goes public via an IPO, retail investors can apply for shares before it lists on the exchange.",
            .marketMechanics)

        add("SIP",
            "Systematic Investment Plan — a method of investing a fixed amount regularly (e.g., monthly) into a mutual fund or stock.",
            "A ₹5,000 monthly SIP in a Nifty 50 index fund automates your investing and averages out market volatility over time.",
            .portfolio)

        add("Lumpsum",
            "A single, bulk investment made at one time rather than spreading it out over multiple smaller investments like an SIP.",
            "If you receive a ₹1L bonus and invest it all today, that is a lumpsum investment. It carries timing risk.",
            .portfolio)

        add("Mutual Fund",
            "A pool of money collected from many investors, managed by professionals to buy a diversified portfolio of stocks or bonds.",
            "Instead of picking 30 stocks yourself, you can buy an Equity Mutual Fund where a fund manager does the research.",
            .portfolio)

        add("LTCG",
            "Long Term Capital Gains — the profit made from selling an asset after holding it for longer than a specified period (typically 1 year for Indian equities).",
            "LTCG on Indian stocks is currently taxed at a lower rate than short-term gains, encouraging long-term investing.",
            .portfolio)

        add("STCG",
            "Short Term Capital Gains — the profit made from selling an asset held for a short period (typically less than 1 year).",
            "If you buy a stock and sell it for a profit 3 months later, that profit is STCG and taxed at a higher rate.",
            .portfolio)

        add("NIFTY 50",
            "The benchmark index of the National Stock Exchange (NSE) representing the top 50 largest and most liquid Indian companies.",
            "When people say 'the market is up today', they usually mean the NIFTY 50 index went up.",
            .macro)

        add("SENSEX",
            "The benchmark index of the Bombay Stock Exchange (BSE) representing 30 large, well-established companies.",
            "SENSEX was India's first major stock index. Like NIFTY, it serves as a barometer of the Indian economy.",
            .macro)

        add("NSE",
            "National Stock Exchange — the largest stock exchange in India by trading volume.",
            "Most retail traders prefer NSE due to its high liquidity and volume.",
            .marketMechanics)

        add("BSE",
            "Bombay Stock Exchange — Asia's oldest stock exchange, located in Mumbai.",
            "Many older or smaller companies are only listed on the BSE, though the top companies are listed on both NSE and BSE.",
            .marketMechanics)

        self.dict = d

    }

    private func normalize(_ string: String) -> String {
        return string.lowercased()
            .components(separatedBy: .punctuationCharacters)
            .joined()
            .components(separatedBy: .whitespaces)
            .joined()
    }

    /// Look up a term using fuzzy matching (ignoring punctuation and spacing). Returns nil if not found.
    func lookup(_ term: String) -> FinanceTerm? {
        let searchKey = normalize(term)
        
        // 1. Exact normalized match
        if let exact = dict.values.first(where: { normalize($0.term) == searchKey }) {
            return exact
        }
        
        // 2. Contains match (useful for acronyms)
        if let partial = dict.values.first(where: { normalize($0.term).contains(searchKey) || searchKey.contains(normalize($0.term)) }) {
            return partial
        }
        
        return nil
    }

    func termsByCategory(_ category: TermCategory) -> [FinanceTerm] {
        dict.values.filter { $0.category == category }.sorted { $0.term < $1.term }
    }

    func allTerms() -> [FinanceTerm] {
        dict.values.sorted { $0.term < $1.term }
    }
}
