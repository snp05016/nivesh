import SwiftUI
import Charts

// MARK: - Mutual Fund Detail

struct MutualFundDetailView: View {
    @StateObject private var vm: MutualFundDetailViewModel
    @State private var showSIPCalculator = false

    init(fund: MutualFundDTO) {
        _vm = StateObject(wrappedValue: MutualFundDetailViewModel(seed: fund))
    }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                MutualFundDetailHeader(fund: vm.fund)

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                MutualFundReturnsGrid(fund: vm.fund, historyStart: vm.historyStart)
                    .padding(.horizontal, Theme.screenPadding)

                MutualFundNAVHistorySection(vm: vm)
                    .padding(.horizontal, Theme.screenPadding)

                if vm.fund.isinGrowth != nil || vm.fund.isinReinvest != nil {
                    MutualFundISINSection(fund: vm.fund)
                        .padding(.horizontal, Theme.screenPadding)
                }

                MutualFundSIPEntryPoint { showSIPCalculator = true }
                    .padding(.horizontal, Theme.screenPadding)

                if vm.fund.parsedRiskLevel != nil {
                    MutualFundRiskometerSection(fund: vm.fund)
                        .padding(.horizontal, Theme.screenPadding)
                }

                if vm.fund.fundManager != nil {
                    MutualFundFundManagerSection(fund: vm.fund)
                        .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(vm.fund.fundName)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { vm.loadAll() }
        .refreshable { vm.loadAll() }
        .sheet(isPresented: $showSIPCalculator) {
            SIPCalculatorSheet(fund: vm.fund)
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
    }
}

// MARK: - Header

struct MutualFundDetailHeader: View {
    let fund: MutualFundDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.standard) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(Theme.canvasShadow)
                    .frame(width: 52, height: 52)
                    .overlay(
                        Text(String(fund.fundName.prefix(1)))
                            .font(Theme.officialStampFont(size: 18, relativeTo: .title3))
                            .foregroundColor(Theme.inkPrimary)
                    )

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(fund.fundName)
                        .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title2))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(2)
                    Text("\(fund.category) · \(fund.amc)")
                        .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                        .tracking(1.2)
                        .foregroundColor(Theme.inkSecondary)
                    if fund.isSample == true {
                        MutualFundSampleDataStamp()
                    }
                }
                Spacer()
            }

            MutualFundNAVLine(fund: fund)
                .padding(.top, Theme.Spacing.small)

            MutualFundPlanChips(fund: fund)
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - NAV line and plan chips

struct MutualFundNAVLine: View {
    let fund: MutualFundDTO

    private var text: String {
        guard fund.nav != nil else { return "NAV unavailable" }
        let value = fund.isAMFISourced ? fund.navPreciseDisplay : fund.navDisplay
        guard let date = fund.navDate else { return "NAV \(value)" }
        let source = fund.isAMFISourced ? " · Source: AMFI" : ""
        return "NAV \(value) as of \(MutualFundDateText.short(date))\(source)"
    }

    var body: some View {
        Text(text)
            .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
            .foregroundColor(Theme.inkPrimary)
    }
}

struct MutualFundPlanChips: View {
    let fund: MutualFundDTO

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            MutualFundInfoChip(label: (fund.isDirectPlan ?? true) ? "Direct" : "Regular")
            MutualFundInfoChip(label: (fund.isGrowthPlan ?? true) ? "Growth" : "IDCW")
        }
    }
}

private struct MutualFundInfoChip: View {
    let label: String

    var body: some View {
        Text(label.uppercased())
            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
            .tracking(1.2)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.small)
            .foregroundColor(Theme.inkSecondary)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.badge)
                    .stroke(Theme.borderFine, lineWidth: 1)
            )
    }
}

// MARK: - Returns Grid (only figures the backend actually reports)

struct MutualFundReturnsGrid: View {
    let fund: MutualFundDTO
    let historyStart: String?

