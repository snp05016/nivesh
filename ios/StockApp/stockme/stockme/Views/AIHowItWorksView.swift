import SwiftUI

struct AIHowItWorksView: View {
    @State private var expandedStep: Int? = nil

    private let steps: [(icon: String, title: String, short: String, detail: String)] = [
        ("antenna.radiowaves.left.and.right", "Harvest Data",
         "Gathers real-time data about this stock",
         "First, Nivesh gathers data from multiple sources: the latest stock price, recent news articles, company regulatory filings, promoter shareholding changes, FII and DII investment flows, insider trading disclosures, and broader market indicators like crude oil prices and the rupee. This ensures the analysis is based on current, complete information."),
        ("bolt.fill", "Smart Cache Gate",
         "Checks if fresh analysis already exists",
         "If the stock was analysed recently and nothing significant has changed — no major price moves, no news, no corporate actions — Nivesh can skip the full analysis and deliver results in under a second. This saves time and computing resources. The system computes a staleness score (0–100) based on data age, price movement, and signal mismatch."),
        ("brain.head.profile", "Analyst Committee",
         "5 AI agents examine the stock from different angles",
         "Five specialised AI agents each study the stock from their own perspective: the Market Analyst looks at price charts and trends; the Sentiment Analyst evaluates news tone and social mood; the News Analyst reads recent headlines and earnings calls; the Fundamentals Analyst examines financial ratios and balance sheets; and the Governance Analyst checks promoter activity, SEBI actions, and insider trading patterns. Each agent produces an independent report."),
        ("arrow.triangle.branch", "Bull vs Bear Debate",
         "Two opposing researchers argue the case",
         "Two AI researchers — one bullish, one bearish — debate the stock using all five analyst reports as evidence. The Bull argues why the stock might rise. The Bear argues why it might fall. The Bear's arguments are deliberately given 1.5× weight — this makes Nivesh more cautious with your money. Burden of proof lies with the optimistic case."),
        ("person.text.rectangle.fill", "Portfolio Manager",
         "Synthesises all views into one signal",
         "An experienced AI 'manager' reviews all five analyst reports plus the debate transcript. It weighs the evidence, considers the Bear's stronger weighting, and determines the final recommendation: BUY, CAUTIOUSLY BULLISH, HOLD, CAUTIOUSLY BEARISH, or SELL — along with a confidence percentage. This is the final output you see as your AI Signal."),
        ("checkmark.seal.fill", "Reformat & Verify",
         "Format check, Indian numbering, quality control",
         "The final report undergoes rigorous checks: all numbers are converted to Indian format (Lakhs and Crores — never Millions or Billions), emojis are stripped for professional presentation, and all 20+ required data fields are verified present. If any field is missing, a fallback value is inserted to ensure you always see a complete report."),
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
