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

// MARK: - Section 1: Model Signal

struct ModelSignalSection: View {
    let signal: MLSignalResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "MODEL SIGNAL")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let signal = signal {
                ModelSignalContent(signal: signal)
            } else {
                QuantLabEmptyCard(message: "ML signal unavailable for this symbol.")
            }
        }
    }
}

struct ModelSignalContent: View {
    let signal: MLSignalResponse

    private var directionColor: Color {
        switch signal.direction {
        case 1: return Theme.bullGreen
        case -1: return Theme.bearRed
        default: return Theme.holdAmber
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            ModelSignalHeaderRow(signal: signal, directionColor: directionColor)
            ModelSignalDetailsGrid(signal: signal)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct ModelSignalHeaderRow: View {
    let signal: MLSignalResponse
    let directionColor: Color

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text(signal.directionLabel.uppercased())
                    .font(Theme.officialStampFont(size: 14))
                    .tracking(1.5)
                    .foregroundStyle(directionColor)

                if let pct = signal.confidencePct {
                    HStack(spacing: Theme.Spacing.small) {
                        Text("CONFIDENCE")
                            .font(Theme.officialStampFont(size: 9))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)
                        Text("\(pct)%")
                            .font(Theme.serialNumberFont(size: 14))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                }
            }

            Spacer()

            if let pct = signal.confidencePct {
                ConfidenceArcView(score: pct, size: 48)
            }
        }
    }
}

struct ModelSignalDetailsGrid: View {
    let signal: MLSignalResponse

    var body: some View {
        VStack(spacing: Theme.Spacing.medium) {
            ModelSignalDetailRow(label: "ENGINE MODE", value: signal.mlEngineMode.uppercased())
            ModelSignalDetailRow(label: "MODEL VERSION", value: signal.modelVersion ?? "N/A")
            ModelSignalDetailRow(label: "HORIZON", value: signal.predictionHorizon)
            ModelSignalDetailRow(label: "LIGHTGBM", value: signal.lightgbmLoaded ? "LOADED" : "NOT LOADED")

            if let warning = signal.warning {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Theme.holdAmber)
                        .font(Theme.engravedSerif(size: 10))
                    Text(warning)
                        .font(Theme.engravedSerif(size: 11))
                        .foregroundStyle(Theme.holdAmber)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

struct ModelSignalDetailRow: View {
    let label: String
    let value: String

    var body: some View {
        HStack {
            Text(label)
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Spacer()
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
        }
    }
}

// MARK: - Section 2: Feature Drivers

struct FeatureDriversSection: View {
    let signal: MLSignalResponse?
    let isLoading: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "FEATURE DRIVERS")

            if isLoading {
                QuantLabLoadingCard()
            } else if let signal = signal, !signal.featureDrivers.isEmpty {
                FeatureDriversList(drivers: signal.featureDrivers)
            } else {
                QuantLabEmptyCard(message: "Feature drivers available only for trained LightGBM models with explainability enabled.")
            }
        }
    }
}

struct FeatureDriversList: View {
    let drivers: [FeatureDriver]

    private var positiveDrivers: [FeatureDriver] {
        drivers.filter { $0.contribution > 0 }.sorted { $0.contribution > $1.contribution }.prefix(3).map { $0 }
    }

    private var negativeDrivers: [FeatureDriver] {
        drivers.filter { $0.contribution < 0 }.sorted { $0.contribution < $1.contribution }.prefix(3).map { $0 }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            if !positiveDrivers.isEmpty {
                FeatureDriverGroup(title: "POSITIVE DRIVERS", drivers: positiveDrivers, barColor: Theme.bullGreen)
            }
            if !negativeDrivers.isEmpty {
                FeatureDriverGroup(title: "NEGATIVE DRIVERS", drivers: negativeDrivers, barColor: Theme.bearRed)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct FeatureDriverGroup: View {
    let title: String
    let drivers: [FeatureDriver]
    let barColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(title)
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)

            ForEach(drivers, id: \.feature) { driver in
                FeatureDriverBar(driver: driver, barColor: barColor)
            }
        }
    }
}

