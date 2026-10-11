import SwiftUI

// MARK: - Models

struct BenchmarkData: Codable {
    let portfolio_cagr: Double?
    let benchmark_cagr: Double?
    let alpha: Double?
    let tracking_error: Double?
    let information_ratio: Double?
}

struct SIPResult: Codable {
    let total_investment: Double?
    let maturity_value: Double?
    let total_gain: Double?
    let yearly_breakdown: [SIPYearRow]?
}

struct SIPYearRow: Codable, Identifiable {
    var id: String { "\(year ?? 0)" }
    let year: Int?
    let invested: Double?
    let value: Double?
}

// MARK: - Portfolio Tools Card

struct PortfolioToolsCard: View {
    let userId: Int

    @State private var showSIPSheet = false
    @State private var showFDCalculatorSheet = false
    @State private var showCalculatorsSheet = false
    @State private var showBenchmarkSheet = false
    @State private var isExportingPDF = false
    @State private var isLoadingBenchmark = false
    @State private var exportedPDFURL: URL? = nil
    @State private var showShareSheet = false
    @State private var exportError: String? = nil
    @State private var benchmarkData: BenchmarkData? = nil
    @State private var benchmarkError: String? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack {
                Text("TOOLS")
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)
                Spacer()
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)

            GuillocheDivider()
                .padding(.horizontal, Theme.Spacing.card)

            VStack(spacing: Theme.Spacing.none) {
                ToolButtonRow(
                    icon: "chart.line.uptrend.xyaxis",
                    title: "SIP Calculator",
                    subtitle: "Project systematic investment returns",
                    isLoading: false
                ) {
                    HapticManager.selection()
                    showSIPSheet = true
                }

                GuillocheDivider()
                    .padding(.horizontal, Theme.Spacing.card)

                ToolButtonRow(
                    icon: "doc.richtext",
                    title: "Export PDF",
                    subtitle: "Download portfolio report",
                    isLoading: isExportingPDF
                ) {
                    HapticManager.selection()
                    exportPDF()
                }

                if let exportError {
                    Text(exportError)
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.bearRed)
                        .padding(.horizontal, Theme.Spacing.card)
                        .padding(.bottom, Theme.Spacing.standard)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }

                GuillocheDivider()
                    .padding(.horizontal, Theme.Spacing.card)

                ToolButtonRow(
                    icon: "chart.bar.xaxis.ascending",
                    title: "Benchmark Comparison",
                    subtitle: "Compare against Nifty 50",
                    isLoading: isLoadingBenchmark
                ) {
                    HapticManager.selection()
                    fetchBenchmark()
                }

                GuillocheDivider()
                    .padding(.horizontal, Theme.Spacing.card)

                ToolButtonRow(
                    icon: "banknote.fill",
                    title: "Fixed Deposit Calculator",
                    subtitle: "Project FD maturity value",
                    isLoading: false
                ) {
                    HapticManager.selection()
                    showFDCalculatorSheet = true
                }

                GuillocheDivider()
                    .padding(.horizontal, Theme.Spacing.card)

                ToolButtonRow(
                    icon: "function",
                    title: "Calculators",
                    subtitle: "EMI, SIP & Gratuity estimates",
                    isLoading: false
                ) {
                    HapticManager.selection()
                    showCalculatorsSheet = true
                }
            }
            .padding(.bottom, Theme.Spacing.medium)
        }
        .banknoteCard()
        .sheet(isPresented: $showSIPSheet) {
            PortfolioSIPCalculatorSheet()
        }
        .sheet(isPresented: $showFDCalculatorSheet) {
            FixedDepositCalculatorView()
        }
        .sheet(isPresented: $showCalculatorsSheet) {
            CalculatorsView()
        }
        .sheet(isPresented: $showBenchmarkSheet) {
            BenchmarkComparisonSheet(data: benchmarkData, errorMessage: benchmarkError)
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = exportedPDFURL {
                ShareSheet(items: [url])
            }
        }
    }

    private func exportPDF() {
        guard !isExportingPDF else { return }
        isExportingPDF = true
        exportError = nil
        Task {
            do {
                let url = try await NetworkManager.shared.exportPortfolioPDF(userId: userId)
                await MainActor.run {
                    exportedPDFURL = url
                    showShareSheet = true
                    isExportingPDF = false
                    HapticManager.success()
                }
            } catch {
                await MainActor.run {
                    exportError = (error as? LocalizedError)?.errorDescription ?? "Couldn't create the PDF. Please try again."
                    isExportingPDF = false
                    HapticManager.error()
                }
            }
        }
    }

    private func fetchBenchmark() {
        guard !isLoadingBenchmark else { return }
        isLoadingBenchmark = true
        benchmarkError = nil
        Task {
            do {
                let data = try await NetworkManager.shared.fetchBenchmark(userId: userId)
                await MainActor.run {
                    benchmarkData = data
                    showBenchmarkSheet = true
                    isLoadingBenchmark = false
                    HapticManager.success()
                }
            } catch {
                await MainActor.run {
                    benchmarkError = error.localizedDescription
                    benchmarkData = nil
                    showBenchmarkSheet = true
                    isLoadingBenchmark = false
                    HapticManager.error()
                }
            }
        }
    }
}

