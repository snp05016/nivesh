# How Nivesh Analyses a Stock

*Written for Nirav — no tech background needed.*

---

## The Short Version

When you tap **Analyse** on any stock, the app sends that stock to a team of AI agents running on a computer. These agents read everything available about the company — price charts, financial reports, recent news, who owns what — and then argue with each other about whether the stock is a good buy or not. A senior AI then reads their full debate, weighs everything together, and gives you a structured opinion in plain English.

The whole process takes 30–90 seconds and costs roughly ₹15–30 in AI compute per analysis.

---

## Step by Step — What Actually Happens

### Step 1 — You tap Analyse

The app sends the stock ticker (for example, `SUZLON`) to the backend server. The server figures out the full ticker code (`SUZLON.NS` for NSE) and pulls the current date.

---

### Step 2 — Three Expert Analysts Go to Work (simultaneously)

Three separate AI agents run at the same time, each looking at a different angle. Think of them as three research analysts you hired:

---

#### Analyst 1 — The Charts Person (Market Analyst)

This analyst looks only at price data. No news, no financials — just the numbers on the chart.

He studies things like:

- **Price trend** — Is the stock going up, down, or sideways over the last few months?
- **50-day and 200-day moving averages** — Is the current price above or below its own historical average?
- **RSI (Relative Strength Index)** — Is the stock overbought or oversold?
- **Volume** — Are people buying in large quantities?
- **Support and resistance levels** — Where has the stock bounced from historically?

---

#### Analyst 2 — The News Person (News Analyst)

This analyst searches for recent news and events about the company. He specifically looks for things that could change the investment thesis.

He focuses on:

- **Company-specific news** — New orders, management interviews, etc.
- **Sector news** — Government policy changes, etc.
- **Corporate announcements** — ⚠️ He specifically hunts for **Red Flags**: auditor resignations, CFO/MD exits, and SEBI investigations.

---

#### Analyst 3 — The Fundamentals Person (Fundamentals Analyst)

This analyst goes through the actual financial documents — balance sheet, profit and loss statement.

He studies:

- **Revenue & Profit growth** — Is the company earning more?
- **Return on Equity (ROE)** — Is the company using money efficiently?
- **Debt-to-Equity** — How much has the company borrowed?
- **Promoter holding %** — High holding means founders have skin in the game.
- **Promoter pledging %** — ⚠️ Pledging above 30% is a major red flag (it means the promoter is under financial stress).

---

### Step 3 — The Bull and Bear Researchers Argue

After the three analysts finish their reports, two more AI agents read everything and argue:

- **Bull Researcher** makes the strongest possible case for *buying*.
- **Bear Researcher** makes the strongest possible case for *avoiding*.

They go back and forth to stress-test the investment idea.

---

### Step 4 — The Portfolio Manager Makes the Final Call

A senior AI reads everything — all the research, the debate, and the risk discussions — and gives you the final verdict. This is then formatted into the structured screen you see in the app.

The app uses **Claude 3.5 Sonnet** to apply strict **Indian Market Weighting**:

1. **Management quality** — Governance and promoter behaviour.
2. **Institutional activity** — Who is buying (FII/DII)?
3. **Indian Market Sentiment** — ⚠️ High retail/social media excitement is actually treated as a **cautionary signal** (cycle tops often happen when everyone is talking about a stock).
4. **Fundamentals** — Profits, debt, and margins.

---

## Superpowers — High-End Analysis

The app now includes "Superpowers" to help you manage your portfolio more safely:

### 1. Risk Analysis Engine
In your Assets tab, you'll see a **Portfolio Risk Card** with a 10-segment meter.
- **Low Risk (1-4 segments):** Your portfolio is stable.
- **Medium Risk (5-6 segments):** Balanced.
- **High Risk (7-10 segments):** You might be over-exposed to volatile stocks.
- **Correlation Warnings:** The app tells you if you own two stocks that move too similarly (e.g., owning too many banks), which increases your risk.

### 2. Red Flags System
This monitors your portfolio for **Governance Risks**. It uses color-coded flags:
- 🔴 **CRITICAL:** Auditor resignations, SEBI probes, or sudden CFO exits.
- 🟡 **WARNING:** Promoter pledging increasing or suspicious signal flips.
- 🔵 **WATCH:** Low AI confidence or minor data discrepancies.

### 3. Timing Insights
On the Home screen, a **Timeframe Conflicts** banner will appear if a stock's short-term price movement doesn't match its long-term potential. This is how the app identifies **"BUY THE DIP"** opportunities.

### 4. Trade Journal
You can now log your trade decisions in the **Trade Journal** tab. It's designed to help you track your "psychology" — whether you bought because of **FOMO**, a **Contrarian** view, or high **Confidence**. Stamping these entries helps you learn from your mistakes over time.

---

## What the AI Cannot Do

- **It cannot predict the future.** It gives a probability-weighted opinion.
- **It is not a SEBI-registered advisor.** Use this as one input, not the only one.
- **Promoter data can lag.** While the AI tries its best, some financial data might be a few days behind.

---

*Built with love for Nirav's portfolio. — Saumya*