struct FeatureDriverBar: View {
    let driver: FeatureDriver
    let barColor: Color

    private var maxContribution: Double { 1.0 }

    private var barWidth: CGFloat {
        let proportion = min(abs(driver.contribution) / maxContribution, 1.0)
        return CGFloat(proportion) * (UIScreen.main.bounds.width * 0.4)
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Text(driver.feature)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
                .frame(width: UIScreen.main.bounds.width * 0.3, alignment: .leading)
                .lineLimit(1)

            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(barColor.opacity(0.7))
                .frame(width: max(barWidth, Theme.Spacing.small), height: Theme.Spacing.medium)

            Text(String(format: "%.3f", driver.contribution))
                .font(Theme.serialNumberFont(size: 9))
                .foregroundStyle(Theme.inkTertiary)
        }
    }
}

// MARK: - Section 3: Confidence Calibration

struct CalibrationSection: View {
    let data: CalibrationResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "CONFIDENCE CALIBRATION")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data {
                CalibrationContent(data: data)
            } else {
                QuantLabEmptyCard(message: "No calibration data available. Predictions must mature before calibration can be measured.")
            }
        }
    }
}

struct CalibrationContent: View {
    let data: CalibrationResponse

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            CalibrationMetricsRow(data: data)

            if !data.confidenceBucketAccuracy.isEmpty {
                CalibrationBucketTable(buckets: data.confidenceBucketAccuracy)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct CalibrationMetricsRow: View {
    let data: CalibrationResponse

    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            CalibrationMetricCell(
                label: "ECE",
                value: data.expectedCalibrationError.map { String(format: "%.3f", $0) } ?? "N/A"
            )
            CalibrationMetricCell(
                label: "MCE",
                value: data.maxCalibrationError.map { String(format: "%.3f", $0) } ?? "N/A"
            )
            CalibrationMetricCell(
                label: "CAL ERROR",
                value: data.calibrationError.map { String(format: "%.3f", $0) } ?? "N/A"
            )
        }
    }
}

struct CalibrationMetricCell: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .tracking(1.0)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 14))
                .foregroundStyle(Theme.inkPrimary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct CalibrationBucketTable: View {
    let buckets: [CalibrationBucket]

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            CalibrationBucketHeaderRow()

            ForEach(buckets, id: \.bucketLabel) { bucket in
                CalibrationBucketRow(bucket: bucket)
            }
        }
    }
}

struct CalibrationBucketHeaderRow: View {
    var body: some View {
        HStack {
            Text("BUCKET")
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("ACC")
                .frame(width: 50, alignment: .trailing)
            Text("CONF")
                .frame(width: 50, alignment: .trailing)
            Text("N")
                .frame(width: 40, alignment: .trailing)
        }
        .font(Theme.officialStampFont(size: 8))
        .tracking(0.8)
        .foregroundStyle(Theme.inkTertiary)
    }
}

struct CalibrationBucketRow: View {
    let bucket: CalibrationBucket

    private var isOverconfident: Bool {
        guard let acc = bucket.accuracy, let conf = bucket.avgConfidence else { return false }
        return conf > acc + 0.1
    }

    private var isUnderconfident: Bool {
        guard let acc = bucket.accuracy, let conf = bucket.avgConfidence else { return false }
        return acc > conf + 0.1
    }

    private var rowColor: Color {
        if isOverconfident { return Theme.bearRed.opacity(0.08) }
        if isUnderconfident { return Theme.bullGreen.opacity(0.08) }
        return Color.clear
    }

