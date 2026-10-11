import SwiftUI

// MARK: - Fixed Deposit Calculator (Standalone)
//
// MOCK DATA - simulated for demo purposes, not a real integration. Tries
// POST /api/fixed-deposits/calculator first and falls back to an identical
// local compound-interest formula (FixedDepositCalculatorViewModel.computeLocally)
// if that endpoint isn't reachable, so the calculator always works. Mirrors
// SIPCalculatorSheet's input-slider + result-card shape. Reachable from the
// Tools card (PortfolioToolsCard) and from the FD discovery list's toolbar
// "function" icon.

struct FixedDepositCalculatorView: View {
    @StateObject private var vm = FixedDepositCalculatorViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    Text("Project the maturity value of a fixed deposit before you book one.")
                        .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                        .foregroundColor(Theme.inkTertiary)

                    FDInputSlider(
                        title: "Principal Amount",
                        value: $vm.principal,
                        range: 5_000...50_00_000,
                        step: 5_000,
                        display: { IndianFormatter.formatLakhsCrores($0) }
                    )
                    FDInputSlider(
                        title: "Tenure (Months)",
                        value: Binding(
                            get: { Double(vm.tenureMonths) },
                            set: { vm.tenureMonths = Int($0) }
                        ),
                        range: 3...120,
                        step: 1,
                        display: { "\(Int($0)) mo" }
                    )
                    FDInputSlider(
                        title: "Interest Rate (p.a.)",
                        value: $vm.interestRatePct,
                        range: 3...12,
                        step: 0.1,
                        display: { String(format: "%.1f%%", $0) }
                    )

                    FDCalculatorResultCard(result: vm.result, isCalculating: vm.isCalculating)
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Fixed Deposit Calculator")
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
            .task { await vm.recalculate() }
            .onChange(of: vm.principal) { _, _ in Task { await vm.recalculate() } }
            .onChange(of: vm.tenureMonths) { _, _ in Task { await vm.recalculate() } }
            .onChange(of: vm.interestRatePct) { _, _ in Task { await vm.recalculate() } }
        }
    }
}

struct FDInputSlider: View {
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

struct FDCalculatorResultCard: View {
    let result: FDCalculatorResponse?
    let isCalculating: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Projected Outcome")
                .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            if let result {
                HStack(spacing: Theme.Spacing.card) {
                    FDResultTile(label: "Interest Earned", value: result.interestEarnedDisplay, valueColor: Theme.bullGreen)
                    FDResultTile(label: "Maturity Amount", value: result.maturityAmountDisplay, valueColor: Theme.securityGold, isLarge: true)
                }
            } else if isCalculating {
                ProgressView()
                    .tint(Theme.securityGold)
                    .frame(maxWidth: .infinity, minHeight: 60)
            }

            Text("Compound-interest projection — not a guarantee, and no real payment is collected here.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct FDResultTile: View {
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
