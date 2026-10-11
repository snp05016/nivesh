import SwiftUI

// MARK: - SIP Calculator

/// Systematic Investment Plan projection sheet, launched from a fund's
/// detail screen. Computed locally via SIPCalculationResult.computeLocally
/// (same formula as backend mutual_fund_calculators.py; no backend route).
struct SIPCalculatorSheet: View {
    let fund: MutualFundDTO
    @Environment(\.dismiss) private var dismiss

    @State private var monthlyAmount: Double = 5_000
    @State private var years: Double = 10
    @State private var assumedReturnPct: Double
    @State private var result: SIPCalculationResult?

    init(fund: MutualFundDTO) {
        self.fund = fund
        _assumedReturnPct = State(initialValue: fund.returns3y ?? fund.returns1y ?? 12)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    SIPFundBanner(fund: fund)

                    SIPInputSlider(
                        title: "Monthly SIP Amount",
                        value: $monthlyAmount,
                        range: 500...100_000,
                        step: 500,
                        display: { IndianFormatter.formatLakhsCrores($0) }
                    )
                    SIPInputSlider(
                        title: "Investment Tenure (Years)",
                        value: $years,
                        range: 1...30,
                        step: 1,
                        display: { "\(Int($0)) yr" }
                    )
                    SIPInputSlider(
                        title: "Expected Annual Return",
                        value: $assumedReturnPct,
                        range: 1...30,
                        step: 0.5,
                        display: { String(format: "%.1f%%", $0) }
                    )

                    SIPResultCard(result: result)
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("SIP Calculator")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundStyle(Theme.securityGold)
                }
            }
            .onAppear { recalculate() }
            .onChange(of: monthlyAmount) { _, _ in recalculate() }
            .onChange(of: years) { _, _ in recalculate() }
            .onChange(of: assumedReturnPct) { _, _ in recalculate() }
        }
    }

    private func recalculate() {
        result = SIPCalculationResult.computeLocally(
            monthlyAmount: monthlyAmount, annualReturnPct: assumedReturnPct, years: years
        )
    }
}

private struct SIPFundBanner: View {
    let fund: MutualFundDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(fund.fundName)
                .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(2)
            Text("Projection assumes constant monthly compounding — not a guarantee of future returns.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                .foregroundColor(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct SIPInputSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let display: (Double) -> String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                    .tracking(1.5)
                    .foregroundColor(Theme.inkSecondary)
                Spacer()
                Text(display(value))
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                    .foregroundColor(Theme.securityGold)
            }
            Slider(value: $value, in: range, step: step)
                .tint(Theme.securityGold)
                .accessibilityLabel(title)
                .accessibilityValue(display(value))
        }
    }
}

private struct SIPResultCard: View {
    let result: SIPCalculationResult?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Projected Outcome")
                .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            if let result {
                HStack(spacing: Theme.Spacing.card) {
                    SIPResultTile(label: "Invested", value: IndianFormatter.formatLakhsCrores(result.investedAmount))
                    SIPResultTile(label: "Est. Returns", value: IndianFormatter.formatLakhsCrores(result.estimatedReturns), valueColor: Theme.bullGreen)
                }
                SIPResultTile(label: "Maturity Value", value: IndianFormatter.formatLakhsCrores(result.totalValue), valueColor: Theme.securityGold, isLarge: true)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct SIPResultTile: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary
    var isLarge: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: isLarge ? 22 : 16, relativeTo: isLarge ? .title2 : .headline))
                .foregroundColor(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
