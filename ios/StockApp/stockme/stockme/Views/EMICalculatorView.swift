import SwiftUI

// MARK: - EMI Calculator
//
// MOCK/DEMO — purely a local, offline projection tool. No loan application,
// disbursement, or backend call is involved; this only estimates a monthly
// instalment using the standard reducing-balance EMI formula.
//
// EMI = P * r * (1+r)^n / ((1+r)^n - 1)
//   P = principal (loan amount)
//   r = monthly interest rate = annual rate / 12 / 100
//   n = tenure in months
//
// Mirrors FixedDepositCalculatorView's shape (FDInputSlider + result card).
// Embedded only in CalculatorsView (Settings > Tools > Calculators).

/// Inline, self-contained EMI calculator body (sliders + result card) with
/// no NavigationStack of its own, embedded in CalculatorsView's tabbed container.
struct EMICalculatorContent: View {
    @State private var loanAmount: Double = 10_00_000
    @State private var interestRatePct: Double = 9.5
    @State private var tenureMonths: Double = 60

    private var result: EMICalculationResult {
        EMICalculationResult.computeLocally(
            principal: loanAmount,
            annualRatePct: interestRatePct,
            tenureMonths: Int(tenureMonths)
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
            FDInputSlider(
                title: "Loan Amount",
                value: $loanAmount,
                range: 50_000...1_00_00_000,
                step: 5_000,
                display: { IndianFormatter.formatLakhsCrores($0) }
            )
            FDInputSlider(
                title: "Interest Rate (p.a.)",
                value: $interestRatePct,
                range: 5...24,
                step: 0.1,
                display: { String(format: "%.1f%%", $0) }
            )
            FDInputSlider(
                title: "Tenure (Months)",
                value: $tenureMonths,
                range: 6...360,
                step: 1,
                display: { "\(Int($0)) mo" }
            )

            EMIResultCard(result: result)
        }
    }
}

struct EMICalculationResult: Equatable {
    let monthlyEMI: Double
    let totalInterest: Double
    let totalPayment: Double

    /// Standard reducing-balance EMI formula. Pure/local — no backend call.
    static func computeLocally(principal: Double, annualRatePct: Double, tenureMonths: Int) -> EMICalculationResult {
        let n = max(tenureMonths, 1)
        let r = (annualRatePct / 12.0) / 100.0

        let emi: Double
        if r == 0 {
            emi = principal / Double(n)
        } else {
            let factor = pow(1 + r, Double(n))
            emi = principal * r * factor / (factor - 1)
        }

        let totalPayment = emi * Double(n)
        let totalInterest = totalPayment - principal

        return EMICalculationResult(
            monthlyEMI: (emi * 100).rounded() / 100,
            totalInterest: (totalInterest * 100).rounded() / 100,
            totalPayment: (totalPayment * 100).rounded() / 100
        )
    }
}

private struct EMIResultCard: View {
    let result: EMICalculationResult

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Projected Instalment")
                .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            Text(IndianFormatter.formatLakhsCrores(result.monthlyEMI))
                .font(Theme.serialNumberFont(size: 28, relativeTo: .largeTitle))
                .foregroundColor(Theme.securityGold)
            Text("MONTHLY EMI")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.card) {
                EMIResultTile(label: "Total Interest", value: IndianFormatter.formatLakhsCrores(result.totalInterest), valueColor: Theme.bearRed)
                EMIResultTile(label: "Total Payment", value: IndianFormatter.formatLakhsCrores(result.totalPayment), valueColor: Theme.inkPrimary)
            }

            Text("Reducing-balance EMI projection — indicative only, actual terms depend on the lender.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct EMIResultTile: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                .foregroundColor(valueColor)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