    var body: some View {
        HStack {
            Text(bucket.bucketLabel)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(bucket.accuracy.map { String(format: "%.1f%%", $0 * 100) } ?? "-")
                .frame(width: 50, alignment: .trailing)
            Text(bucket.avgConfidence.map { String(format: "%.1f%%", $0 * 100) } ?? "-")
                .frame(width: 50, alignment: .trailing)
            Text("\(bucket.count)")
                .frame(width: 40, alignment: .trailing)
        }
        .font(Theme.serialNumberFont(size: 10))
        .foregroundStyle(Theme.inkSecondary)
        .padding(.vertical, Theme.Spacing.xSmall)
        .padding(.horizontal, Theme.Spacing.small)
        .background(rowColor)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
    }
}

// MARK: - Section 4: Pillar Attribution

struct PillarAttributionSection: View {
    let data: PillarAttributionResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "PILLAR ATTRIBUTION")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data, !data.pillars.isEmpty {
                PillarAttributionContent(data: data)
            } else {
                QuantLabEmptyCard(message: "Pillar attribution requires matured predictions to compute.")
            }
        }
    }
}

struct PillarAttributionContent: View {
    let data: PillarAttributionResponse

    private var bestPillar: PillarAttribution? {
        data.pillars.min(by: { ($0.usefulnessRank ?? 999) < ($1.usefulnessRank ?? 999) })
    }

    private var worstPillar: PillarAttribution? {
        data.pillars.max(by: { ($0.usefulnessRank ?? 999) < ($1.usefulnessRank ?? 999) })
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("\(data.totalPredictions) total predictions analysed")
                .font(Theme.engravedSerif(size: 11))
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)

            ForEach(data.pillars, id: \.pillarName) { pillar in
                PillarAttributionRow(
                    pillar: pillar,
                    isBest: pillar.pillarName == bestPillar?.pillarName,
                    isWorst: pillar.pillarName == worstPillar?.pillarName
                )
            }
        }
    }
}

struct PillarAttributionRow: View {
    let pillar: PillarAttribution
    let isBest: Bool
    let isWorst: Bool

    private var accentColor: Color {
        if isBest { return Theme.securityGold }
        if isWorst { return Theme.bearRed }
        return Theme.borderFine
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text(pillar.pillarName.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.0)
                    .foregroundStyle(isBest ? Theme.securityGold : Theme.inkPrimary)

                Spacer()

                if let rank = pillar.usefulnessRank {
                    Text("#\(rank)")
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(isBest ? Theme.securityGold : Theme.inkTertiary)
                }
            }

            HStack(spacing: Theme.Spacing.card) {
                PillarStatCell(label: "CORR", value: pillar.correlationWithOutcome.map { String(format: "%.3f", $0) } ?? "-")
                PillarStatCell(label: "MISSING", value: String(format: "%.1f%%", pillar.missingRate * 100))
                PillarStatCell(label: "BRIER", value: pillar.avgBrierScore.map { String(format: "%.3f", $0) } ?? "-")
            }
        }
        .padding(Theme.Spacing.standard)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(accentColor, lineWidth: isBest || isWorst ? 1 : 0.5)
        )
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct PillarStatCell: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .tracking(0.8)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Section 5: Model Versions

struct ModelVersionsSection: View {
    let data: ModelVersionsResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "MODEL VERSIONS")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data, !data.versions.isEmpty {
                ModelVersionsContent(data: data)
            } else {
                QuantLabEmptyCard(message: "No model version history available.")
            }
        }
    }
}

struct ModelVersionsContent: View {
    let data: ModelVersionsResponse

