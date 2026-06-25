import Combine
import SwiftUI
import Charts

// MARK: - StockShareholdingView

struct StockShareholdingView: View {
    @ObservedObject var vm: StockProfileViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                if vm.holdersLoading {
                    SPSkeletonBlock(rows: 5)
                    SPSkeletonBlock(rows: 3)
                } else if let sh = vm.shareholding {
                    ShareholdingDonutChartSection(data: sh)

                    if sh.availableQuarters.count > 1 {
                        GuillocheDivider()
                        ShareholdingQuarterPicker(
                            quarters: sh.availableQuarters,
                            selected: sh.latestQuarter
                        )
                    }

                    GuillocheDivider()
                    ShareholdingCategoryGrid(categories: sh.categories)

                    if !sh.categories.isEmpty {
                        GuillocheDivider()
                        ShareholdingWarningBadges(
                            categories: sh.categories,
                            trend: sh.holdingTrend,
                            pledgePct: sh.promoterPledgePct,
                            pledgeQoq: sh.promoterPledgeQoqChange
                        )
                    }

                    if !sh.topHolders.isEmpty {
                        GuillocheDivider()
                        TopHoldersTableSection(holders: sh.topHolders)
                    }

                    if !sh.holdingTrend.isEmpty && sh.holdingTrend.count >= 2 {
                        GuillocheDivider()
                        HoldingTrendChartSection(trend: sh.holdingTrend)
                    }

                    if let pledge = sh.promoterPledgePct {
                        GuillocheDivider()
                        PledgePercentageSection(
                            pledgePct: pledge,
                            qoqChange: sh.promoterPledgeQoqChange
                        )
                    }
                } else {
                    SPEmptyStateView(message: "Shareholding data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchShareholding() }
    }
}

// MARK: - Donut Chart Section

struct ShareholdingDonutChartSection: View {
    let data: ShareholdingResponse

    private var categoryColors: [String: Color] {
        [
            "Promoter": Theme.bullGreen,
            "FII": Theme.securityGold,
            "DII": Theme.holdAmber,
            "Public": Theme.inkTertiary,
            "Others": Theme.inkSecondary
        ]
    }