// MARK: - Tool Button Row

private struct ToolButtonRow: View {
    let icon: String
    let title: String
    let subtitle: String
    let isLoading: Bool
    let action: () -> Void

    var body: some View {
        Button(action: { HapticManager.selection(); action() }) { HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: icon)
                    .font(Theme.engravedSerif(size: 18, weight: .medium))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(width: 36, height: 36)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(title)
                        .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                    Text(subtitle)
                        .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                }

                Spacer()

                if isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                } else {
                    Image(systemName: "chevron.right")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .buttonStyle(EKPressStyle())
        .disabled(isLoading)
    }
}

// MARK: - SIP Calculator Sheet

private struct PortfolioSIPCalculatorSheet: View {
    @Environment(\.dismiss) private var dismiss

    @State private var monthlyAmount: String = "10000"
    @State private var expectedReturn: String = "12"
    @State private var years: String = "10"
    @State private var stepUpPct: String = "0"

    @State private var result: SIPResult? = nil
    @State private var isCalculating = false

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        HStack {
                            Spacer()
                            Text("SIP CALCULATOR")
                                .font(Theme.officialStampFont(size: 10))
                                .tracking(2)
                                .foregroundStyle(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.standard)
                                .padding(.vertical, Theme.Spacing.tight)
                                .background(Theme.securityGold.opacity(0.10))
                                .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5))
                            Spacer()
                        }
                        .padding(.top, Theme.Spacing.standard)

                        VStack(spacing: Theme.Spacing.standard) {
                            SIPInputField(title: "Monthly Investment (₹)", text: $monthlyAmount)
                            SIPInputField(title: "Expected Return (%)", text: $expectedReturn)
                            SIPInputField(title: "Investment Period (Years)", text: $years)
                            SIPInputField(title: "Annual Step-Up (%)", text: $stepUpPct)
                        }
                        .banknoteCard()

                        Button { HapticManager.selection(); 
    HapticManager.selection()
                            HapticManager.impact(.medium)
                            calculate()
                        } label: {
                            HStack(spacing: Theme.Spacing.medium) {
                                if isCalculating {
                                    ProgressView().tint(Theme.canvasDeep)
                                }
                                Text("CALCULATE")
                                    .font(Theme.officialStampFont(size: 11))
                                    .tracking(1.5)
                            }
                            .foregroundStyle(Theme.canvasDeep)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(Theme.securityGold)
                            .cornerRadius(Theme.CornerRadius.medium)
                        }
                        .buttonStyle(EKPressStyle())
                        .disabled(isCalculating)

                        if let r = result {
                            SIPResultView(result: r)
                                .padding(.top, Theme.Spacing.standard)
                        }
                    }
                    .padding(Theme.Spacing.screen)
                }
            }
            .navigationTitle("SIP Calculator")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }.buttonStyle(EKPressStyle())
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
        }
    }

    private func calculate() {
        HapticManager.impact(.medium)
        isCalculating = true
        let m = Double(monthlyAmount) ?? 10000
        let r = (Double(expectedReturn) ?? 12) / 100.0
        let n = Int(years) ?? 10
        let step = (Double(stepUpPct) ?? 0) / 100.0

        Task {
            let (invested, maturity, gain, breakdown) = computeSIP(
                monthly: m, annualReturn: r, years: n, stepUp: step
            )
            let s = SIPResult(
                total_investment: invested,
                maturity_value: maturity,
                total_gain: gain,
                yearly_breakdown: breakdown
            )
            await MainActor.run {
                result = s
                isCalculating = false
                HapticManager.success()
            }
        }
    }

    private func computeSIP(
        monthly: Double, annualReturn: Double, years: Int, stepUp: Double
    ) -> (Double, Double, Double, [SIPYearRow]) {
        let months = years * 12
        let monthlyRate = annualReturn / 12.0
        var totalInvested: Double = 0
        var corpus: Double = 0
        var yearlyBreakdown: [SIPYearRow] = []
        var currentMonthly = monthly

        for y in 1...years {
            let yearStartInvested = totalInvested
            let yearStartCorpus = corpus
            for _ in 1...12 {
                corpus += currentMonthly
                totalInvested += currentMonthly
                corpus *= (1 + monthlyRate)
            }
            let row = SIPYearRow(
                year: y,
                invested: totalInvested,
                value: corpus
            )
            yearlyBreakdown.append(row)
            currentMonthly *= (1 + stepUp)
        }
        let gain = corpus - totalInvested
        return (totalInvested, corpus, gain, yearlyBreakdown)
    }
}

// MARK: - SIP Input Field

private struct SIPInputField: View {
    let title: String
    @Binding var text: String

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(title)
                .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .callout))
                .foregroundStyle(Theme.inkSecondary)
                .frame(width: UIScreen.main.bounds.width * 0.42, alignment: .leading)
            TextField(title, text: $text)
                .keyboardType(.decimalPad)
                .multilineTextAlignment(.trailing)
                .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.medium)
    }
}