    private let columns = [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())]

    private var hasReturns: Bool {
        fund.returns1y != nil || fund.returns3y != nil || fund.returns5y != nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            LazyVGrid(columns: columns, spacing: Theme.Spacing.card) {
                if let value = fund.returns1y {
                    MutualFundFactTile(label: "1Y Change", value: IndianFormatter.delta(value), valueColor: colorFor(value))
                }
                if let value = fund.returns3y {
                    MutualFundFactTile(label: "3Y CAGR", value: IndianFormatter.delta(value), valueColor: colorFor(value))
                }
                if let value = fund.returns5y {
                    MutualFundFactTile(label: "5Y CAGR", value: IndianFormatter.delta(value), valueColor: colorFor(value))
                }
                if fund.expenseRatio != nil {
                    MutualFundFactTile(label: "Expense Ratio", value: fund.expenseRatioDisplay)
                }
                if fund.aumCr != nil {
                    MutualFundFactTile(label: "AUM", value: fund.aumDisplay)
                }
                MutualFundFactTile(label: "Scheme Code", value: fund.schemeCode ?? "—")
            }
            MutualFundReturnsCaption(hasReturns: hasReturns, historyStart: historyStart)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func colorFor(_ value: Double) -> Color {
        value >= 0 ? Theme.bullGreen : Theme.bearRed
    }
}

/// Explains why returns are absent: Nivesh records AMFI NAVs from launch and computes no returns yet.
struct MutualFundReturnsCaption: View {
    let hasReturns: Bool
    let historyStart: String?

    private var text: String {
        if hasReturns {
            return "Point-to-point change in NAV. Past performance does not indicate future returns."
        }
        if let historyStart {
            return "Returns appear once Nivesh has recorded at least a year of NAVs for this fund (recording since \(MutualFundDateText.short(historyStart)))."
        }
        return "Nivesh hasn't recorded NAV history for this fund yet."
    }

    var body: some View {
        Text(text)
            .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
            .foregroundColor(Theme.inkTertiary)
    }
}

// MARK: - ISINs