    private var bestVersion: ModelVersionStats? {
        data.versions.max(by: { ($0.hitRate30d ?? 0) < ($1.hitRate30d ?? 0) })
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.medium) {
            ModelVersionsHeaderRow()

            ForEach(data.versions, id: \.modelVersion) { version in
                ModelVersionRow(
                    version: version,
                    isBest: version.modelVersion == bestVersion?.modelVersion
                )
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct ModelVersionsHeaderRow: View {
    var body: some View {
        HStack {
            Text("VERSION")
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("HIT")
                .frame(width: 44, alignment: .trailing)
            Text("BRIER")
                .frame(width: 50, alignment: .trailing)
            Text("CAL")
                .frame(width: 44, alignment: .trailing)
        }
        .font(Theme.officialStampFont(size: 8))
        .tracking(0.8)
        .foregroundStyle(Theme.inkTertiary)
    }
}

struct ModelVersionRow: View {
    let version: ModelVersionStats
    let isBest: Bool

    var body: some View {
        HStack {
            HStack(spacing: Theme.Spacing.small) {
                if isBest {
                    Image(systemName: "star.fill")
                        .foregroundStyle(Theme.securityGold)
                        .font(Theme.engravedSerif(size: 8))
                }
                Text(version.modelVersion)
                    .lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            Text(version.hitRate30d.map { String(format: "%.0f%%", $0 * 100) } ?? "-")
                .frame(width: 44, alignment: .trailing)
            Text(version.brierScore30d.map { String(format: "%.3f", $0) } ?? "-")
                .frame(width: 50, alignment: .trailing)
            Text(version.calibrationError30d.map { String(format: "%.3f", $0) } ?? "-")
                .frame(width: 44, alignment: .trailing)
        }
        .font(Theme.serialNumberFont(size: 10))
        .foregroundStyle(isBest ? Theme.securityGold : Theme.inkSecondary)
        .padding(.vertical, Theme.Spacing.xSmall)
    }
}

// MARK: - Section 6: Alpha Validation

struct AlphaValidationSection: View {
    let data: BacktestResult?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "ALPHA VALIDATION")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data {
                AlphaValidationContent(data: data)
            } else {
                QuantLabEmptyCard(message: "Alpha validation not yet available. Requires sufficient prediction history.")
            }
        }
    }
}

struct AlphaValidationContent: View {
    let data: BacktestResult

    private var hasAlphaBeforeCosts: Bool {
        data.metrics.grossReturn > 0 && data.metrics.benchmarkExcessReturn > 0
    }

    private var hasAlphaAfterCosts: Bool {
        data.metrics.netReturn > 0 && data.metrics.benchmarkExcessReturn > 0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            AlphaMetricsGrid(metrics: data.metrics)
            AlphaVerdictRow(hasAlphaBeforeCosts: hasAlphaBeforeCosts, hasAlphaAfterCosts: hasAlphaAfterCosts)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct AlphaMetricsGrid: View {
    let metrics: PortfolioMetrics

    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: Theme.Spacing.standard) {
            AlphaMetricCell(label: "CAGR", value: String(format: "%.1f%%", metrics.cagr * 100), isPositive: metrics.cagr > 0)
            AlphaMetricCell(label: "SHARPE", value: String(format: "%.2f", metrics.sharpe), isPositive: metrics.sharpe > 1)
            AlphaMetricCell(label: "SORTINO", value: String(format: "%.2f", metrics.sortino), isPositive: metrics.sortino > 1)
            AlphaMetricCell(label: "MAX DD", value: String(format: "%.1f%%", metrics.maxDrawdown * 100), isPositive: false)
            AlphaMetricCell(label: "HIT RATE", value: String(format: "%.0f%%", metrics.hitRate * 100), isPositive: metrics.hitRate > 0.5)
            AlphaMetricCell(label: "EXCESS", value: String(format: "%.1f%%", metrics.benchmarkExcessReturn * 100), isPositive: metrics.benchmarkExcessReturn > 0)
        }
    }
}

struct AlphaMetricCell: View {
    let label: String
    let value: String
    let isPositive: Bool

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .tracking(0.8)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 13))
                .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
        }
    }
}