// MARK: - SIP Result View

private struct SIPResultView: View {
    let result: SIPResult

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                Text("RESULTS")
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)
                Spacer()
            }

            HStack(spacing: Theme.Spacing.none) {
                SIPMetricBox(label: "Invested", value: result.total_investment ?? 0)
                SIPMetricBox(label: "Maturity", value: result.maturity_value ?? 0)
                SIPMetricBox(label: "Gain", value: result.total_gain ?? 0, isGain: true)
            }

            if let breakdown = result.yearly_breakdown, !breakdown.isEmpty {
                GuillocheDivider()
                    .padding(.vertical, Theme.Spacing.small)

                Text("YEAR-BY-YEAR")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1)
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.bottom, Theme.Spacing.small)

                ForEach(breakdown) { row in
                    HStack(spacing: Theme.Spacing.none) {
                        Text("Year \(row.year ?? 0)")
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(Theme.inkPrimary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                        Text(IndianFormatter.formatLakhsCrores(row.value ?? 0))
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(Theme.inkPrimary)
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    }
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - SIP Metric Box

private struct SIPMetricBox: View {
    let label: String
    let value: Double
    var isGain: Bool = false

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(IndianFormatter.formatLakhsCrores(value))
                .font(Theme.serialNumberFont(size: 15, relativeTo: .subheadline).weight(.bold))
                .foregroundStyle(isGain
                    ? (value >= 0 ? Theme.bullGreen : Theme.bearRed)
                    : Theme.inkPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 8))
                .tracking(1)
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.tight)
    }
}

// MARK: - Benchmark Comparison Sheet

private struct BenchmarkComparisonSheet: View {
    @Environment(\.dismiss) private var dismiss
    let data: BenchmarkData?
    let errorMessage: String?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()

                if let error = errorMessage {
                    VStack(spacing: Theme.Spacing.large) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(Theme.engravedSerif(size: 44, weight: .light))
                            .foregroundStyle(Theme.bearRed)
                        Text("Failed to load benchmark data")
                            .font(Theme.engravedSerif(size: 16, weight: .medium, relativeTo: .title3))
                            .foregroundStyle(Theme.inkPrimary)
                        Text(error)
                            .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .callout))
                            .foregroundStyle(Theme.inkSecondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(Theme.Spacing.screen)
                } else if let d = data {
                    ScrollView {
                        VStack(spacing: Theme.Spacing.standard) {
                            HStack {
                                Spacer()
                                Text("BENCHMARK VS NIFTY 50")
                                    .font(Theme.officialStampFont(size: 10))
                                    .tracking(2)
                                    .foregroundStyle(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.standard)
                                    .padding(.vertical, Theme.Spacing.tight)
                                    .background(Theme.securityGold.opacity(0.10))
                                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                        .stroke(Theme.securityGold.opacity(0.35), lineWidth: 0.5))
                                Spacer()
                            }
                            .padding(.top, Theme.Spacing.standard)

                            VStack(spacing: Theme.Spacing.none) {
                                BenchmarkRow(
                                    label: "Portfolio CAGR",
                                    value: d.portfolio_cagr,
                                    isPercent: true
                                )
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.Spacing.card)
                                BenchmarkRow(
                                    label: "Benchmark CAGR",
                                    value: d.benchmark_cagr,
                                    isPercent: true
                                )
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.Spacing.card)
                                BenchmarkRow(
                                    label: "Alpha",
                                    value: d.alpha,
                                    isPercent: true,
                                    isAlpha: true
                                )
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.Spacing.card)
                                BenchmarkRow(
                                    label: "Tracking Error",
                                    value: d.tracking_error,
                                    isPercent: true
                                )
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.Spacing.card)
                                BenchmarkRow(
                                    label: "Information Ratio",
                                    value: d.information_ratio,
                                    isPercent: false
                                )
                            }
                            .banknoteCard()
                        }
                        .padding(Theme.Spacing.screen)
                    }
                }
            }
            .navigationTitle("Benchmark")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }.buttonStyle(EKPressStyle())
                        .foregroundStyle(Theme.inkPrimary)
                }
            }
        }
    }
}

// MARK: - Benchmark Row

private struct BenchmarkRow: View {
    let label: String
    let value: Double?
    let isPercent: Bool
    var isAlpha: Bool = false

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(label)
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .callout))
                .foregroundStyle(Theme.inkSecondary)
                .frame(maxWidth: .infinity, alignment: .leading)
            if let v = value {
                Text(formatValue(v))
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body).weight(.semibold))
                    .foregroundStyle(valueColor(v))
            } else {
                Text("--")
                    .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
    }

    private func formatValue(_ v: Double) -> String {
        if isPercent {
            let sign = v >= 0 ? "+" : ""
            return "\(sign)\(String(format: "%.2f", v))%"
        }
        return String(format: "%.2f", v)
    }

    private func valueColor(_ v: Double) -> Color {
        if isAlpha {
            return v >= 0 ? Theme.bullGreen : Theme.bearRed
        }
        return Theme.inkPrimary
    }
}
