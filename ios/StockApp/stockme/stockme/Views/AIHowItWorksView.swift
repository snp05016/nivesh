import SwiftUI

struct AIHowItWorksView: View {
    @State private var expandedStep: Int? = nil

    private let steps: [(icon: String, title: String, short: String, detail: String)] = [
        ("antenna.radiowaves.left.and.right", "Harvest Data",
         "Gathers real-time data about this stock",
         "Nivesh initiates a highly concurrent data harvesting process to fetch the latest market state. It simultaneously queries NSE servers for live price ticks, pulls deep historical trends, scrapes financial statements (balance sheet, cash flow, income statement), and extracts promoter pledging and shareholding patterns. Concurrently, it fetches the last 7 days of global and local news, scoring each headline through a FinBERT sentiment model to assess market tailwinds or headwinds. This rich, multi-dimensional dataset forms the foundational ground-truth for the AI agents."),
        ("bolt.fill", "Smart Cache Gate",
         "Computes staleness to save time",
         "Before engaging the heavy AI pipeline, the Smart Cache Gate computes a Staleness Score (0–100) based on three factors: Time Elapsed since last analysis, Price Volatility, and News Sentiment Shifts. If the score is below 20 (Fresh), Nivesh instantly serves the cached report (under 100ms). If it's between 20-44 (Aging), it might trigger a fast update via a smaller model. Only if the score exceeds 45, or if major corporate actions like stock splits or special dividends are detected, does the full deep-scan pipeline run."),
        ("brain.head.profile", "Analyst Committee",
         "Parallel execution of 5 specialized agents",
         "Nivesh deploys a LangGraph-based multi-agent framework. Five specialized AI agents analyze the data concurrently: The Market Analyst examines technical charts, RSI, MACD, and price action; The Sentiment Analyst gauges public mood and FinBERT scores; The News Analyst reads recent events and earnings calls; The Fundamentals Analyst breaks down P/E, ROE, debt, and computes the Piotroski F-Score; The Governance Analyst checks for promoter pledging risks, insider trading, and SEBI ASM/GSM lists. Each agent independently drafts a specialized report."),
        ("arrow.triangle.branch", "Dialectical Debate (Bull vs Bear)",
         "Adversarial testing of the investment thesis",
         "Nivesh employs Dialectical Asymmetry to protect your capital. A Bullish Researcher and a Bearish Researcher engage in a rigorous debate using the 5 committee reports as evidence. The Bear is deliberately given a 1.5× weight advantage and a longer, more critical prompt. The burden of proof strictly lies with the Bull. This adversarial setup ensures that any BUY signal has survived intense scrutiny regarding valuation risks, governance flags, and market headwinds."),
        ("person.text.rectangle.fill", "Portfolio Manager",
         "Synthesizes debate into a final verdict",
         "A senior AI Portfolio Manager agent reviews the entire debate transcript and all individual analyst reports. It evaluates the Bear's critiques against the Bull's defenses. Based on this synthesis, it assigns a final categorical signal: BUY, CAUTIOUSLY BULLISH, HOLD, CAUTIOUSLY BEARISH, or SELL. It also generates a confidence percentage (0-100%), sets precise 3-month, 12-month, and 36-month target prices, and drafts the definitive Bull Case, Bear Case, and Key Risks."),
        ("checkmark.seal.fill", "Normalization & Formatting",
         "Ensures architectural compliance",
         "The raw AI output is strictly validated against the Nivesh Architectural Ordinance. The payload passes through a JSON extraction pipeline to guarantee 20+ required fields exist with correct data types. A specialized filter completely bans Western numbering (Millions/Billions) and enforces Indian formats (Lakhs/Crores). Finally, all emojis are stripped for a professional Banknote Aesthetic, ensuring the report is structured, safe, and easily readable on your device."),
    ]