struct AlphaVerdictRow: View {
    let hasAlphaBeforeCosts: Bool
    let hasAlphaAfterCosts: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            AlphaVerdictBadge(question: "Alpha before costs?", answer: hasAlphaBeforeCosts)
            AlphaVerdictBadge(question: "Alpha survives costs?", answer: hasAlphaAfterCosts)
        }
    }
}

struct AlphaVerdictBadge: View {
    let question: String
    let answer: Bool

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text(question)
                .font(Theme.engravedSerif(size: 10))
                .foregroundStyle(Theme.inkTertiary)
            Text(answer ? "YES" : "NO")
                .font(Theme.officialStampFont(size: 11))
                .tracking(1.5)
                .foregroundStyle(answer ? Theme.bullGreen : Theme.bearRed)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .background((answer ? Theme.bullGreen : Theme.bearRed).opacity(0.1))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Section 7: Strategy Sweep

struct StrategySweepSection: View {
    let data: StrategySweepResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "STRATEGY SWEEP")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data, !data.allResults.isEmpty {
                StrategySweepContent(data: data)
            } else {
                QuantLabEmptyCard(message: "Strategy sweep requires sufficient backtest data.")
            }
        }
    }
}

struct StrategySweepContent: View {
    let data: StrategySweepResponse
    @State private var selectedFilter: SweepFilter = .all

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SweepFilterChips(selectedFilter: $selectedFilter)
            SweepHighlightsRow(data: data)
            SweepResultsTable(results: filteredResults)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }

    private var filteredResults: [SweepIteration] {
        switch selectedFilter {
        case .all: return data.allResults
        case .highConfidence: return data.allResults.filter { $0.confidenceThreshold >= 0.7 }
        case .topK5: return data.allResults.filter { $0.topK <= 5 }
        }
    }
}

enum SweepFilter: String, CaseIterable {
    case all = "All"
    case highConfidence = "High Conf"
    case topK5 = "Top K<=5"
}

struct SweepFilterChips: View {
    @Binding var selectedFilter: SweepFilter

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            ForEach(SweepFilter.allCases, id: \.self) { filter in
                Button(action: { HapticManager.selection();  HapticManager.selection()
                    HapticManager.selection()
                    selectedFilter = filter
                }) {
                    Text(filter.rawValue.uppercased())
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(0.8)
                        .foregroundStyle(selectedFilter == filter ? Theme.securityGold : Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.medium)
                        .padding(.vertical, Theme.Spacing.small)
                        .background(selectedFilter == filter ? Theme.securityGold.opacity(0.1) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                .stroke(selectedFilter == filter ? Theme.securityGold.opacity(0.4) : Theme.borderFine, lineWidth: 0.5)
                        )
                }
                .buttonStyle(EKPressStyle())
            }
        }
    }
}

struct SweepHighlightsRow: View {
    let data: StrategySweepResponse

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            if let best = data.bestCagr {
                SweepHighlightCell(label: "BEST CAGR", value: String(format: "%.1f%%", best.netCagr * 100))
            }
            if let best = data.bestSharpe {
                SweepHighlightCell(label: "BEST SHARPE", value: String(format: "%.2f", best.sharpe))
            }
        }
    }
}

struct SweepHighlightCell: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .tracking(0.8)
                .foregroundStyle(Theme.securityGold)
            Text(value)
                .font(Theme.serialNumberFont(size: 14))
                .foregroundStyle(Theme.inkPrimary)
        }
        .frame(maxWidth: .infinity)
    }
}

struct SweepResultsTable: View {
    let results: [SweepIteration]

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            SweepTableHeader()

            ForEach(Array(results.prefix(10).enumerated()), id: \.offset) { _, iteration in
                SweepTableRow(iteration: iteration)
            }
        }
    }
}