    private var instHoldingPct: Double {
        data.categories
            .filter { ["Promoter", "FII", "DII"].contains($0.name) }
            .reduce(0) { $0 + $1.currentPct }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("SHAREHOLDING PATTERN")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            ZStack {
                Chart {
                    ForEach(data.categories) { cat in
                        SectorMark(
                            angle: .value("Holding", cat.currentPct),
                            innerRadius: .ratio(0.68),
                            angularInset: 1.5
                        )
                        .foregroundStyle(categoryColors[cat.name] ?? Theme.inkTertiary)
                    }
                }
                .frame(height: UIScreen.main.bounds.height * 0.22)

                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("INSTITUTIONAL")
                        .font(Theme.officialStampFont(size: 8))
                        .tracking(1.0)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(String(format: "%.1f%%", instHoldingPct))
                        .font(Theme.serialNumberFont(size: 24, relativeTo: .title2))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .frame(width: UIScreen.main.bounds.width * 0.22)
            }

            let legendColumns = [
                GridItem(.flexible(), spacing: Theme.Spacing.standard),
                GridItem(.flexible(), spacing: Theme.Spacing.standard),
                GridItem(.flexible(), spacing: Theme.Spacing.standard)
            ]
            LazyVGrid(columns: legendColumns, alignment: .leading, spacing: Theme.Spacing.tight) {
                ForEach(data.categories) { cat in
                    HStack(spacing: Theme.Spacing.small) {
                        Circle()
                            .fill(categoryColors[cat.name] ?? Theme.inkTertiary)
                            .frame(width: Theme.Spacing.medium, height: Theme.Spacing.medium)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(cat.name.uppercased())
                                .font(Theme.officialStampFont(size: 7))
                                .foregroundStyle(Theme.inkTertiary)
                            Text(String(format: "%.1f%%", cat.currentPct))
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Quarter Picker

struct ShareholdingQuarterPicker: View {
    let quarters: [String]
    let selected: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("QUARTER")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.small) {
                    ForEach(quarters, id: \.self) { q in
                        ShareholdingQuarterChip(
                            label: q,
                            isSelected: q == selected
                        )
                    }
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct ShareholdingQuarterChip: View {
    let label: String
    let isSelected: Bool

    var body: some View {
        Text(label)
            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
            .foregroundStyle(isSelected ? Theme.inkPrimary : Theme.inkTertiary)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .background(isSelected ? Theme.securityGold.opacity(0.12) : Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                    .stroke(isSelected ? Theme.securityGold.opacity(0.4) : Theme.borderFine, lineWidth: 0.5)
            )
    }
}

// MARK: - Category Breakdown Grid

struct ShareholdingCategoryGrid: View {
    let categories: [ShareholderCategory]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("CATEGORY BREAKDOWN")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            LazyVGrid(
                columns: [GridItem(.flexible()), GridItem(.flexible())],
                spacing: Theme.Spacing.medium
            ) {
                ForEach(categories) { cat in
                    ShareholdingCategoryCard(category: cat)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct ShareholdingCategoryCard: View {
    let category: ShareholderCategory

    private var catColor: Color {
        switch category.name {
        case "Promoter": return Theme.bullGreen
        case "FII": return Theme.securityGold
        case "DII": return Theme.holdAmber
        case "Public": return Theme.inkTertiary
        default: return Theme.inkSecondary
        }
    }

    private var qoqColor: Color {
        guard let change = category.qoqChangeBps else { return Theme.inkTertiary }
        return change >= 0 ? Theme.bullGreen : Theme.bearRed
    }

    private var yoyColor: Color {
        guard let change = category.yoyChangeBps else { return Theme.inkTertiary }
        return change >= 0 ? Theme.bullGreen : Theme.bearRed
    }

    private func qoqFormatted(_ bps: Double?) -> String {
        guard let bps = bps else { return "—" }
        let sign = bps >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", bps / 100))%"
    }

    private func yoyFormatted(_ bps: Double?) -> String {
        qoqFormatted(bps)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack(spacing: Theme.Spacing.small) {
                Circle()
                    .fill(catColor)
                    .frame(width: Theme.Spacing.small, height: Theme.Spacing.small)
                Text(category.name.uppercased())
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(0.8)
                    .foregroundStyle(Theme.inkTertiary)
            }

            Text(String(format: "%.2f%%", category.currentPct))
                .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                .foregroundStyle(catColor)

            HStack(spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("QoQ")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                    HStack(spacing: Theme.Spacing.xSmall) {
                        arrowIcon(for: category.qoqChangeBps)
                        Text(qoqFormatted(category.qoqChangeBps))
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(qoqColor)
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("YoY")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                    HStack(spacing: Theme.Spacing.xSmall) {
                        arrowIcon(for: category.yoyChangeBps)
                        Text(yoyFormatted(category.yoyChangeBps))
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(yoyColor)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }

    @ViewBuilder
    private func arrowIcon(for bps: Double?) -> some View {
        if let bps = bps {
            if bps > 0 {
                Image(systemName: "arrowtriangle.up.fill")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bullGreen)
            } else if bps < 0 {
                Image(systemName: "arrowtriangle.down.fill")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bearRed)
            } else {
                Text("→")
                    .font(Theme.serialNumberFont(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
    }
}

// MARK: - Warning Badges

struct ShareholdingWarningBadges: View {
    let categories: [ShareholderCategory]
    let trend: [ShareholdingQuarter]
    let pledgePct: Double?
    let pledgeQoq: Double?

    private var computedWarnings: [(label: String, color: Color)] {
        var warnings: [(label: String, color: Color)] = []

        // Promoter holding falling: dropped >2% over last 4 quarters
        if trend.count >= 5 {
            let latest = trend.last?.promoterPct ?? 0
            let fourBack = trend[trend.count - 5].promoterPct
            if latest > 0 && fourBack > 0 && (fourBack - latest) > 2.0 {
                warnings.append(("Promoter Holding Falling", Theme.bearRed))
            }
        } else if trend.count >= 2 {
            let latest = trend.last?.promoterPct ?? 0
            let first = trend.first?.promoterPct ?? 0
            if latest > 0 && first > 0 && (first - latest) > 2.0 {
                warnings.append(("Promoter Holding Falling", Theme.bearRed))
            }
        }

        // Pledge increasing: increased >5%
        if let qoq = pledgeQoq, qoq > 5.0 {
            warnings.append(("Pledge Increasing", Theme.bearRed))
        }

        // FII selling: FII dropped >3% in last 2 quarters
        if trend.count >= 3 {
            let latest = trend.last?.fiiPct ?? 0
            let twoBack = trend[trend.count - 3].fiiPct
            if latest > 0 && twoBack > 0 && (twoBack - latest) > 3.0 {
                warnings.append(("FII Selling", Theme.bearRed))
            }
        } else if let fiiCat = categories.first(where: { $0.name == "FII" }),
                  let qoq = fiiCat.qoqChangeBps, qoq < -300 {
            warnings.append(("FII Selling", Theme.bearRed))
        }

        // DII accumulating: DII increased >3% in last 2 quarters
        if trend.count >= 3 {
            let latest = trend.last?.diiPct ?? 0
            let twoBack = trend[trend.count - 3].diiPct
            if latest > 0 && twoBack > 0 && (latest - twoBack) > 3.0 {
                warnings.append(("DII Accumulating", Theme.bullGreen))
            }
        } else if let diiCat = categories.first(where: { $0.name == "DII" }),
                  let qoq = diiCat.qoqChangeBps, qoq > 300 {
            warnings.append(("DII Accumulating", Theme.bullGreen))
        }

        // High pledge warning
        if let pledge = pledgePct, pledge > 20.0 {
            warnings.append(("High Pledge >20%", Theme.bearRed))
        }

        return warnings
    }

    var body: some View {
        if computedWarnings.isEmpty {
            EmptyView()
        } else {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("WARNINGS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                VStack(spacing: Theme.Spacing.tight) {
                    ForEach(computedWarnings, id: \.label) { warning in
                        ShareholdingWarningBadgeRow(label: warning.label, color: warning.color)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

struct ShareholdingWarningBadgeRow: View {
    let label: String
    let color: Color

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle()
                .fill(color)
                .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
            Text(label.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.0)
                .foregroundStyle(color)
            Spacer()
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .background(color.opacity(0.07))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(color.opacity(0.25), lineWidth: 0.5)
        )
    }
}

// MARK: - Top Holders Table

struct TopHoldersTableSection: View {
    let holders: [TopHolder]

    private var sortedHolders: [TopHolder] {
        holders.sorted { $0.holdingPct > $1.holdingPct }
    }

    private var catColor: [String: Color] {
        [
            "Promoter": Theme.bullGreen,
            "FII": Theme.securityGold,
            "DII": Theme.holdAmber,
            "Public": Theme.inkTertiary,
            "Others": Theme.inkSecondary
        ]
    }

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding - 2 * Theme.Spacing.card

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("TOP HOLDERS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.none) {
                Text("HOLDER")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.38, alignment: .leading)
                Text("CATEGORY")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.24, alignment: .trailing)
                Text("STAKE")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.18, alignment: .trailing)
                Text("QoQ")
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkSecondary)
                    .frame(width: colW * 0.20, alignment: .trailing)
            }
            .padding(.horizontal, Theme.Spacing.medium)

            let shown = Array(sortedHolders.prefix(10))
            ForEach(shown) { holder in
                TopHolderRow(holder: holder, colW: colW)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct TopHolderRow: View {
    let holder: TopHolder
    let colW: CGFloat

    private var catColor: Color {
        switch holder.category {
        case "Promoter": return Theme.bullGreen
        case "FII": return Theme.securityGold
        case "DII": return Theme.holdAmber
        case "Public": return Theme.inkTertiary
        default: return Theme.inkSecondary
        }
    }

    private var qoqFormatted: String {
        guard let bps = holder.qoqChangeBps else { return "—" }
        let sign = bps >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", bps / 100))%"
    }

    private var qoqColor: Color {
        guard let change = holder.qoqChangeBps else { return Theme.inkTertiary }
        return change >= 0 ? Theme.bullGreen : Theme.bearRed
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            HStack(spacing: Theme.Spacing.small) {
                Circle()
                    .fill(catColor)
                    .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
                Text(holder.name)
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.72)
            }
            .frame(width: colW * 0.38, alignment: .leading)

            Text(holder.category.uppercased())
                .font(Theme.officialStampFont(size: 7))
                .foregroundStyle(catColor)
                .frame(width: colW * 0.24, alignment: .trailing)

            Text(String(format: "%.2f%%", holder.holdingPct))
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption))
                .foregroundStyle(Theme.inkPrimary)
                .frame(width: colW * 0.18, alignment: .trailing)

            Text(qoqFormatted)
                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                .foregroundStyle(qoqColor)
                .frame(width: colW * 0.20, alignment: .trailing)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.small)
        .overlay(Rectangle().fill(Theme.borderFine).frame(height: 0.5), alignment: .bottom)
    }
}

// MARK: - Holding Trend Chart

struct HoldingTrendChartSection: View {
    let trend: [ShareholdingQuarter]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("HOLDING TREND")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Chart {
                ForEach(trend) { q in
                    LineMark(
                        x: .value("Quarter", q.quarter),
                        y: .value("Promoter %", q.promoterPct)
                    )
                    .foregroundStyle(Theme.bullGreen)
                    .interpolationMethod(.catmullRom)

                    AreaMark(
                        x: .value("Quarter", q.quarter),
                        y: .value("Promoter %", q.promoterPct)
                    )
                    .foregroundStyle(Theme.bullGreen.opacity(0.06))
                    .interpolationMethod(.catmullRom)

                    LineMark(
                        x: .value("Quarter", q.quarter),
                        y: .value("FII %", q.fiiPct)
                    )
                    .foregroundStyle(Theme.securityGold)
                    .interpolationMethod(.catmullRom)

                    LineMark(
                        x: .value("Quarter", q.quarter),
                        y: .value("DII %", q.diiPct)
                    )
                    .foregroundStyle(Theme.holdAmber)
                    .interpolationMethod(.catmullRom)
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: min(trend.count, 6))) { _ in
                    AxisValueLabel()
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .chartYAxis {
                AxisMarks { _ in
                    AxisValueLabel()
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.22)

            HStack(spacing: Theme.Spacing.standard) {
                trendLegendDot(color: Theme.bullGreen, label: "Promoter")
                trendLegendDot(color: Theme.securityGold, label: "FII")
                trendLegendDot(color: Theme.holdAmber, label: "DII")
            }
            .frame(maxWidth: .infinity)

            if trend.count >= 2 {
                let latest = trend.last!
                let prev = trend[trend.count - 2]
                HoldingTrendSummary(latest: latest, previous: prev)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func trendLegendDot(color: Color, label: String) -> some View {
        HStack(spacing: Theme.Spacing.small) {
            Circle()
                .fill(color)
                .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(Theme.inkTertiary)
        }
    }
}

struct HoldingTrendSummary: View {
    let latest: ShareholdingQuarter
    let previous: ShareholdingQuarter

    var body: some View {
        let items: [(label: String, latest: Double, old: Double, color: Color)] = [
            ("Promoter", latest.promoterPct, previous.promoterPct, Theme.bullGreen),
            ("FII", latest.fiiPct, previous.fiiPct, Theme.securityGold),
            ("DII", latest.diiPct, previous.diiPct, Theme.holdAmber)
        ]

        HStack(spacing: Theme.Spacing.none) {
            ForEach(items, id: \.label) { item in
                let change = item.latest - item.old
                let sign = change >= 0 ? "+" : ""
                let changeStr = "\(sign)\(String(format: "%.2f", change))%"

                VStack(spacing: Theme.Spacing.xSmall) {
                    Text(item.label)
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(String(format: "%.1f%%", item.latest))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(item.color)
                    Text(changeStr)
                        .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                        .foregroundStyle(change >= 0 ? Theme.bullGreen : Theme.bearRed)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding(.top, Theme.Spacing.tight)
    }
}

// MARK: - Pledge Percentage Section

struct PledgePercentageSection: View {
    let pledgePct: Double
    let qoqChange: Double?

    private var isHighRisk: Bool {
        pledgePct > 20.0
    }

    private var isIncreasing: Bool {
        (qoqChange ?? 0) > 0
    }

    private var statusColor: Color {
        if pledgePct > 50.0 {
            return Theme.bearRed
        } else if pledgePct > 20.0 {
            return Theme.holdAmber
        } else {
            return Theme.bullGreen
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER PLEDGE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(alignment: .firstTextBaseline) {
                Text(String(format: "%.1f%%", pledgePct))
                    .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                    .foregroundStyle(statusColor)

                if let qoq = qoqChange, qoq != 0 {
                    HStack(spacing: Theme.Spacing.xSmall) {
                        Image(systemName: qoq > 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(qoq > 0 ? Theme.bearRed : Theme.bullGreen)
                        Text("\(qoq >= 0 ? "+" : "")\(String(format: "%.1f", qoq))%")
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(qoq > 0 ? Theme.bearRed : Theme.bullGreen)
                    }
                }

                Spacer()

                if isHighRisk {
                    BanknoteSignalBadge(
                        text: "HIGH RISK",
                        color: Theme.bearRed,
                        rotation: -2
                    )
                } else if isIncreasing {
                    BanknoteSignalBadge(
                        text: "INCREASING",
                        color: Theme.holdAmber,
                        rotation: -1
                    )
                } else {
                    BanknoteSignalBadge(
                        text: "SAFE",
                        color: Theme.bullGreen,
                        rotation: -1
                    )
                }
            }

            PledgeIndicatorBar(pledgePct: pledgePct)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct PledgeIndicatorBar: View {
    let pledgePct: Double

    private var clampedPct: Double {
        min(max(pledgePct, 0), 100)
    }

    private var segmentColor: Color {
        if pledgePct > 50.0 {
            return Theme.bearRed
        } else if pledgePct > 20.0 {
            return Theme.holdAmber
        } else {
            return Theme.bullGreen
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.tight) {
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(Theme.borderFine)
                        .frame(height: 6)

                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(segmentColor)
                        .frame(width: max(geo.size.width * CGFloat(clampedPct / 100.0), 4), height: 6)
                }
            }
            .frame(height: 6)

            HStack {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Circle()
                        .fill(Theme.bullGreen)
                        .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
                    Text("0-20% Safe")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                HStack(spacing: Theme.Spacing.xSmall) {
                    Circle()
                        .fill(Theme.holdAmber)
                        .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
                    Text("20-50% Caution")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                HStack(spacing: Theme.Spacing.xSmall) {
                    Circle()
                        .fill(Theme.bearRed)
                        .frame(width: Theme.Spacing.tight, height: Theme.Spacing.tight)
                    Text(">50% Risk")
                        .font(Theme.officialStampFont(size: 7))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
        }
    }
}