struct MutualFundISINSection: View {
    let fund: MutualFundDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("ISIN")
                .font(Theme.engravedSerif(size: 18, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                if let isin = fund.isinGrowth {
                    MutualFundISINRow(label: "Growth / payout", isin: isin)
                }
                if let isin = fund.isinReinvest {
                    MutualFundISINRow(label: "Reinvestment", isin: isin)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

private struct MutualFundISINRow: View {
    let label: String
    let isin: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(isin)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
                .textSelection(.enabled)
        }
    }
}

struct MutualFundFactTile: View {
    let label: String
    let value: String
    var valueColor: Color = Theme.inkPrimary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                .tracking(1.2)
                .foregroundColor(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                .foregroundColor(valueColor)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - NAV History Chart

struct MutualFundNAVHistorySection: View {
    @ObservedObject var vm: MutualFundDetailViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("NAV History")
                .font(Theme.engravedSerif(size: 18, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            VStack(spacing: Theme.Spacing.medium) {
                MutualFundNAVChart(points: vm.navHistory, isLoading: vm.isLoadingNAV, historyStart: vm.historyStart)

                HStack(spacing: Theme.Spacing.medium) {
                    ForEach(MutualFundNAVRange.allCases) { range in
                        MutualFundRangeButton(range: range, isSelected: vm.selectedRange == range) {
                            vm.changeRange(range)
                        }
                    }
                }
                .padding(.top, Theme.Spacing.small)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

private struct MutualFundNAVChart: View {
    let points: [MutualFundNAVPoint]
    let isLoading: Bool
    let historyStart: String?

    private var emptyText: String {
        if let historyStart {
            return "Nivesh began recording this fund's NAV on \(MutualFundDateText.short(historyStart)). The chart fills in as AMFI publishes new NAVs."
        }
        return "NAV history isn't available for this fund yet."
    }

    var body: some View {
        Group {
            if isLoading && points.isEmpty {
                ProgressView()
                    .tint(Theme.securityGold)
                    .frame(height: 200, alignment: .center)
                    .frame(maxWidth: .infinity)
            } else if points.isEmpty {
                Text(emptyText)
                    .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                    .foregroundColor(Theme.inkTertiary)
                    .multilineTextAlignment(.center)
                    .frame(height: 200, alignment: .center)
                    .frame(maxWidth: .infinity)
            } else {
                Chart(points) { point in
                    LineMark(
                        x: .value("Date", point.parsedDate ?? Date()),
                        y: .value("NAV", point.nav)
                    )
                    .foregroundStyle(Theme.securityGold)
                    .lineStyle(StrokeStyle(lineWidth: 1.5))
                    .interpolationMethod(.catmullRom)

                    AreaMark(
                        x: .value("Date", point.parsedDate ?? Date()),
                        y: .value("NAV", point.nav)
                    )
                    .foregroundStyle(Theme.chartBullGradient)
                    .interpolationMethod(.catmullRom)
                }
                .chartXAxis {
                    AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                        AxisValueLabel()
                            .font(Theme.microLabel())
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .trailing) { _ in
                        AxisValueLabel()
                            .font(Theme.microLabel())
                            .foregroundStyle(Theme.inkTertiary)
                        AxisGridLine().foregroundStyle(Theme.borderFine)
                    }
                }
                .frame(height: 200)
            }
        }
    }
}

private struct MutualFundRangeButton: View {
    let range: MutualFundNAVRange
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            Text(range.rawValue)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .subheadline))
                .foregroundColor(isSelected ? Theme.canvas : Theme.inkSecondary)
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .background(isSelected ? Theme.inkPrimary : Color.clear)
                .cornerRadius(Theme.CornerRadius.small)
        }
        .buttonStyle(EKPressStyle())
        .frame(maxWidth: .infinity)
    }
}

// MARK: - SIP Calculator Entry Point

struct MutualFundSIPEntryPoint: View {
    let action: () -> Void

    var body: some View {
        Button {
            HapticManager.selection()
            action()
        } label: {
            HStack(spacing: Theme.Spacing.card) {
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .fill(Theme.securityGold.opacity(0.12))
                        .frame(width: 44, height: 44)
                    Image(systemName: "indianrupeesign.circle.fill")
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                        .foregroundStyle(Theme.securityGold)
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("SIP Calculator")
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    Text("Project your monthly SIP's maturity value in this fund")
                        .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(2)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Theme.securityGold.opacity(0.6))
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - Riskometer

struct MutualFundRiskometerSection: View {
    let fund: MutualFundDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Riskometer")
                .font(Theme.engravedSerif(size: 18, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            HStack(spacing: Theme.Spacing.card) {
                MutualFundRiskGauge(riskLevel: fund.parsedRiskLevel)

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(fund.parsedRiskLevel?.rawValue ?? "Not Rated")
                        .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)

                    Text(riskDescription)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(3)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }

    private var riskDescription: String {
        switch fund.parsedRiskLevel {
        case .low: return "Investors understand that their principal will be at low risk."
        case .lowToModerate: return "Investors understand that their principal will be at low to moderate risk."
        case .moderate: return "Investors understand that their principal will be at moderate risk."
        case .moderatelyHigh: return "Investors understand that their principal will be at moderately high risk."
        case .high: return "Investors understand that their principal will be at high risk."
        case .veryHigh: return "Investors understand that their principal will be at very high risk."
        case .none: return "Risk rating for this scheme hasn't been reported yet."
        }
    }
}

private struct MutualFundRiskGauge: View {
    let riskLevel: MutualFundRiskLevel?

    private var color: Color {
        switch riskLevel {
        case .low, .lowToModerate: return Theme.bullGreen
        case .moderate, .moderatelyHigh: return Theme.holdAmber
        case .high, .veryHigh: return Theme.bearRed
        case .none: return Theme.inkTertiary
        }
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(Theme.borderFine, lineWidth: 8)
            Circle()
                .trim(from: 0, to: riskLevel?.gaugeFraction ?? 0)
                .stroke(color, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Text(riskLevel != nil ? String(format: "%.0f%%", (riskLevel?.gaugeFraction ?? 0) * 100) : "—")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .foregroundColor(color)
        }
        .frame(width: 72, height: 72)
    }
}

// MARK: - Fund Manager

struct MutualFundFundManagerSection: View {
    let fund: MutualFundDTO

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Fund Management")
                .font(Theme.engravedSerif(size: 18, weight: .semibold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)

            HStack(spacing: Theme.Spacing.card) {
                Circle()
                    .fill(Theme.canvasShadow)
                    .frame(width: 44, height: 44)
                    .overlay(
                        Image(systemName: "person.fill")
                            .foregroundColor(Theme.inkSecondary)
                    )

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(fund.fundManager ?? "Fund manager not reported")
                        .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                    Text(fund.amc)
                        .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                }
                Spacer()
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

// MARK: - Sample Data Stamp

/// Shown on any fund the backend flags `is_sample` (seeded catalog with frozen
/// figures, not a live AMFI feed) so it is never mistaken for real fund data.
struct MutualFundSampleDataStamp: View {
    var body: some View {
        Text("SAMPLE DATA · NOT LIVE FUND FIGURES")
            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
            .tracking(1.2)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .foregroundColor(Theme.holdAmber)
            .background(Theme.holdAmber.opacity(0.12))
            .cornerRadius(Theme.CornerRadius.badge)
    }
}
