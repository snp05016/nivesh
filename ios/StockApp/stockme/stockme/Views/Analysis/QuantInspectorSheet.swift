import SwiftUI

struct QuantInspectorSheet: View {
    let analysis: StockAnalysis

    private var breakdown: [String: Double]? {
        guard let values = analysis.confidenceMathBreakdown, !values.isEmpty else {
            return nil
        }
        return values
    }

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()
            DenominationBackground(denomination: .hundred)
                .opacity(0.28)
                .allowsHitTesting(false)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    QuantInspectorHeader(ticker: analysis.ticker)

                    if let breakdown {
                        QuantLedgerCard(
                            breakdown: breakdown,
                            marketRegime: analysis.marketRegime,
                            lowerBound: analysis.conformalTargetLower3m,
                            upperBound: analysis.conformalTargetUpper3m
                        )
                        QuantGlossaryCard()
                    } else {
                        QuantInspectorEmptyState()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.vertical, Theme.Spacing.screen)
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }
}

private struct QuantInspectorHeader: View {
    let ticker: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("QUANTITATIVE ENGINE LOG")
                .font(Theme.officialStampFont(size: 13, relativeTo: .headline))
                .tracking(2)
                .foregroundStyle(Theme.inkPrimary)
            Text(ticker.uppercased())
                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                .foregroundStyle(Theme.securityGold)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct QuantLedgerCard: View {
    let breakdown: [String: Double]
    let marketRegime: String?
    let lowerBound: Double?
    let upperBound: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            QuantLedgerRow(
                label: "Base Probability",
                value: probability("base_probability")
            )
            QuantLedgerRow(
                label: "SHAP Drivers Adjustment",
                value: signedProbability("net_shap_adjustment")
            )
            QuantLedgerRow(
                label: regimeLabel,
                value: multiplier("regime_multiplier")
            )
            QuantLedgerRow(
                label: "Tail Risk Penalties",
                value: penalty("tail_risk_deduction")
            )

            GuillocheDivider()

            QuantLedgerRow(
                label: "Calibrated Confidence",
                value: probability("final_calibrated_confidence"),
                isTotal: true
            )

            if let lowerBound, let upperBound, lowerBound > 0, upperBound > 0 {
                QuantBoundsContext(lowerBound: lowerBound, upperBound: upperBound)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private var regimeLabel: String {
        guard let marketRegime, !marketRegime.isEmpty else {
            return "Regime Multiplier"
        }
        let shortRegime = marketRegime.components(separatedBy: " / ").first ?? marketRegime
        return "Regime Multiplier (\(shortRegime))"
    }

    private func value(_ key: String) -> Double {
        breakdown[key] ?? 0.0
    }

    private func probability(_ key: String) -> String {
        String(format: "%.2f", value(key))
    }

    private func signedProbability(_ key: String) -> String {
        let amount = value(key)
        return String(format: "%+.2f", amount)
    }

    private func multiplier(_ key: String) -> String {
        String(format: "x%.2f", value(key))
    }

    private func penalty(_ key: String) -> String {
        String(format: "-%.2f", abs(value(key)))
    }
}

private struct QuantLedgerRow: View {
    let label: String
    let value: String
    var isTotal = false

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.engravedSerif(size: isTotal ? 15 : 13, weight: isTotal ? .bold : .regular, relativeTo: .body))
                .foregroundStyle(isTotal ? Theme.inkPrimary : Theme.inkSecondary)
                .lineLimit(2)
            Rectangle()
                .fill(Theme.inkTertiary.opacity(0.18))
                .frame(height: 1)
            Text(value)
                .font(Theme.serialNumberFont(size: isTotal ? 16 : 14, relativeTo: .body))
                .foregroundStyle(isTotal ? Theme.securityGold : Theme.inkPrimary)
                .monospacedDigit()
        }
    }
}

private struct QuantBoundsContext: View {
    let lowerBound: Double
    let upperBound: Double

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text("3M VOLATILITY RANGE (≈90%)")
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            HStack(spacing: Theme.Spacing.small) {
                Text(IndianFormatter.price(lowerBound))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed)
                Text("to")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
                Text(IndianFormatter.price(upperBound))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.bullGreen)
            }
        }
        .padding(.top, Theme.Spacing.small)
    }
}

private struct QuantGlossaryCard: View {
    private let items: [(title: String, detail: String)] = [
        (
            "Base Probability",
            "The mathematical starting point before any market conditions are applied."
        ),
        (
            "SHAP Adjustments",
            "How much specific indicators like P/E ratio or RSI pushed the score up or down."
        ),
        (
            "Regime Multiplier",
            "A mathematical penalty or boost applied from broader market volatility. High volatility discounts fundamental scores."
        ),
        (
            "Tail Risk Penalties",
            "Large mathematical deductions triggered by severe red flags like excessive promoter pledging or auditor resignations."
        ),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("GLOSSARY")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundStyle(Theme.inkPrimary)

            ForEach(items, id: \.title) { item in
                QuantGlossaryRow(title: item.title, detail: item.detail)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct QuantGlossaryRow: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundStyle(Theme.securityGold)
            Text(detail)
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(4)
        }
    }
}

private struct QuantInspectorEmptyState: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Image(systemName: "function")
                .font(.title2)
                .foregroundStyle(Theme.securityGold)
            Text("Mathematical breakdown unavailable for legacy reports. Please tap Refresh Analysis to run the new Quantitative Engine.")
                .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(5)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