struct SweepTableHeader: View {
    var body: some View {
        HStack {
            Text("CONF")
                .frame(width: 40, alignment: .leading)
            Text("K")
                .frame(width: 24, alignment: .trailing)
            Text("CAGR")
                .frame(maxWidth: .infinity, alignment: .trailing)
            Text("SHARPE")
                .frame(width: 50, alignment: .trailing)
            Text("DD")
                .frame(width: 44, alignment: .trailing)
        }
        .font(Theme.officialStampFont(size: 7))
        .tracking(0.6)
        .foregroundStyle(Theme.inkTertiary)
    }
}

struct SweepTableRow: View {
    let iteration: SweepIteration

    var body: some View {
        HStack {
            Text(String(format: "%.0f%%", iteration.confidenceThreshold * 100))
                .frame(width: 40, alignment: .leading)
            Text("\(iteration.topK)")
                .frame(width: 24, alignment: .trailing)
            Text(String(format: "%.1f%%", iteration.netCagr * 100))
                .frame(maxWidth: .infinity, alignment: .trailing)
                .foregroundStyle(iteration.netCagr > 0 ? Theme.bullGreen : Theme.bearRed)
            Text(String(format: "%.2f", iteration.sharpe))
                .frame(width: 50, alignment: .trailing)
            Text(String(format: "%.0f%%", iteration.maxDrawdown * 100))
                .frame(width: 44, alignment: .trailing)
                .foregroundStyle(Theme.bearRed)
        }
        .font(Theme.serialNumberFont(size: 9))
        .foregroundStyle(Theme.inkSecondary)
        .padding(.vertical, Theme.Spacing.xSmall)
    }
}

// MARK: - Section 8: Regime Breakdown

struct RegimeBreakdownSection: View {
    let data: RegimeBreakdownResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "REGIME BREAKDOWN")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data, !data.regimes.isEmpty {
                RegimeBreakdownContent(data: data)
            } else {
                QuantLabEmptyCard(message: "Regime breakdown requires backtest data across market conditions.")
            }
        }
    }
}

struct RegimeBreakdownContent: View {
    let data: RegimeBreakdownResponse

    private var worksWell: [RegimePerformance] {
        data.regimes.filter { ($0.sharpe ?? 0) > 0.5 }
    }

    private var struggles: [RegimePerformance] {
        data.regimes.filter { ($0.sharpe ?? 0) <= 0.5 }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            if !worksWell.isEmpty {
                RegimeGroupHeader(title: "WHERE NIVESH WORKS", icon: "checkmark.circle.fill", color: Theme.bullGreen)
            }

            ForEach(worksWell, id: \.regimeName) { regime in
                RegimeCard(regime: regime, accent: Theme.bullGreen)
            }

            if !struggles.isEmpty {
                RegimeGroupHeader(title: "WHERE NIVESH STRUGGLES", icon: "exclamationmark.triangle.fill", color: Theme.holdAmber)
            }

            ForEach(struggles, id: \.regimeName) { regime in
                RegimeCard(regime: regime, accent: Theme.bearRed)
            }

            if let conclusion = data.conclusion {
                Text(conclusion)
                    .font(Theme.engravedSerif(size: 11))
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}

struct RegimeGroupHeader: View {
    let title: String
    let icon: String
    let color: Color

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            Image(systemName: icon)
                .foregroundStyle(color)
                .font(Theme.engravedSerif(size: 12))
            Text(title)
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.0)
                .foregroundStyle(color)
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct RegimeCard: View {
    let regime: RegimePerformance
    let accent: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                Text(regime.regimeName.uppercased())
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.0)
                    .foregroundStyle(Theme.inkPrimary)

                Spacer()

                Text("n=\(regime.sampleSize)")
                    .font(Theme.serialNumberFont(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }

            HStack(spacing: Theme.Spacing.card) {
                RegimeStatCell(label: "CAGR", value: regime.netCagr.map { String(format: "%.1f%%", $0 * 100) } ?? "-")
                RegimeStatCell(label: "SHARPE", value: regime.sharpe.map { String(format: "%.2f", $0) } ?? "-")
                RegimeStatCell(label: "HIT", value: regime.hitRate.map { String(format: "%.0f%%", $0 * 100) } ?? "-")
                RegimeStatCell(label: "DD", value: regime.maxDrawdown.map { String(format: "%.0f%%", $0 * 100) } ?? "-")
            }
        }
        .padding(Theme.Spacing.standard)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(accent.opacity(0.3), lineWidth: 0.5)
        )
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct RegimeStatCell: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .tracking(0.6)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Section 9: Cost Sensitivity

struct CostSensitivitySection: View {
    let data: CostSensitivityResponse?
    let isLoading: Bool
    let error: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "COST SENSITIVITY")

