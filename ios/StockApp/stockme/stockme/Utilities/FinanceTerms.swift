import Foundation

/// A single financial term with its definition and a real-world example.
struct FinanceTerm: Codable {
    let term: String
    let definition: String
    let example: String
}

/// Singleton dictionary of financial terms used across the app.
/// Keys are lowercase, whitespace-normalized for fuzzy matching.
final class FinanceTerms {
    static let shared = FinanceTerms()

    private let dict: [String: FinanceTerm]

    private init() {
        var d: [String: FinanceTerm] = [:]

        func add(_ t: String, _ def: String, _ ex: String) {
            let key = t.lowercased().trimmingCharacters(in: .whitespaces)
            d[key] = FinanceTerm(term: t, definition: def, example: ex)
        }

        // ── Technical Indicators ──────────────────────────────────────
        add("RSI",
            "Relative Strength Index — a momentum oscillator measuring speed and magnitude "
            + "of recent price changes. Ranges 0–100.",
            "RSI above 70 = overbought (price may pull back). RSI below 30 = oversold "
            + "(price may bounce). RELIANCE RSI at 74 signals caution.")

        add("MACD",
            "Moving Average Convergence Divergence — tracks the relationship between two "
            + "exponential moving averages (12-day and 26-day) of a stock's price.",
            "When the MACD line crosses above the signal line, it's a bullish signal. "
            + "TCS showed a MACD crossover on 3 Jan, rose 8% over the next 3 weeks.")

        add("SMA",
            "Simple Moving Average — the arithmetic mean of a stock's closing prices over "
            + "N days. Smooths out short-term noise.",
            "50-day SMA for RELIANCE = ₹2,760. Price currently ₹2,847 = trading above its "
            + "50-day average, which is a bullish sign.")

        add("EMA",
            "Exponential Moving Average — like SMA but gives more weight to recent prices, "
            + "reacting faster to price changes.",
            "12-day EMA responds faster to new prices than 50-day SMA. MACD is built from "
            + "the difference between 12-day EMA and 26-day EMA.")

        // ── Valuation Metrics ──────────────────────────────────────────
        add("P/E Ratio",
            "Price-to-Earnings ratio — how much investors pay per rupee of annual profit. "
            + "Higher P/E = investors expect faster growth.",
            "HDFCBANK trades at P/E 18×. If it earns ₹100/share, the stock costs ₹1,800. "
            + "NIFTY 50 average P/E is ~22×.")

        add("P/E",
            "Price-to-Earnings ratio — how much investors pay per rupee of annual profit. "
            + "Higher P/E = investors expect faster growth.",
            "HDFCBANK trades at P/E 18×. If it earns ₹100/share, the stock costs ₹1,800. "
            + "NIFTY 50 average P/E is ~22×.")

        add("EPS",
            "Earnings Per Share — the company's net profit divided by total shares outstanding. "
            + "Higher EPS means more profit for each share you hold.",
            "TCS EPS ₹122 this quarter. If you hold 10 shares, TCS earned ₹1,220 on your behalf.")

        add("ROE",
            "Return on Equity — how efficiently a company uses shareholder money to generate "
            + "profit. Expressed as a percentage.",
            "HDFCBANK ROE 16% means: for every ₹100 of shareholder equity, it earns ₹16 profit. "
            + "Above 15% is generally considered strong.")

        add("EBITDA",
            "Earnings Before Interest, Taxes, Depreciation and Amortisation — a proxy for "
            + "operating cash flow before financing and accounting decisions.",
            "RELIANCE EBITDA ₹1.8L Cr means its core businesses generated that much operating "
            + "profit before paying interest and taxes.")

        // ── Market Participants ────────────────────────────────────────
        add("FII",
            "Foreign Institutional Investor — overseas funds (pension funds, hedge funds, "
            + "mutual funds) that invest in Indian markets.",
            "FIIs bought ₹8,200 Cr of Indian equities last month. Heavy FII buying often "
            + "signals confidence in India's growth story.")

        add("DII",
            "Domestic Institutional Investor — Indian institutions (LIC, mutual funds, banks) "
            + "investing in Indian equities.",
            "When FIIs sell, DIIs often absorb the selling. In Oct 2023, DIIs bought ₹12,000 Cr "
            + "net while FIIs sold ₹8,000 Cr — markets stayed stable.")

        // ── Risk & Volatility ──────────────────────────────────────────
        add("Beta",
            "Measures how much a stock moves relative to the market. Beta 1 = moves with "
            + "NIFTY. Beta > 1 = more volatile. Beta < 1 = more stable.",
            "TATAMOTORS Beta 1.4 — if NIFTY falls 5%, TATAMOTORS typically falls ~7%. "
            + "HDFCBANK Beta 0.9 — more defensive.")

        add("VIX",
            "India VIX — the 'Fear Index'. Measures expected market volatility over the "
            + "next 30 days derived from NIFTY options prices.",
            "VIX at 12 = calm markets. VIX spiking to 25+ = panic buying of puts, expect "
            + "large NIFTY swings. Historically, VIX spikes are buying opportunities.")

        // ── Returns & Performance ──────────────────────────────────────
        add("CAGR",
            "Compound Annual Growth Rate — the steady annual return rate that would take an "
            + "investment from its starting value to its ending value.",
            "₹1L invested in INFY 5 years ago is now ₹1.95L. CAGR = 14.3% per year. "
            + "Better than FD (6.5% CAGR) but with higher risk.")

        add("XIRR",
            "Extended Internal Rate of Return — the actual annualised return on your "
            + "portfolio accounting for the exact timing of every buy and sell.",
            "Even if a stock is up 40%, your XIRR may be 22% if you added more money at the peak. "
            + "XIRR is the only honest way to measure your personal returns.")

        // ── Fundamental Health ─────────────────────────────────────────
        add("Piotroski Score",
            "A 0–9 scoring system for a company's financial health. Scores 8–9 = financially "
            + "strong. Scores 0–2 = financially weak. Based on profitability, leverage, and "
            + "operating efficiency metrics.",
            "HDFCBANK Piotroski Score 8 — strong earnings, declining debt, growing margins. "
            + "A score of 2 on a stock you hold is a red flag.")

        // ── Price Benchmarks ───────────────────────────────────────────
        add("52W High",
            "The highest price a stock traded at in the last 52 weeks (1 year).",
            "RELIANCE 52W High ₹3,124. Current price ₹2,847 = trading 8.9% below its yearly "
            + "peak. Some investors see this as a discount entry.")

        add("52W Low",
            "The lowest price a stock traded at in the last 52 weeks.",
            "TATAMOTORS 52W Low ₹802. It has rallied 22% from that bottom. Sustained recovery "
            + "above 52W Low suggests the sell-off phase is over.")

        add("52-Week High",
            "The highest price a stock traded at in the last 52 weeks (1 year).",
            "RELIANCE 52W High ₹3,124. Current price ₹2,847 = trading 8.9% below its yearly peak.")

        add("52-Week Low",
            "The lowest price a stock traded at in the last 52 weeks.",
            "TATAMOTORS 52W Low ₹802. It has rallied 22% from that bottom.")

        // ── Market Structure ───────────────────────────────────────────
        add("Market Cap",
            "Total market value of a company — current stock price × total shares outstanding. "
            + "Determines if it's large-cap, mid-cap or small-cap.",
            "RELIANCE Market Cap ₹19.8L Cr = largest listed company in India. NIFTY 50 "
            + "includes only large-cap companies above ~₹20,000 Cr.")

        // ── Derivatives ────────────────────────────────────────────────
        add("Open Interest",
            "The total number of outstanding derivative contracts (options or futures) that "
            + "have not been settled. Higher OI = more active participation.",
            "NIFTY 23,000 Call OI rose 8L contracts. This means more traders are betting NIFTY "
            + "will NOT cross 23,000 — acts as a resistance level.")

        add("Put/Call Ratio",
            "Total Put open interest divided by total Call open interest. A ratio above 1 "
            + "means more bearish bets. Below 1 means more bullish bets.",
            "PCR 1.3 for BANKNIFTY = more puts than calls, meaning institutional hedges are "
            + "high. Contrarians read this as a bullish signal.")

        // ── Market Mechanics ───────────────────────────────────────────
        add("Circuit Breaker",
            "A regulatory halt triggered when a stock moves up or down by a set percentage "
            + "in a single session. Upper circuit = price locked at the limit up.",
            "A small-cap stock hit 20% upper circuit — it cannot trade higher today regardless "
            + "of demand. Check if this is news-driven or operator activity.")

        add("Bulk Deal",
            "A single trade of more than 0.5% of a company's total shares in one session. "
            + "Must be disclosed to the exchange on the day of the trade.",
            "LIC bought 1.2% of BAJFINANCE in a bulk deal at ₹6,800. When LIC accumulates, "
            + "it's often read as a long-term confidence signal.")

        // ── Balance Sheet ─────────────────────────────────────────────
        add("Debt/Equity",
            "Total debt divided by shareholders' equity. Lower is generally safer. "
            + "Shows how leveraged a company is.",
            "TATAMOTORS D/E 1.8 = it owes ₹1.80 for every ₹1 of equity — highly leveraged. "
            + "INFY D/E 0.02 — virtually debt-free, much safer balance sheet.")

        add("D/E Ratio",
            "Total debt divided by shareholders' equity. Lower is generally safer. "
            + "Shows how leveraged a company is.",
            "TATAMOTORS D/E 1.8 — highly leveraged. INFY D/E 0.02 — virtually debt-free.")

        add("Dividend Yield",
            "Annual dividend per share divided by current share price, expressed as a %. "
            + "Shows the cash income you earn just for holding the stock.",
            "ITC pays ₹6.75 dividend. Share price ₹438 → Dividend Yield 1.54%. "
            + "If ITC were a bank FD, you'd compare this to the FD interest rate.")

        add("Free Cash Flow",
            "Cash a company generates after paying for capital expenditure — the actual "
            + "money left over that can be returned to shareholders or invested.",
            "RELIANCE generated ₹48,000 Cr FCF last year. This funds Jio expansion, retail "
            + "growth AND share buybacks — without needing to borrow.")

        add("Promoter Pledging",
            "When promoters (founders/major shareholders) pledge their shares as collateral "
            + "for loans. High pledging is a risk — forced selling if stock falls.",
            "If a promoter pledges 60% of their holding and the stock drops sharply, lenders "
            + "can sell those shares, causing further price collapse. Always check.")

        add("Promoter",
            "The founders or controlling shareholders of a company. High promoter holding "
            + "signals alignment with minority shareholders.",
            "TCS promoter (Tata Group) holds 72% — strong alignment. Low promoter holding "
            + "below 30% can signal weak commitment.")

        add("Institution",
            "Institutional investors — FIIs, DIIs, mutual funds, insurance companies that "
            + "invest large pools of capital with professional management.",
            "High institutional holding (above 40%) indicates professional confidence in the "
            + "stock. But coordinated selling can cause sharp falls.")

        add("Confidence Score",
            "A 0–100 score representing the AI model's confidence in its BUY/SELL/HOLD "
            + "recommendation. Higher = more conviction.",
            "Confidence score 85 on a SELL signal = the model is very certain of downside. "
            + "Score 55 on BUY = marginal conviction, more research warranted.")

        add("Upside",
            "The potential percentage gain from the current price to the target price. "
            + "Higher upside = more potential profit, but also typically higher risk.",
            "3-month target ₹3,200 vs current ₹2,847 = 12.4% upside. Long-term 36-month "
            + "target shows the analyst's multi-year view.")

        self.dict = d
    }

    /// Look up a term case-insensitively. Returns nil if not found.
    func lookup(_ term: String) -> FinanceTerm? {
        let key = term.lowercased().trimmingCharacters(in: .whitespaces)
        return dict[key]
    }
}
