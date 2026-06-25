import Combine
import SwiftUI

// MARK: - Period & Consolidation Enums

enum FinancialPeriodType: String, CaseIterable {
    case quarterly = "QUARTERLY"
    case annual = "ANNUAL"

    var label: String { rawValue }
}

enum FinancialConsolidationType: String, CaseIterable {
    case standalone = "STANDALONE"
    case consolidated = "CONSOLIDATED"

    var label: String { rawValue }
}

// MARK: - Financial Statement Response (Rich Model)

/// Lightweight container for expanded financial data.
/// When populated, enables Income Statement / Balance Sheet / Cash Flow / Ratios sections.
/// Falls back gracefully when nil — only the basic quarterly table is shown.
struct ExpandedFinancialData {
    let ticker: String
    let periodType: String
    let consolidation: String
    let periods: [FinancialPeriod]
    let lineItems: [FinancialLineItem]
    let availablePeriods: [String]

    /// Whether any period in this dataset belongs to a bank.
    var isBank: Bool { periods.contains { $0.isBank } }

    /// Line items filtered by group key (e.g. "income_statement", "balance_sheet", "cash_flow", "ratios").
    func items(in group: String) -> [FinancialLineItem] {
        lineItems.filter { $0.group == group }
    }
}

// MARK: - Main View

struct StockFinancialsView: View {
    @ObservedObject var vm: StockProfileViewModel

    @State private var periodType: FinancialPeriodType = .quarterly
    @State private var consolidation: FinancialConsolidationType = .standalone
    @State private var selectedPeriodLabel: String = ""

    // When the backend provides richer data via StockProfileResponse,
    // populate this to unlock all expanded sections.
    var expandedData: ExpandedFinancialData? = nil

    private var effectivePeriods: [String] {
        if let ed = expandedData, !ed.availablePeriods.isEmpty {
            return ed.availablePeriods
        }
        // Fallback: derive from quarterlyFinancials
        return vm.quarterlyFinancials.map(\.label)
    }

    private var isBank: Bool {
        expandedData?.isBank ?? false
    }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                if vm.financialsLoading {
                    SPSkeletonBlock(rows: 10)
                } else if vm.quarterlyFinancials.isEmpty && vm.piotroski == nil {
                    SPEmptyStateView(message: "Financial data unavailable")
                } else {
                    controlsSection
                    quarterlySummarySection
                    incomeStatementSection
                    balanceSheetSection
                    cashFlowSection
                    ratiosSection
                    piotroskiSection
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchFinancials() }
        .onAppear {
            if selectedPeriodLabel.isEmpty, let first = effectivePeriods.first {
                selectedPeriodLabel = first
            }
        }
    }

    // MARK: - Controls

    private var controlsSection: some View {
        FinancialControlsCard(
            periodType: $periodType,
            consolidation: $consolidation,
            periods: effectivePeriods,
            selectedPeriodLabel: $selectedPeriodLabel
        )
    }

    // MARK: - Quarterly Summary (Compact Table — existing data)

    private var quarterlySummarySection: some View {
        FinancialPeriodTableSection(
            title: "QUARTERLY SUMMARY",
            quarters: vm.quarterlyFinancials
        )
    }

    // MARK: - Income Statement

    @ViewBuilder
    private var incomeStatementSection: some View {
        if let ed = expandedData {
            FinancialStatementTableSection(
                title: "INCOME STATEMENT",
                lineItems: ed.items(in: "income_statement"),
                periodLabels: ed.availablePeriods,
                isBank: isBank
            )
        }
    }

    // MARK: - Balance Sheet

    @ViewBuilder
    private var balanceSheetSection: some View {
        if let ed = expandedData {
            FinancialStatementTableSection(
                title: "BALANCE SHEET",
                lineItems: ed.items(in: "balance_sheet"),
                periodLabels: ed.availablePeriods,
                isBank: isBank
            )
        }
    }

    // MARK: - Cash Flow

    @ViewBuilder
    private var cashFlowSection: some View {
        if let ed = expandedData {
            FinancialStatementTableSection(
                title: "CASH FLOW",
                lineItems: ed.items(in: "cash_flow"),
                periodLabels: ed.availablePeriods,
                isBank: isBank
            )
        }
    }

    // MARK: - Ratios

    @ViewBuilder
    private var ratiosSection: some View {
        if let ed = expandedData {
            FinancialRatiosGridSection(
                lineItems: ed.items(in: "ratios"),
                periodLabels: ed.availablePeriods,
                isBank: isBank
            )
        }
    }

    // MARK: - Piotroski

    @ViewBuilder
    private var piotroskiSection: some View {
        if let piotroski = vm.piotroski {
            PiotroskiScoreCardView(data: piotroski)
        }
    }
}

