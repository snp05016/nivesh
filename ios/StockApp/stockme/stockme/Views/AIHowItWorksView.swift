import SwiftUI

struct AIHowItWorksView: View {
    @State private var expandedStep: Int? = nil

    private let steps: [(icon: String, title: String, short: String, detail: String)] = [
        ("antenna.radiowaves.left.and.right", "Data Harvesting",
         "Gathers real-time data about this stock",
         "Nivesh initiates a highly concurrent data harvesting process to fetch the latest market state. It simultaneously queries NSE servers for live price ticks, pulls deep historical trends, scrapes financial statements, and extracts promoter pledging patterns. Concurrently, it fetches the last 7 days of global news, scoring each headline through a FinBERT sentiment model."),
        ("bolt.fill", "Smart Cache Gate",
         "Computes staleness to save time",
         "Before engaging the heavy pipeline, the Smart Cache Gate computes a Staleness Score (0–100) based on Time Elapsed, Price Volatility, and News Sentiment Shifts. If the score is below 20, Nivesh instantly serves the cached report. If it exceeds 45, the deep-scan pipeline runs."),
        ("function", "The Quantitative Engine",
         "Deterministic mathematical modeling",
         "Before any AI reads text, Nivesh's Machine Learning engine crunches the numbers. It computes the broader market volatility regime, mathematically bounds the target prices using historical standard deviation, and isolates exactly which financial features (like P/E or RSI) are driving the stock. This strict statistical layer entirely eliminates AI hallucination."),
        ("brain.head.profile", "The Analyst Committee",
         "Parallel execution of 5 specialized agents",
         "Once the mathematical probability is locked in, Nivesh deploys a LangGraph-based AI framework. Five specialized agents—Market, Sentiment, News, Fundamentals, and Governance—concurrently read through earnings calls, news, and SEBI filings to provide human-readable context explaining the 'why' behind the Quantitative Engine's math."),
        ("arrow.triangle.branch", "Dialectical Debate (Bull vs Bear)",
         "Adversarial testing of the investment thesis",
         "A Bullish Researcher and a Bearish Researcher engage in a rigorous debate. The Bear is deliberately given a 1.5× weight advantage and aggressively weaponizes any tail-risks flagged by the Quantitative Engine (like auditor resignations or excessive pledging). The burden of proof strictly lies with the Bull."),
        ("person.text.rectangle.fill", "The Portfolio Manager",
         "Final synthesis & Calibration",
         "A senior AI Portfolio Manager reviews the math and the debate transcript. It synthesizes the final report and outputs a 'Mathematically Calibrated Confidence' score. Unlike standard AI apps that simply guess, this confidence percentage is rigorously calibrated using Venn-Abers probabilities against historical backtests.")
    ]

    private let factors: [(category: String, items: [String])] = [
        ("Price & Charts", ["Price momentum", "Moving averages (50-DMA, 200-DMA)", "RSI (overbought/oversold)", "Support & resistance levels", "Volume analysis"]),
        ("Company Fundamentals", ["Revenue & PAT growth", "P/E ratio vs industry", "ROE & ROCE", "Debt-to-equity ratio", "Free cash flow", "Piotroski F-Score"]),
        ("Ownership & Governance", ["Promoter holding & pledging", "FII & DII activity", "Insider transactions", "SEBI actions & ASM/GSM status", "Related-party transactions"]),
        ("Market Sentiment", ["News sentiment analysis", "Social media & retail mood", "Earnings call tone", "Brokerage upgrades/downgrades"]),
        ("Macro Economy", ["Crude oil prices", "USD/INR exchange rate", "RBI repo rate", "India VIX (fear index)", "FII/DII flow trends"]),
    ]

    private let mathFormulas: [(title: String, formula: String, explanation: String)] = [
        ("Regime Volatility (HMM Proxy)", "σ_annual = StdDev(R_30d) × √252", "Calculates the 30-day trailing volatility. If σ > 22%, the backend triggers a 'Crisis Regime', automatically slashing fundamental confidence multipliers and pivoting to momentum features."),
        ("Conformal Price Bounds", "P_target = P_current × (1 ± (σ_daily × √63 × 1.645))", "Computes the 3-month (63 trading days) target price boundaries. It uses the 90% confidence Z-score (1.645) to guarantee targets are strictly bounded by historical variance, destroying LLM hallucination."),
        ("SHAP Base Score", "S_base = Σ (w_i × f_i) / n", "Aggregates structural features (Piotroski F-Score, RSI, Debt/Equity). Each feature f_i is mapped to a strictly bounded [-1.0, 1.0] modifier depending on historical correlation w_i."),
        ("Venn-Abers Calibration", "C_final = max(0.05, min(0.95, (S_base × R_mult) - T_penalty))", "The final calibrated probability. It takes the base SHAP score, multiplies it by the Regime Multiplier (R_mult), and subtracts absolute Tail Risk Penalties (T_penalty) like excessive promoter pledging.")
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

                    mathematicsSection

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
            Text("Nivesh uses a hybrid Quantitative Machine Learning framework combined with 8 AI agents to analyse each stock.")
                .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(5)
            Text("The math engine calculates the probabilities, and the AI committee debates the qualitative risks. The Bear researcher is weighted 1.5× to be conservative.")
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
                Text("1–3 seconds")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                Text("·")
                    .foregroundStyle(Theme.inkTertiary)
                Text("Deep Scan")
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed)
                Text("60–120 seconds")
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

    private var mathematicsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("THE BACKEND MATHEMATICS")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            VStack(spacing: Theme.Spacing.card) {
                ForEach(mathFormulas, id: \.title) { math in
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text(math.title.uppercased())
                            .font(Theme.microLabel(size: 8))
                            .foregroundStyle(Theme.securityGold)

                        Text(math.formula)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .body))
                            .foregroundStyle(Theme.bullGreen)
                            .padding(Theme.Spacing.small)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Theme.bullGreen.opacity(0.08))
                            .cornerRadius(Theme.CornerRadius.small)

                        Text(math.explanation)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(4)
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}