            if isLoading {
                QuantLabLoadingCard()
            } else if let error = error {
                QuantLabErrorCard(message: error)
            } else if let data = data, !data.presets.isEmpty {
                CostSensitivityContent(data: data)
            } else {
                QuantLabEmptyCard(message: "Cost sensitivity analysis not available.")
            }
        }
    }
}

struct CostSensitivityContent: View {
    let data: CostSensitivityResponse

    private let presetOrder = ["zero_cost", "optimistic", "realistic", "conservative", "institutional"]

    private var orderedPresets: [(String, CostPresetResult)] {
        presetOrder.compactMap { key in
            data.presets[key].map { (key, $0) }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            ForEach(orderedPresets, id: \.0) { key, preset in
                CostPresetCard(presetName: key, preset: preset)
            }

            if let warning = data.warning {
                CostWarningText(warning: warning)
            }

            CostWarningText(warning: "Backtests are estimates. Actual execution costs, slippage, and market impact may differ significantly.")
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct CostPresetCard: View {
    let presetName: String
    let preset: CostPresetResult

    private var displayName: String {
        presetName.replacingOccurrences(of: "_", with: " ").uppercased()
    }

    private var accentColor: Color {
        switch presetName {
        case "zero_cost": return Theme.securityGold
        case "optimistic": return Theme.bullGreen
        case "realistic": return Theme.holdAmber
        case "conservative": return Theme.bearRed
        case "institutional": return Theme.inkSecondary
        default: return Theme.inkTertiary
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(accentColor)
                    .frame(width: Theme.Spacing.small, height: Theme.Spacing.card)

                Text(displayName)
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.0)
                    .foregroundStyle(accentColor)

                Spacer()

                if let error = preset.error {
                    Text(error)
                        .font(Theme.engravedSerif(size: 9))
                        .foregroundStyle(Theme.bearRed)
                }
            }

            if preset.error == nil {
                CostPresetMetrics(preset: preset)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}

struct CostPresetMetrics: View {
    let preset: CostPresetResult

    private var costDrag: Double? {
        guard let gross = preset.grossReturn, let net = preset.netReturn else { return nil }
        return gross - net
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            CostMetricCell(label: "GROSS", value: preset.grossReturn.map { String(format: "%.1f%%", $0 * 100) } ?? "-", color: Theme.inkPrimary)
            CostMetricCell(label: "NET", value: preset.netReturn.map { String(format: "%.1f%%", $0 * 100) } ?? "-", color: (preset.netReturn ?? 0) > 0 ? Theme.bullGreen : Theme.bearRed)
            CostMetricCell(label: "DRAG", value: costDrag.map { String(format: "%.1f%%", $0 * 100) } ?? "-", color: Theme.holdAmber)
            CostMetricCell(label: "SHARPE", value: preset.sharpe.map { String(format: "%.2f", $0) } ?? "-", color: Theme.inkSecondary)
        }
    }
}

struct CostMetricCell: View {
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .tracking(0.6)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 11))
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
    }
}

struct CostWarningText: View {
    let warning: String

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: "info.circle")
                .foregroundStyle(Theme.holdAmber)
                .font(Theme.engravedSerif(size: 11))
            Text(warning)
                .font(Theme.engravedSerif(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
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