// MARK: - Financial Controls Card

struct FinancialControlsCard: View {
    @Binding var periodType: FinancialPeriodType
    @Binding var consolidation: FinancialConsolidationType
    let periods: [String]
    @Binding var selectedPeriodLabel: String

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            FinancialSegmentedPicker(
                title: "PERIOD",
                selection: $periodType,
                cases: FinancialPeriodType.allCases
            )
            FinancialSegmentedPicker(
                title: "VIEW",
                selection: $consolidation,
                cases: FinancialConsolidationType.allCases
            )
            FinancialPeriodStrip(
                periods: periods,
                selected: $selectedPeriodLabel
            )
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Segmented Picker (Generic)

struct FinancialSegmentedPicker<T: RawRepresentable & CaseIterable & Hashable>: View where T.RawValue == String, T.AllCases: RandomAccessCollection {
    let title: String
    @Binding var selection: T
    let cases: [T]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            Text(title)
                .font(Theme.officialStampFont(size: 8))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
            HStack(spacing: Theme.Spacing.small) {
                ForEach(cases, id: \.rawValue) { option in
                    Button {
    HapticManager.selection()
                        HapticManager.selection()
                        selection = option
                    } label: {
                        Text(option.rawValue)
                            .font(Theme.officialStampFont(size: 10))
                            .tracking(1.0)
                            .foregroundStyle(
                                selection.rawValue == option.rawValue
                                    ? Theme.inkPrimary : Theme.inkTertiary
                            )
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.small)
                            .background(
                                selection.rawValue == option.rawValue
                                    ? Theme.securityGold.opacity(0.12)
                                    : Color.clear
                            )
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                    .stroke(
                                        selection.rawValue == option.rawValue
                                            ? Theme.securityGold.opacity(0.3)
                                            : Theme.borderFine,
                                        lineWidth: 0.5
                                    )
                            )
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

// MARK: - Period Strip (Horizontal Scroll)

struct FinancialPeriodStrip: View {
    let periods: [String]
    @Binding var selected: String

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Theme.Spacing.tight) {
                ForEach(periods, id: \.self) { period in
                    Button {
    HapticManager.selection()
                        HapticManager.selection()
                        selected = period
                    } label: {
                        Text(period)
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(selected == period ? Theme.inkPrimary : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.standard)
                            .padding(.vertical, Theme.Spacing.tight)
                            .background(
                                selected == period
                                    ? Theme.securityGold.opacity(0.10)
                                    : Color.clear
                            )
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                                    .stroke(
                                        selected == period
                                            ? Theme.securityGold.opacity(0.25)
                                            : Theme.borderFine,
                                        lineWidth: 0.5
                                    )
                            )
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

// MARK: - Financial Period Table (Quarterly Summary — uses existing model)

struct FinancialPeriodTableSection: View {
    let title: String
    let quarters: [QuarterlyFinancial]

    private var shownQuarters: [QuarterlyFinancial] {
        Array(quarters.prefix(8))
    }

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            FinancialStampHeader(title: title)

            // Column headers
            HStack(spacing: Theme.Spacing.none) {
                Text("PERIOD")
                    .frame(width: colW * 0.30, alignment: .leading)
                Text("REVENUE")
                    .frame(width: colW * 0.35, alignment: .trailing)
                Text("NET PROFIT")
                    .frame(width: colW * 0.35, alignment: .trailing)
            }
            .font(Theme.officialStampFont(size: 8))
            .foregroundStyle(Theme.inkSecondary)
            .padding(.horizontal, Theme.Spacing.medium)

            ForEach(shownQuarters) { q in
                HStack(spacing: Theme.Spacing.none) {
                    Text(q.label)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.30, alignment: .leading)
                    Text(IndianFormatter.priceCompact(q.revenue))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.35, alignment: .trailing)
                    Text(IndianFormatter.priceCompact(q.netProfit))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(q.netProfit >= 0 ? Theme.bullGreen : Theme.bearRed)
                        .frame(width: colW * 0.35, alignment: .trailing)
                }
                .padding(.horizontal, Theme.Spacing.medium)
                .padding(.vertical, Theme.Spacing.small)
                .overlay(
                    Rectangle().fill(Theme.borderFine).frame(height: 0.5),
                    alignment: .bottom
                )
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Financial Statement Table (Expanded — uses rich line items)

struct FinancialStatementTableSection: View {
    let title: String
    let lineItems: [FinancialLineItem]
    let periodLabels: [String]
    let isBank: Bool

    private var visiblePeriods: [String] {
        Array(periodLabels.prefix(4))
    }

    private var filteredItems: [FinancialLineItem] {
        lineItems.filter { item in
            // If bank-specific and not a bank, hide
            if item.bankSpecific && !isBank { return false }
            return true
        }
    }

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            FinancialStampHeader(title: title)

            if filteredItems.isEmpty {
                HStack {
                    Spacer()
                    Text("No data available for selected filters")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                    Spacer()
                }
                .padding(.vertical, Theme.Spacing.medium)
            } else {
                // Horizontal scroll for the value columns
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(alignment: .top, spacing: Theme.Spacing.none) {
                        // Sticky first column: line item names
                        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                            // Header spacer
                            Text("LINE ITEM")
                                .font(Theme.officialStampFont(size: 8))
                                .foregroundStyle(Theme.inkSecondary)
                                .frame(width: colW * 0.34, alignment: .leading)
                                .padding(.vertical, Theme.Spacing.tight)
                                .padding(.horizontal, Theme.Spacing.medium)

                            ForEach(filteredItems) { item in
                                Text(item.label)
                                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .lineLimit(2)
                                    .fixedSize(horizontal: false, vertical: true)
                                    .frame(width: colW * 0.34, alignment: .leading)
                                    .padding(.vertical, Theme.Spacing.small)
                                    .padding(.horizontal, Theme.Spacing.medium)
                                    .background(
                                        (filteredItems.firstIndex(where: { $0.id == item.id }) ?? 0) % 2 == 0
                                            ? Color.clear
                                            : Theme.inkTertiary.opacity(0.03)
                                    )
                            }
                        }

                        // Scrollable value columns
                        ForEach(visiblePeriods, id: \.self) { period in
                            VStack(alignment: .trailing, spacing: Theme.Spacing.none) {
                                Text(period)
                                    .font(Theme.officialStampFont(size: 8))
                                    .foregroundStyle(Theme.inkSecondary)
                                    .frame(width: colW * 0.30, alignment: .trailing)
                                    .padding(.vertical, Theme.Spacing.tight)
                                    .padding(.horizontal, Theme.Spacing.tight)

                                ForEach(filteredItems) { item in
                                    FinancialValueCell(
                                        item: item,
                                        period: period,
                                        width: colW * 0.30,
                                        isAlternateRow: (filteredItems.firstIndex(where: { $0.id == item.id }) ?? 0) % 2 != 0
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Financial Value Cell

struct FinancialValueCell: View {
    let item: FinancialLineItem
    let period: String
    let width: CGFloat
    let isAlternateRow: Bool

    private var rawValue: Double? {
        item.values[period] ?? nil
    }

    private var qoq: Double? {
        item.qoqChangePct[period] ?? nil
    }

    private var yoy: Double? {
        item.yoyChangePct[period] ?? nil
    }

    private var displayValue: String {
        guard let v = rawValue else { return "—" }
        if item.isPercentage {
            return IndianFormatter.percent(v)
        }
        return IndianFormatter.priceCompact(v)
    }

    private var qoqColor: Color {
        guard let q = qoq else { return Theme.inkTertiary }
        return q >= 0 ? Theme.bullGreen : Theme.bearRed
    }

    private var qoqText: String {
        guard let q = qoq else { return "" }
        let sign = q >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", q))%"
    }

    var body: some View {
        VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
            Text(displayValue)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(rawValue == nil ? Theme.inkTertiary : Theme.inkPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.7)

            if qoq != nil || yoy != nil {
                HStack(spacing: Theme.Spacing.small) {
                    if let q = qoq {
                        Text("QoQ \(q >= 0 ? "+" : "")\(String(format: "%.1f", q))%")
                            .font(Theme.serialNumberFont(size: 8, relativeTo: .caption2))
                            .foregroundStyle(q >= 0 ? Theme.bullGreen : Theme.bearRed)
                            .lineLimit(1)
                    }
                    if let y = yoy {
                        Text("YoY \(y >= 0 ? "+" : "")\(String(format: "%.1f", y))%")
                            .font(Theme.serialNumberFont(size: 8, relativeTo: .caption2))
                            .foregroundStyle(y >= 0 ? Theme.bullGreen : Theme.bearRed)
                            .lineLimit(1)
                    }
                }
            }
        }
        .frame(width: width, alignment: .trailing)
        .padding(.vertical, Theme.Spacing.small)
        .padding(.horizontal, Theme.Spacing.tight)
        .background(
            isAlternateRow
                ? Theme.inkTertiary.opacity(0.03)
                : Color.clear
        )
    }
}

// MARK: - Financial Ratios Grid (Expanded)

struct FinancialRatiosGridSection: View {
    let lineItems: [FinancialLineItem]
    let periodLabels: [String]
    let isBank: Bool

    private var visiblePeriods: [String] {
        Array(periodLabels.prefix(3))
    }

    private var filteredItems: [FinancialLineItem] {
        lineItems.filter { item in
            if item.bankSpecific && !isBank { return false }
            return true
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            FinancialStampHeader(title: "KEY RATIOS")

            if filteredItems.isEmpty {
                HStack {
                    Spacer()
                    Text("No ratio data available for selected filters")
                        .font(Theme.officialStampFont(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                    Spacer()
                }
                .padding(.vertical, Theme.Spacing.medium)
            } else {
                LazyVGrid(
                    columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ],
                    spacing: Theme.Spacing.standard
                ) {
                    ForEach(filteredItems) { item in
                        RatioCardView(
                            item: item,
                            periodLabels: visiblePeriods
                        )
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Ratio Card (single ratio in a mini card)

struct RatioCardView: View {
    let item: FinancialLineItem
    let periodLabels: [String]

    private var latestPeriod: String? { periodLabels.first }
    private var latestValue: Double? {
        guard let p = latestPeriod else { return nil }
        return item.values[p] ?? nil
    }

    private var displayValue: String {
        guard let v = latestValue else { return "—" }
        if item.isPercentage {
            return IndianFormatter.percent(v)
        }
        return String(format: "%.2f", v)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(item.label)
                .font(Theme.officialStampFont(size: 9))
                .tracking(0.8)
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)

            Text(displayValue)
                .font(Theme.serialNumberFont(size: 15, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.6)

            // Show per-period values
            ForEach(periodLabels.prefix(3), id: \.self) { period in
                if let v = item.values[period] {
                    HStack(spacing: Theme.Spacing.xSmall) {
                        Text(period)
                            .font(Theme.officialStampFont(size: 7))
                            .foregroundStyle(Theme.inkTertiary)
                        Spacer()
                        Text(item.isPercentage ? IndianFormatter.percent(v) : String(format: "%.2f", v))
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Piotroski F-Score Card (Enhanced)

struct PiotroskiScoreCardView: View {
    let data: PiotroskiData

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Header row with score and grade
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    FinancialStampHeader(title: "PIOTROSKI F-SCORE")

                    if let fScore = data.fScore {
                        let maxScore = data.maxPossible ?? 9
                        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                            Text("\(fScore)")
                                .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                                .foregroundStyle(piotroskiColor(fScore))
                            Text("/ \(maxScore)")
                                .font(Theme.officialStampFont(size: 12))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
                .explainableTerm("Piotroski Score")

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.small) {
                    if let grade = data.grade {
                        BanknoteSignalBadge(
                            text: grade,
                            color: gradeColor(grade),
                            rotation: -2
                        )
                    }
                    if let confidence = data.confidence {
                        Text(confidence)
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
            }

            // Score interpretation bar
            if let fScore = data.fScore {
                PiotroskiScoreBar(score: fScore)
            }

            // Check grid
            if let checks = data.checks, !checks.isEmpty {
                GuillocheDivider()

                LazyVGrid(
                    columns: [
                        GridItem(.flexible()),
                        GridItem(.flexible())
                    ],
                    spacing: Theme.Spacing.tight
                ) {
                    ForEach(checks.keys.sorted(), id: \.self) { key in
                        PiotroskiCheckRow(
                            label: formatCheckLabel(key),
                            passed: checks[key] == "PASS"
                        )
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func piotroskiColor(_ score: Int) -> Color {
        if score >= 7 { return Theme.bullGreen }
        if score >= 4 { return Theme.holdAmber }
        return Theme.bearRed
    }

    private func gradeColor(_ grade: String) -> Color {
        switch grade {
        case "STRONG": return Theme.bullGreen
        case "GOOD": return Theme.bullGreenLight
        case "DISTRESS": return Theme.bearRed
        case "WEAK": return Theme.bearRedLight
        default: return Theme.holdAmber
        }
    }

    private func formatCheckLabel(_ key: String) -> String {
        key.replacingOccurrences(of: "_", with: " ")
            .split(separator: " ")
            .map { $0.prefix(1).uppercased() + $0.dropFirst().lowercased() }
            .joined(separator: " ")
    }
}

// MARK: - Piotroski Score Bar

struct PiotroskiScoreBar: View {
    let score: Int

    private let maxScore: Int = 9

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.xSmall) {
                Text("WEAK")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bearRed)
                Spacer()
                Text("STRONG")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bullGreen)
            }

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    // Background track
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.inkTertiary.opacity(0.12))
                        .frame(height: 6)

                    // Filled portion
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(scoreBarGradient)
                        .frame(width: geo.size.width * CGFloat(score) / CGFloat(maxScore), height: 6)

                    // Score indicator dot
                    Circle()
                        .fill(Theme.securityGold)
                        .frame(width: 10, height: 10)
                        .shadow(color: Theme.securityGold.opacity(0.4), radius: 3)
                        .offset(x: geo.size.width * CGFloat(score) / CGFloat(maxScore) - 5)
                }
            }
            .frame(height: 10)

            HStack {
                ForEach(0..<10) { i in
                    Text("\(i)")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(i == score ? Theme.securityGold : Theme.inkTertiary)
                    if i < 9 { Spacer() }
                }
            }
        }
    }

    private var scoreBarGradient: LinearGradient {
        LinearGradient(
            colors: [Theme.bearRed, Theme.holdAmber, Theme.bullGreen],
            startPoint: .leading,
            endPoint: .trailing
        )
    }
}

// MARK: - Piotroski Check Row

struct PiotroskiCheckRow: View {
    let label: String
    let passed: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle()
                .fill(passed ? Theme.bullGreen : Theme.bearRed)
                .frame(width: 6, height: 6)
            Text(passed ? "✓" : "✗")
                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                .foregroundStyle(passed ? Theme.bullGreen : Theme.bearRed)
            Text(label)
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(1)
            Spacer()
        }
    }
}

// MARK: - Shared Section Header

struct FinancialStampHeader: View {
    let title: String

    var body: some View {
        Text(title)
            .font(Theme.officialStampFont(size: 9))
            .tracking(1.5)
            .foregroundStyle(Theme.inkTertiary)
    }
}

// MARK: - Preview

#if DEBUG
struct StockFinancialsView_Previews: PreviewProvider {
    static var previews: some View {
        let vm = StockProfileViewModel(ticker: "RELIANCE", exchange: "NSE")
        StockFinancialsView(vm: vm)
            .preferredColorScheme(.dark)
    }
}
#endif
