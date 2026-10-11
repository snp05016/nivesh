import SwiftUI

// MARK: - Gratuity Calculator
//
// MOCK/DEMO — a simplified, offline estimate only. This is NOT tax or legal
// advice; it approximates the gratuity formula of the Code on Social Security,
// 2020 (Chapter V, which replaced the Payment of Gratuity Act, 1972) and the
// common 15/30 convention for non-covered establishments, and does not account
// for exemptions or employer-specific gratuity schemes. Always
// confirm actual entitlement with your employer/HR or a qualified advisor.
//
// Eligibility: 5 years of continuous service (1 year for fixed-term employees,
//   pro-rata); below that payable is ₹0, except on death or disablement.
// Covered: Gratuity = (Last Drawn Monthly Salary × 15 × Years) / 26,
//   where a final part-year of more than 6 months counts as a full year.
// Not covered: Gratuity = (Salary × 15 × Completed Years) / 30.
// Statutory ceiling (current): ₹20,00,000 — amounts above this are capped.

/// Slider inputs, owned by CalculatorsView so they survive tab switches.
struct GratuityInputs {
    var lastDrawnSalary: Double = 50_000
    var yearsOfService: Double = 10
    var extraMonths: Double = 0
    var coveredByAct = true
    var isFixedTerm = false
}

/// Inline, self-contained gratuity calculator body (sliders + result card)
/// with no NavigationStack of its own, embedded in CalculatorsView's tabbed
/// container (Settings > Tools > Calculators).
struct GratuityCalculatorContent: View {
    @Binding var inputs: GratuityInputs

    private var result: GratuityCalculationResult {
        GratuityCalculationResult.computeLocally(
            lastDrawnSalary: inputs.lastDrawnSalary,
            yearsOfService: Int(inputs.yearsOfService),
            months: Int(inputs.extraMonths),
            coveredByAct: inputs.coveredByAct,
            isFixedTerm: inputs.isFixedTerm
        )
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
            FDInputSlider(
                title: "Last Drawn Monthly Salary (Basic + DA)",
                value: $inputs.lastDrawnSalary,
                range: 5_000...10_00_000,
                step: 1_000,
                display: { IndianFormatter.formatLakhsCrores($0) }
            )
            FDInputSlider(
                title: "Years of Service",
                value: $inputs.yearsOfService,
                range: 0...45,
                step: 1,
                display: { "\(Int($0)) yr" }
            )
            FDInputSlider(
                title: "Additional Months",
                value: $inputs.extraMonths,
                range: 0...11,
                step: 1,
                display: { "\(Int($0)) mo" }
            )
            Toggle(isOn: $inputs.coveredByAct) {
                Text("Employer covered by the gratuity law (Social Security Code)")
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)
            Toggle(isOn: $inputs.isFixedTerm) {
                Text("Fixed-term employee (eligible after 1 year)")
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
            }
            .tint(Theme.securityGold)

            GratuityResultCard(result: result)
        }
    }
}

struct GratuityCalculationResult: Equatable {
    let uncappedGratuity: Double
    let payableGratuity: Double
    let isCapped: Bool
    /// False below the minimum continuous service (`minimumYears`, or
    /// `fixedTermMinimumYears` for fixed-term employees): nothing is payable
    /// then. This is the only implementation (the backend has no gratuity calculator).
    let isEligible: Bool

    /// Minimum continuous service for gratuity eligibility.
    static let minimumYears = 5
    /// Fixed-term employees qualify pro-rata after one year of service.
    static let fixedTermMinimumYears = 1

    /// Statutory ceiling under the Code on Social Security, 2020 (Chapter V)
    /// (current value as of this demo).
    static let statutoryCeiling: Double = 20_00_000

    /// Covered: (Salary × 15 × Years) / 26, a final part-year over 6 months
    /// counted as a full year. Not covered: (Salary × 15 × Completed Years) / 30.
    /// Payable is 0 below the minimum service; `uncappedGratuity` is still filled
    /// so the card can show the value that applies on death/disablement.
    /// Pure/local — simplified/demo estimate only, not tax or legal advice.
    static func computeLocally(
        lastDrawnSalary: Double,
        yearsOfService: Int,
        months: Int = 0,
        coveredByAct: Bool = true,
        isFixedTerm: Bool = false
    ) -> GratuityCalculationResult {
        let years = max(yearsOfService, 0)
        let extraMonths = min(max(months, 0), 11)
        let requiredYears = isFixedTerm ? fixedTermMinimumYears : minimumYears
        let isEligible = years * 12 + extraMonths >= requiredYears * 12
        let countedYears = coveredByAct && extraMonths > 6 ? years + 1 : years
        let uncapped = (lastDrawnSalary * 15 * Double(countedYears)) / (coveredByAct ? 26.0 : 30.0)
        let payable = isEligible ? min(uncapped, statutoryCeiling) : 0

        return GratuityCalculationResult(
            uncappedGratuity: (uncapped * 100).rounded() / 100,
            payableGratuity: (payable * 100).rounded() / 100,
            isCapped: isEligible && uncapped > statutoryCeiling,
            isEligible: isEligible
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
                    .foregroundColor(Theme.holdAmber)
                Text("Gratuity requires at least \(GratuityCalculationResult.minimumYears) years of continuous service (\(GratuityCalculationResult.fixedTermMinimumYears) year for fixed-term employees) under the Code on Social Security, 2020, except on death or disablement. Estimated value if eligible: \(IndianFormatter.formatLakhsCrores(min(result.uncappedGratuity, GratuityCalculationResult.statutoryCeiling))).")
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

            Text("Simplified estimate. Covered employers use 15/26 and count a final part-year over 6 months as a full year; others use 15/30 on completed years. Not tax or legal advice; confirm with your employer or an advisor.")
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
