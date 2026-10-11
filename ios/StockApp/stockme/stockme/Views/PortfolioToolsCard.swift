import SwiftUI

// MARK: - Models

/// GET /portfolio/benchmark (routers/portfolio_analytics.py + portfolio_service.compute_benchmark).
/// The *_cagr_pct keys hold an absolute return under a year and an XIRR from a year on; return_basis says which.
struct BenchmarkData: Codable {
    let portfolioReturn: Double?
    let niftyReturn: Double?
    let alpha: Double?
    let returnBasis: String?
    let periodDays: Int?
    let unpricedTickers: [String]?

    enum CodingKeys: String, CodingKey {
        case portfolioReturn = "portfolio_cagr_pct"
        case niftyReturn = "nifty_cagr_pct"
        case alpha = "alpha_pct"
        case returnBasis = "return_basis"
        case periodDays = "period_days"
        case unpricedTickers = "unpriced_tickers"
    }

    var isAnnualized: Bool { returnBasis == "annualized_xirr" }
}

// MARK: - Portfolio Tools Card

struct PortfolioToolsCard: View {
    let userId: Int

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
                    icon: "doc.richtext",
                    title: "Export PDF",
                    subtitle: "Download portfolio report",
                    isLoading: isExportingPDF
                ) {
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
                    showCalculatorsSheet = true
                }
            }
            .padding(.bottom, Theme.Spacing.medium)
        }
        .banknoteCard()
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
                    showBenchmarkSheet = true
                    isLoadingBenchmark = false
                    // A payload without a portfolio return is a failure, not an all-"--" success.
                    if data.portfolioReturn != nil {
                        benchmarkData = data
                        HapticManager.success()
                    } else {
                        benchmarkData = nil
                        benchmarkError = "Benchmark unavailable"
                        HapticManager.error()
                    }
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
                                    label: d.isAnnualized ? "Portfolio XIRR" : "Portfolio return",
                                    value: d.portfolioReturn,
                                    isPercent: true
                                )
                                GuillocheDivider()
                                    .padding(.horizontal, Theme.Spacing.card)
                                BenchmarkRow(
                                    label: d.isAnnualized ? "Nifty 50 (same cash flows)" : "Nifty 50 return",
                                    value: d.niftyReturn,
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
                            }
                            .banknoteCard()

                            if let unpriced = d.unpricedTickers, !unpriced.isEmpty {
                                Text("Excluded (price unavailable): \(unpriced.joined(separator: ", "))")
                                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                                    .foregroundStyle(Theme.inkTertiary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
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
