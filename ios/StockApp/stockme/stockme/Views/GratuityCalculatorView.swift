import SwiftUI

// MARK: - Gratuity Calculator
//
// MOCK/DEMO — a simplified, offline estimate only. This is NOT tax or legal
// advice; it approximates the Payment of Gratuity Act, 1972 formula for
// employees covered under the Act and does not account for exemptions,
// employer-specific gratuity schemes, or non-covered establishments. Always
// confirm actual entitlement with your employer/HR or a qualified advisor.
//
// Gratuity = (Last Drawn Monthly Salary × 15 × Years of Service) / 26
// Statutory ceiling (current): ₹20,00,000 — amounts above this are capped.

/// Inline, self-contained gratuity calculator body (sliders + result card)
/// with no NavigationStack of its own, embedded in CalculatorsView's tabbed
/// container (Settings > Tools > Calculators).
struct GratuityCalculatorContent: View {
    @State private var lastDrawnSalary: Double = 50_000
    @State private var yearsOfService: Double = 10

    private var result: GratuityCalculationResult {
        GratuityCalculationResult.computeLocally(
            lastDrawnSalary: lastDrawnSalary,
            yearsOfService: Int(yearsOfService)
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
            FDInputSlider(
                title: "Last Drawn Monthly Salary (Basic + DA)",
                value: $lastDrawnSalary,
                range: 5_000...10_00_000,
                step: 1_000,
                display: { IndianFormatter.formatLakhsCrores($0) }
            )
            FDInputSlider(
                title: "Years of Service",
                value: $yearsOfService,
                range: 1...45,
                step: 1,
                display: { "\(Int($0)) yr" }
            )

            GratuityResultCard(result: result)
        }
    }
}

struct GratuityCalculationResult: Equatable {
    let uncappedGratuity: Double
    let payableGratuity: Double
    let isCapped: Bool
    /// False below `minimumYears` of continuous service: the Act pays
    /// nothing then (finance_calculators.calculate_gratuity mirrors this).
    let isEligible: Bool

    /// Section 4(1) minimum continuous service for gratuity eligibility.
    static let minimumYears = 5

    /// Statutory ceiling for employees covered under the Payment of
    /// Gratuity Act, 1972 (current value as of this demo).
    static let statutoryCeiling: Double = 20_00_000

    /// Gratuity = (Last Drawn Salary × 15 × Years of Service) / 26.
    /// Pure/local — simplified/demo estimate only, not tax or legal advice.
    static func computeLocally(lastDrawnSalary: Double, yearsOfService: Int) -> GratuityCalculationResult {
        let years = max(yearsOfService, 0)
        guard years >= minimumYears else {
            return GratuityCalculationResult(uncappedGratuity: 0, payableGratuity: 0, isCapped: false, isEligible: false)
        }
        let uncapped = (lastDrawnSalary * 15 * Double(years)) / 26.0
        let payable = min(uncapped, statutoryCeiling)

        return GratuityCalculationResult(
            uncappedGratuity: (uncapped * 100).rounded() / 100,
            payableGratuity: (payable * 100).rounded() / 100,
            isCapped: uncapped > statutoryCeiling,
            isEligible: true
        )
    }
}

private struct GratuityResultCard: View {
    let result: GratuityCalculationResult

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Estimated Gratuity")
                .font(Theme.engravedSerif(size: 16, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            if result.isEligible {
                Text(IndianFormatter.formatLakhsCrores(result.payableGratuity))
                    .font(Theme.serialNumberFont(size: 28, relativeTo: .largeTitle))
                    .foregroundColor(Theme.securityGold)
                Text("PAYABLE GRATUITY")
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundColor(Theme.inkTertiary)
            } else {
                Text("NOT ELIGIBLE")
                    .font(Theme.serialNumberFont(size: 28, relativeTo: .largeTitle))
                    .foregroundColor(Theme.inkSecondary)
                Text("Gratuity is payable after \(GratuityCalculationResult.minimumYears) years of continuous service. Exceptions: no minimum on death or disablement; fixed-term employees may qualify after 1 year under the Code on Social Security, 2020.")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }

            if result.isCapped {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text("UNCAPPED VALUE: \(IndianFormatter.formatLakhsCrores(result.uncappedGratuity))")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .tracking(1.0)
                        .foregroundColor(Theme.inkSecondary)
                    Text("Capped at the statutory ceiling of \(IndianFormatter.formatLakhsCrores(GratuityCalculationResult.statutoryCeiling)).")
                        .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                }
            }

            Text("Simplified estimate for employees covered under the Payment of Gratuity Act, 1972. Not tax or legal advice; confirm with your employer or an advisor.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
