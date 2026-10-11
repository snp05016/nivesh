import SwiftUI

// MARK: - Unified Calculators
//
// Container tying together the EMI, SIP, and Gratuity calculators as tabs
// inside a single sheet (single NavigationStack — each tab's content view
// has none of its own so there's no nested-stack conflict). All three tabs
// are LOCAL-ONLY projections; no backend call is made from this container.

private enum CalculatorTab: String, CaseIterable, Identifiable {
    case emi = "EMI"
    case sip = "SIP"
    case gratuity = "Gratuity"

    var id: String { rawValue }
}

struct CalculatorsView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var selectedTab: CalculatorTab = .emi
    // Held here, not in the tab views, so inputs survive switching tabs.
    @State private var emi = EMIInputs()
    @State private var sip = SIPInputs()
    @State private var gratuity = GratuityInputs()

    var body: some View {
        NavigationStack {
            VStack(spacing: Theme.Spacing.none) {
                Picker("Calculator", selection: $selectedTab) {
                    ForEach(CalculatorTab.allCases) { tab in
                        Text(tab.rawValue).tag(tab)
                    }
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.standard)
                .onChange(of: selectedTab) { _, _ in
                    HapticManager.selection()
                }

                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                        switch selectedTab {
                        case .emi:
                            Text("Estimate your monthly instalment before applying for a loan.")
                                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                                .foregroundColor(Theme.inkTertiary)
                            EMICalculatorContent(inputs: $emi)
                        case .sip:
                            Text("Project systematic investment returns assuming constant monthly compounding.")
                                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                                .foregroundColor(Theme.inkTertiary)
                            GenericSIPCalculatorContent(inputs: $sip)
                        case .gratuity:
                            Text("Estimate your gratuity payout under the Code on Social Security, 2020 (Chapter V).")
                                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                                .foregroundColor(Theme.inkTertiary)
                            GratuityCalculatorContent(inputs: $gratuity)
                        }
                    }
                    .padding(Theme.screenPadding)
                }
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Calculators")
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
        }
    }
}

private struct SIPInputs {
    var monthlyAmount: Double = 5_000
    var years: Double = 10
    var assumedReturnPct: Double = 12
}

/// Generic SIP tab — reuses SIPCalculationResult.computeLocally (already a
/// pure, fund-agnostic static function) so no fund selection is required.
private struct GenericSIPCalculatorContent: View {
    @Binding var inputs: SIPInputs

    private var result: SIPCalculationResult {
        SIPCalculationResult.computeLocally(
            monthlyAmount: inputs.monthlyAmount, annualReturnPct: inputs.assumedReturnPct, years: inputs.years
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
            FDInputSlider(
                title: "Monthly SIP Amount",
                value: $inputs.monthlyAmount,
                range: 500...1_00_000,
                step: 500,
                display: { IndianFormatter.formatLakhsCrores($0) }
            )
            FDInputSlider(
                title: "Investment Tenure (Years)",
                value: $inputs.years,
                range: 1...30,
                step: 1,
                display: { "\(Int($0)) yr" }
            )
            FDInputSlider(
                title: "Expected Annual Return",
                value: $inputs.assumedReturnPct,
                range: 1...30,
                step: 0.5,
                display: { String(format: "%.1f%%", $0) }
            )

            GenericSIPResultCard(result: result)
        }
    }
}

private struct GenericSIPResultCard: View {
    let result: SIPCalculationResult

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Projected Outcome")
                .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            HStack(spacing: Theme.Spacing.card) {
                GenericSIPResultTile(label: "Invested", value: IndianFormatter.formatLakhsCrores(result.investedAmount))
                GenericSIPResultTile(label: "Est. Returns", value: IndianFormatter.formatLakhsCrores(result.estimatedReturns), valueColor: Theme.bullGreen)
            }
            GenericSIPResultTile(label: "Maturity Value", value: IndianFormatter.formatLakhsCrores(result.totalValue), valueColor: Theme.securityGold, isLarge: true)

            Text("Projection assumes constant monthly compounding — not a guarantee of future returns.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct GenericSIPResultTile: View {
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
