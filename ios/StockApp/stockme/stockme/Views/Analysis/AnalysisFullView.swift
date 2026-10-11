import SwiftUI

struct AnalysisFullView: View {
    let analysis: StockAnalysis
    let previousAnalysis: StockAnalysis?
    let ticker: String
    let livePrice: Double?
    @ObservedObject var viewModel: AnalysisViewModel
    @Binding var extremeViewMode: Int
    let heroPrices: [Double]
    let heroDates: [Date]
    let heroLoading: Bool
    @Binding var heroPeriod: String
    let onPeriodChange: (String) -> Void

    var body: some View {
        if analysis.analysisTier == "extreme" {
            VStack(spacing: Theme.Spacing.none) {
                extremeModeSwitcherView
                    .background(Theme.canvas)
                if extremeViewMode == 0 {
                    aiReportScrollView
                } else {
                    StockProfileView(ticker: ticker, exchange: analysis.exchange ?? "NSE")
                }
            }
        } else {
            aiReportScrollView
        }
    }

    private var extremeModeSwitcherView: some View {
        HStack(spacing: Theme.Spacing.small) {
            ForEach(Array(["AI REPORT", "FULL PROFILE"].enumerated()), id: \.offset) { idx, label in
                Button { HapticManager.selection(); 
    HapticManager.selection()
                    HapticManager.selection()
                    extremeViewMode = idx
                } label: {
                    Text(label)
                        .font(Theme.sectionCapsLabel(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(extremeViewMode == idx ? Theme.canvas : Theme.inkSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                .fill(extremeViewMode == idx ? Theme.securityGold : Theme.surfaceElevated)
                        )
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.standard)
    }

    private var aiReportScrollView: some View {
        let isExtreme = analysis.analysisTier == "extreme"
        return ScrollView {
            heroChartSectionView
                .padding(.bottom, Theme.Spacing.standard)

            AnalysisCoreSections(
                analysis: analysis,
                previousAnalysis: previousAnalysis,
                ticker: ticker,
                livePrice: livePrice,
                viewModel: viewModel
            )
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.Spacing.standard)

            if let regime = analysis.marketRegime, !regime.isEmpty {
                RegimeWarningBanner(regime: regime)
                    .padding(.horizontal, Theme.screenPadding)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }

            if let drivers = analysis.quantitativeDrivers, !drivers.isEmpty {
                QuantitativeDriversCard(drivers: drivers)
                    .padding(.horizontal, Theme.screenPadding)
                    .transition(.opacity)
            }

            if isExtreme {
                GuillocheDivider()
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.sectionBreath)

                AnalysisExtremeSections(
                    analysis: analysis,
                    previousAnalysis: previousAnalysis,
                    viewModel: viewModel
                )
                .padding(.horizontal, Theme.screenPadding)
            }

            Spacer(minLength: 100)
        }
    }

    @ViewBuilder
    private var heroChartSectionView: some View {
        if !heroPrices.isEmpty {
            let price = livePrice ?? viewModel.quickInfo?.price ?? heroPrices.last ?? 0
            ImmersiveStockHeroChart(
                prices: heroPrices,
                currentPrice: price,
                dates: heroDates
            )
            HStack(spacing: Theme.Spacing.tight) {
                ForEach(
                    Array(zip(
                        ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                        ["1M",  "3M",  "6M",  "1Y", "2Y", "5Y", "ALL"]
                    )),
                    id: \.0
                ) { period, label in
                    Button { HapticManager.selection(); 
    HapticManager.selection()
                        HapticManager.selection()
                        heroPeriod = period
                        onPeriodChange(period)
                    } label: {
                        Text(label)
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(heroPeriod == period ? Theme.securityGold : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(heroPeriod == period ? Theme.securityGold.opacity(0.12) : Theme.canvasDeep)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.top, Theme.Spacing.standard)
        } else if heroLoading {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .fill(Theme.inkTertiary.opacity(0.08))
                .frame(height: UIScreen.main.bounds.height * 0.26)
                .shimmerPlaceholder(isLoading: true)
        }
    }
}