    private let factors: [(category: String, items: [String])] = [
        ("Price & Charts", ["Price momentum", "Moving averages (50-DMA, 200-DMA)", "RSI (overbought/oversold)", "Support & resistance levels", "Volume analysis"]),
        ("Company Fundamentals", ["Revenue & PAT growth", "P/E ratio vs industry", "ROE & ROCE", "Debt-to-equity ratio", "Free cash flow", "Piotroski F-Score"]),
        ("Ownership & Governance", ["Promoter holding & pledging", "FII & DII activity", "Insider transactions", "SEBI actions & ASM/GSM status", "Related-party transactions"]),
        ("Market Sentiment", ["News sentiment analysis", "Social media & retail mood", "Earnings call tone", "Brokerage upgrades/downgrades"]),
        ("Macro Economy", ["Crude oil prices", "USD/INR exchange rate", "RBI repo rate", "India VIX (fear index)", "FII/DII flow trends"]),
    ]

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)
            BanknoteWatermark(text: "AI", size: 100, opacity: 0.015, alignment: .center)

            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    header

                    VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                        Text("THE PIPELINE")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                            .tracking(1.5)
                            .foregroundStyle(Theme.inkTertiary)
                            .padding(.horizontal, Theme.screenPadding)

                        ForEach(Array(steps.enumerated()), id: \.offset) { idx, step in
                            stepCard(idx: idx, step: step)
                        }
                    }

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    durationSection

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    whatItAnalysesSection

                    Spacer(minLength: 80)
                }
                .padding(.top, Theme.Spacing.large)
            }
        }
        .navigationTitle("How AI Analysis Works")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("Nivesh uses a committee of 8 AI agents to analyse each stock through a dialectical debate process.")
                .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(5)
            Text("The Bear researcher is weighted 1.5× to be conservative — earning money is harder than losing it.")
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(4)
        }
        .padding(.horizontal, Theme.screenPadding)
    }

    private func stepCard(idx: Int, step: (icon: String, title: String, short: String, detail: String)) -> some View {
        let isExpanded = expandedStep == idx

        return Button {
            HapticManager.selection()
            withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                expandedStep = isExpanded ? nil : idx
            }
        } label: {
            VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                HStack(spacing: Theme.Spacing.standard) {
                    Text("\(idx + 1)")
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                        .foregroundStyle(Theme.securityGold)
                        .frame(width: 28, height: 28)
                        .background(Theme.securityGold.opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))

                    Image(systemName: step.icon)
                        .font(.title3)
                        .foregroundStyle(isExpanded ? Theme.securityGold : Theme.inkSecondary)
                        .frame(width: 28)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(step.title)
                            .font(Theme.engravedSerif(size: 15, weight: .semibold, relativeTo: .headline))
                            .foregroundStyle(Theme.inkPrimary)
                        if !isExpanded {
                            Text(step.short)
                                .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(1)
                        }
                    }

                    Spacer()

                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.inkTertiary)
                }

                if isExpanded {
                    Text(step.detail)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(5)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, Theme.Spacing.standard)
                        .padding(.leading, 60)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .padding(.horizontal, Theme.screenPadding)
    }

    private var durationSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("TYPICAL DURATION")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            HStack(spacing: Theme.Spacing.xSmall) {
                Text("Standard")
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .caption))
                    .foregroundStyle(Theme.bullGreen)
                Text("30–60 seconds")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                Text("·")
                    .foregroundStyle(Theme.inkTertiary)
                Text("Extreme")
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed)
                Text("3–5 minutes")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }

    private var whatItAnalysesSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("WHAT IT ANALYSES")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            ForEach(factors, id: \.category) { section in
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(section.category.uppercased())
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.securityGold)
                    ForEach(section.items, id: \.self) { item in
                        HStack(spacing: Theme.Spacing.small) {
                            Circle()
                                .fill(Theme.securityGold.opacity(0.5))
                                .frame(width: 4, height: 4)
                            Text(item)
                                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}
