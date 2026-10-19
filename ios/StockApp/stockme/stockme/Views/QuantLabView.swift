import SwiftUI

// MARK: - Quant Lab View

struct QuantLabView: View {
    let symbol: String
    @StateObject private var vm: QuantLabViewModel

    init(symbol: String) {
        self.symbol = symbol
        _vm = StateObject(wrappedValue: QuantLabViewModel(symbol: symbol))
    }

    var body: some View {
        ZStack {
            DenominationBackground(denomination: .twoHundred)

            ScrollView {
                LazyVStack(spacing: Theme.sectionSpacing) {
                    QuantLabHeader(symbol: symbol)

                    ModelSignalSection(signal: vm.mlSignal, isLoading: vm.mlSignalLoading, error: vm.mlSignalError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    FeatureDriversSection(signal: vm.mlSignal, isLoading: vm.mlSignalLoading)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    CalibrationSection(data: vm.calibration, isLoading: vm.calibrationLoading, error: vm.calibrationError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    PillarAttributionSection(data: vm.pillarAttribution, isLoading: vm.pillarAttributionLoading, error: vm.pillarAttributionError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    ModelVersionsSection(data: vm.modelVersions, isLoading: vm.modelVersionsLoading, error: vm.modelVersionsError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    AlphaValidationSection(data: vm.alphaValidation, isLoading: vm.alphaValidationLoading, error: vm.alphaValidationError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    StrategySweepSection(data: vm.strategySweep, isLoading: vm.strategySweepLoading, error: vm.strategySweepError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    RegimeBreakdownSection(data: vm.regimeBreakdown, isLoading: vm.regimeBreakdownLoading, error: vm.regimeBreakdownError)

                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                    CostSensitivitySection(data: vm.costSensitivity, isLoading: vm.costSensitivityLoading, error: vm.costSensitivityError)

                    QuantLabDisclaimer()
                }
                .padding(.bottom, Theme.sectionSpacing)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                Text("QUANT LAB")
                    .font(Theme.officialStampFont(size: 11))
                    .tracking(1.5)
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .toolbarBackground(Theme.canvas, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .task { await vm.loadAll() }
    }
}

// MARK: - Header

struct QuantLabHeader: View {
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(spacing: Theme.Spacing.medium) {
                Image(systemName: "flask.fill")
                    .foregroundStyle(Theme.securityGold)
                    .font(Theme.engravedSerif(size: 20, weight: .bold))

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(symbol.uppercased())
                        .font(Theme.engravedSerif(size: 18, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)

                    Text("QUANT LAB")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                }

                Spacer()
            }

            Text("Research validation tools for the Nivesh ML pipeline")
                .font(Theme.engravedSerif(size: 13))
                .foregroundStyle(Theme.inkSecondary)
        }
        .padding(Theme.Spacing.card)
        .padding(.horizontal, Theme.Spacing.small)
    }
}

// MARK: - Section Empty / Error / Loading Helpers

struct QuantLabLoadingCard: View {
    var body: some View {
        RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
            .fill(Theme.canvasDeep)
            .frame(maxWidth: .infinity)
            .frame(height: 80)
            .shimmerPlaceholder(isLoading: true)
            .padding(.horizontal, Theme.screenPadding)
    }
}

struct QuantLabErrorCard: View {
    let message: String

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundStyle(Theme.holdAmber)
            Text(message)
                .font(Theme.engravedSerif(size: 12))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(3)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct QuantLabEmptyCard: View {
    let message: String

    var body: some View {
        VStack(spacing: Theme.Spacing.medium) {
            Image(systemName: "chart.bar.doc.horizontal")
                .foregroundStyle(Theme.inkTertiary)
                .font(Theme.engravedSerif(size: 24))
            Text(message)
                .font(Theme.engravedSerif(size: 12))
                .foregroundStyle(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Disclaimer

struct QuantLabDisclaimer: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("DISCLAIMER")
                .font(Theme.officialStampFont(size: 8))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Text("Backtests are estimates and may not reflect live execution. Past performance is not indicative of future results. All metrics are computed on historical data and subject to look-ahead bias, survivorship bias, and data quality limitations.")
                .font(Theme.engravedSerif(size: 10))
                .foregroundStyle(Theme.inkTertiary)
                .lineSpacing(Theme.Spacing.small)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, Theme.screenPadding)
    }
}
