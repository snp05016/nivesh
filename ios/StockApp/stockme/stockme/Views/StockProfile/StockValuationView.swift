import Combine
import SwiftUI
import Charts

// MARK: - Stock Valuation View

struct StockValuationView: View {
    let ticker: String
    let exchange: String
    @ObservedObject var vm: StockProfileViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                if vm.valuationLoading {
                    SPSkeletonBlock(rows: 8)
                } else if let data = vm.valuationData {
                    ValuationMetricsGridView(snapshot: data.snapshot)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    PEBandVisualizationView(snapshot: data.snapshot)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    ValuationIndicatorsView(snapshot: data.snapshot)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)

                    PeerComparisonTableView(
                        peers: data.peerComparison,
                        currentTicker: ticker
                    )

                    if let peBand = data.peBandData, !peBand.isEmpty {
                        GuillocheDivider()
                            .padding(.horizontal, Theme.screenPadding)

                        HistoricalPEBandView(peBandData: peBand)
                    }
                } else if let error = vm.valuationError {
                    SPEmptyStateView(message: error)
                } else {
                    SPEmptyStateView(message: "Valuation data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchValuation() }
    }
}

// MARK: - Valuation Metrics Grid (3×2)

struct ValuationMetricsGridView: View {
    let snapshot: ValuationSnapshot

    private var metrics: [(String, String, String, Color)] {
        var items: [(String, String, String, Color)] = []

        // PE Ratio
        if let peCurrent = snapshot.peCurrent {
            let currentPE = String(format: "%.1f", peCurrent)
            var sub = ""
            var subColor = Theme.inkSecondary
            if let pe5yrAvg = snapshot.pe5yrAvg, pe5yrAvg > 0 {
                let diff = ((peCurrent - pe5yrAvg) / pe5yrAvg) * 100
                let label = diff >= 0 ? "premium" : "discount"
                sub = "vs 5yr avg \(String(format: "%+.0f", diff))% \(label)"
                subColor = diff > 10 ? Theme.bearRed : diff < -10 ? Theme.bullGreen : Theme.holdAmber
            }
            items.append(("P/E RATIO", currentPE, sub, subColor))
        }

        // PB Ratio
        if let pbCurrent = snapshot.pbCurrent {
            let currentPB = String(format: "%.1f", pbCurrent)
            var sub = ""
            var subColor = Theme.inkSecondary
            if let pb5yrAvg = snapshot.pb5yrAvg, pb5yrAvg > 0 {
                let diff = ((pbCurrent - pb5yrAvg) / pb5yrAvg) * 100
                sub = "5yr avg \(String(format: "%.1f", pb5yrAvg))"
                subColor = diff > 10 ? Theme.bearRed : diff < -10 ? Theme.bullGreen : Theme.holdAmber
            }
            items.append(("P/B RATIO", currentPB, sub, subColor))
        }

        // EV/EBITDA
        if let evEbitda = snapshot.evEbitda {
            items.append(("EV/EBITDA", String(format: "%.1f", evEbitda), "Enterprise Value to EBITDA", Theme.inkSecondary))
        }

        // Market Cap
        let mcap = snapshot.marketCapCrores
        items.append(("MARKET CAP", IndianFormatter.formatLakhsCrores(mcap), "Crores", Theme.inkSecondary))

        // Dividend Yield
        if let divYield = snapshot.dividendYield {
            items.append(("DIV YIELD", String(format: "%.2f%%", divYield), "Trailing twelve months", Theme.inkSecondary))
        }

        // PEG Ratio
        if let peg = snapshot.pegRatio {
            let pegStr = String(format: "%.2f", peg)
            let pegColor: Color = peg < 1 ? Theme.bullGreen : peg > 2 ? Theme.bearRed : Theme.holdAmber
            items.append(("PEG RATIO", pegStr, peg < 1 ? "Undervalued" : peg > 2 ? "Overvalued" : "Fair", pegColor))
        }

        return items
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("KEY VALUATION METRICS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            LazyVGrid(
                columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())],
                spacing: Theme.Spacing.medium
            ) {
                ForEach(metrics, id: \.0) { label, value, sub, subColor in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(label.uppercased())
                            .font(Theme.officialStampFont(size: 7))
                            .tracking(0.8)
                            .foregroundStyle(Theme.inkTertiary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                        Text(value)
                            .font(Theme.serialNumberFont(size: 13, relativeTo: .caption))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                        Text(sub.uppercased())
                            .font(Theme.microLabel(size: 8))
                            .foregroundStyle(subColor)
                            .lineLimit(2)
                            .minimumScaleFactor(0.6)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Spacing.medium)
                    .banknoteCard()
                }
            }
        }
    }
}

// MARK: - PE Band Visualization

struct PEBandVisualizationView: View {
    let snapshot: ValuationSnapshot

    private var hasPEBandData: Bool {
        snapshot.pe5yrLow != nil && snapshot.pe5yrHigh != nil
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("P/E BAND (5-YEAR RANGE)")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if hasPEBandData {
                peBandContent
            } else {
                Text("5-year P/E range unavailable")
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, Theme.Spacing.xLarge)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    /// Computed bar width uses proportional screen sizing — no GeometryReader in scrollable context (§2.2).
    private var barWidth: CGFloat {
        UIScreen.main.bounds.width - 2 * Theme.screenPadding - 2 * Theme.Spacing.card
    }

    private var peBandContent: some View {
        let low = snapshot.pe5yrLow ?? 0
        let high = snapshot.pe5yrHigh ?? 1
        let current = snapshot.peCurrent ?? 0
        let avg = snapshot.pe5yrAvg ?? current
        let sector = snapshot.peSectorAvg
        let span = max(high - low, 0.01)
        let currentFraction = CGFloat((current - low) / span)
        let avgFraction = CGFloat((avg - low) / span)

        return VStack(spacing: Theme.Spacing.standard) {
            // PE band bar
            let clampedCurrent = max(0, min(1, currentFraction))

            ZStack(alignment: .leading) {
                // Background track
                Rectangle()
                    .fill(Theme.inkTertiary.opacity(0.1))
                    .frame(width: barWidth, height: Theme.Spacing.medium)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))

                // Gradient bar: green → amber → red
                LinearGradient(
                    colors: [Theme.bullGreen, Theme.holdAmber, Theme.bearRed],
                    startPoint: .leading,
                    endPoint: .trailing
                )
                .frame(width: barWidth * clampedCurrent, height: Theme.Spacing.medium)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))

                // Current PE marker (diamond)
                ZStack {
                    DiamondShape()
                        .fill(Theme.securityGold)
                        .frame(width: Theme.Spacing.standard, height: Theme.Spacing.standard)
                }
                .offset(x: barWidth * clampedCurrent - Theme.Spacing.tight)

                // Average marker (thin line)
                Rectangle()
                    .fill(Theme.inkPrimary.opacity(0.6))
                    .frame(width: 1.5, height: Theme.Spacing.large)
                    .offset(x: barWidth * CGFloat(max(0, min(1, avgFraction))) - 0.75)
            }
            .frame(width: barWidth, height: Theme.Spacing.large)

            // Legend markers
            HStack(spacing: Theme.Spacing.medium) {
                LegendItem(color: Theme.securityGold, shape: "◆", label: "Current", value: String(format: "%.1f", current))
                LegendItem(color: Theme.inkPrimary, shape: "|", label: "5yr Avg", value: String(format: "%.1f", avg))
                if let sectorPE = sector {
                    LegendItem(color: Theme.avatarBlue, shape: "△", label: "Sector", value: String(format: "%.1f", sectorPE))
                }
            }
            .font(Theme.microLabel(size: 9))

            // Range labels
            HStack {
                Text(String(format: "%.1f", low))
                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                    .foregroundStyle(Theme.bullGreen)
                Spacer()
                Text(String(format: "%.1f", high))
                    .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                    .foregroundStyle(Theme.bearRed)
            }

            // Position interpretation
            let pctFromLow = ((current - low) / span) * 100
            HStack(spacing: Theme.Spacing.small) {
                Circle()
                    .fill(currentFraction < 0.35 ? Theme.bullGreen : currentFraction > 0.65 ? Theme.bearRed : Theme.holdAmber)
                    .frame(width: Theme.Spacing.small, height: Theme.Spacing.small)
                Text(positionLabel(fraction: currentFraction, pctFromLow: pctFromLow))
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.top, Theme.Spacing.xSmall)
        }
    }

    private func positionLabel(fraction: CGFloat, pctFromLow: Double) -> String {
        if fraction < 0.2 {
            return "Near 5-year low — potentially undervalued"
        } else if fraction < 0.4 {
            return "Below historical average"
        } else if fraction < 0.6 {
            return "Near 5-year average — fairly valued"
        } else if fraction < 0.8 {
            return "Above historical average"
        } else {
            return "Near 5-year high — potentially overvalued"
        }
    }
}

private struct DiamondShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.midX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.midY))
        p.addLine(to: CGPoint(x: rect.midX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.midY))
        p.closeSubpath()
        return p
    }
}

private struct LegendItem: View {
    let color: Color
    let shape: String
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Text(shape)
                .foregroundStyle(color)
                .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
            Text("\(label) \(value)")
                .foregroundStyle(Theme.inkSecondary)
                .font(Theme.microLabel(size: 9))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
    }
}

// MARK: - Valuation Indicators

struct ValuationIndicatorsView: View {
    let snapshot: ValuationSnapshot

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("VALUATION INDICATORS")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            VStack(spacing: Theme.Spacing.medium) {
                // PE vs 5yr Avg
                if let current = snapshot.peCurrent, let avg = snapshot.pe5yrAvg, avg > 0 {
                    let pctVsAvg = ((current - avg) / avg) * 100
                    let isPremium = pctVsAvg > 0
                    let severity = valuationSeverity(pctDiff: pctVsAvg)
                    ValuationIndicatorRow(
                        label: "P/E vs 5-Year Average",
                        detail: "Trading at \(String(format: "%.1f", abs(pctVsAvg)))% \(isPremium ? "premium" : "discount") to 5-year average of \(String(format: "%.1f", avg))",
                        severity: severity
                    )
                }

                // PE vs Sector
                if let current = snapshot.peCurrent, let sector = snapshot.peSectorAvg, sector > 0 {
                    let pctVsSector = ((current - sector) / sector) * 100
                    let isHigher = pctVsSector > 0
                    let severity = valuationSeverity(pctDiff: pctVsSector)
                    ValuationIndicatorRow(
                        label: "P/E vs Sector Average",
                        detail: "\(String(format: "%.1f", abs(pctVsSector)))% \(isHigher ? "higher" : "lower") than sector average of \(String(format: "%.1f", sector))",
                        severity: severity
                    )
                }

                // Earnings Yield
                if let earningsYield = snapshot.earningsYield {
                    ValuationIndicatorRow(
                        label: "Earnings Yield",
                        detail: "\(String(format: "%.1f", earningsYield))% — \(earningsYield >= 8 ? "Attractive vs bond yields" : earningsYield >= 5 ? "Moderate" : "Below risk-free rate")",
                        severity: earningsYield > 8 ? .low : earningsYield > 5 ? .medium : .high
                    )
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func valuationSeverity(pctDiff: Double) -> SeverityDot.Severity {
        let absPct = abs(pctDiff)
        if absPct < 10 { return .low }
        if absPct < 30 { return .medium }
        return .high
    }
}

struct ValuationIndicatorRow: View {
    let label: String
    let detail: String
    let severity: SeverityDot.Severity

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            SeverityDot(severity: severity)
                .padding(.top, Theme.Spacing.xSmall)

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(label.uppercased())
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(0.8)
                    .foregroundStyle(Theme.inkSecondary)
                Text(detail)
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
        .padding(Theme.Spacing.medium)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Peer Comparison Table

struct PeerComparisonTableView: View {
    let peers: [PeerValuation]
    let currentTicker: String

    private let columns: [(String, KeyPath<PeerValuation, Double?>)] = [
        ("P/E", \.pe),
        ("P/B", \.pb),
        ("EV/EBITDA", \.evEbitda),
        ("ROCE", \.roce),
        ("ROE", \.roe),
    ]

    @State private var sortColumn: Int = 0
    @State private var sortAscending: Bool = false

    private var sortedPeers: [PeerValuation] {
        guard sortColumn < columns.count else { return peers }
        let keyPath = columns[sortColumn].1
        return peers.sorted { a, b in
            let valA = a[keyPath: keyPath] ?? Double.infinity
            let valB = b[keyPath: keyPath] ?? Double.infinity
            return sortAscending ? valA < valB : valA > valB
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PEER COMPARISON")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            let nameColW: CGFloat = 80
            let dataColW: CGFloat = 56
            let totalW = nameColW + dataColW * CGFloat(columns.count)

            ScrollView(.horizontal, showsIndicators: false) {
                VStack(spacing: Theme.Spacing.none) {
                    // Header row
                    HStack(spacing: Theme.Spacing.none) {
                        Text("COMPANY")
                            .font(Theme.officialStampFont(size: 7))
                            .tracking(0.5)
                            .foregroundStyle(Theme.inkTertiary)
                            .frame(width: nameColW, alignment: .leading)

                        ForEach(Array(columns.enumerated()), id: \.offset) { idx, col in
                            Button {
                                HapticManager.selection()
                                if sortColumn == idx {
                                    sortAscending.toggle()
                                } else {
                                    sortColumn = idx
                                    sortAscending = false
                                }
                            } label: {
                                HStack(spacing: Theme.Spacing.xSmall) {
                                    Text(col.0)
                                        .font(Theme.officialStampFont(size: 7))
                                        .tracking(0.5)
                                        .foregroundStyle(sortColumn == idx ? Theme.securityGold : Theme.inkTertiary)
                                    if sortColumn == idx {
                                        Image(systemName: sortAscending ? "chevron.up" : "chevron.down")
                                            .font(Theme.officialStampFont(size: 6))
                                            .foregroundStyle(Theme.securityGold)
                                    }
                                }
                                .frame(width: dataColW, alignment: .trailing)
                            }
                            .buttonStyle(EKPressStyle())
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.small)

                    // Separator
                    Rectangle()
                        .fill(Theme.borderFine)
                        .frame(height: 0.5)
                        .padding(.horizontal, Theme.Spacing.medium)

                    // Data rows
                    ForEach(sortedPeers) { peer in
                        let isCurrent = peer.ticker.uppercased() == currentTicker.uppercased()
                        PeerValuationRow(
                            peer: peer,
                            nameColW: nameColW,
                            dataColW: dataColW,
                            columns: columns,
                            isCurrent: isCurrent
                        )
                    }
                }
                .frame(minWidth: totalW)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

struct PeerValuationRow: View {
    let peer: PeerValuation
    let nameColW: CGFloat
    let dataColW: CGFloat
    let columns: [(String, KeyPath<PeerValuation, Double?>)]
    let isCurrent: Bool

    var body: some View {
        HStack(spacing: Theme.Spacing.none) {
            Text(peer.ticker.uppercased())
                .font(Theme.officialStampFont(size: 8))
                .foregroundStyle(isCurrent ? Theme.securityGold : Theme.inkPrimary)
                .frame(width: nameColW, alignment: .leading)

            ForEach(columns, id: \.0) { _, keyPath in
                let value = peer[keyPath: keyPath]
                Text(value.map { String(format: "%.1f", $0) } ?? "—")
                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                    .foregroundStyle(
                        isCurrent ? Theme.securityGold : (value ?? 0) >= 0 ? Theme.inkSecondary : Theme.bearRed
                    )
                    .frame(width: dataColW, alignment: .trailing)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
            }
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.tight)
        .background(isCurrent ? Theme.securityGoldLight : Color.clear)
        .overlay(
            Rectangle().fill(Theme.borderFine).frame(height: 0.5),
            alignment: .bottom
        )
    }
}

// MARK: - Historical PE Band Chart

struct HistoricalPEBandView: View {
    let peBandData: [[String: AnyCodable]]

    private struct PEPoint: Identifiable {
        let id = UUID()
        let date: Date
        let pe: Double
        let peLow: Double?
        let peAvg: Double?
        let peHigh: Double?
    }

    private var parsedPoints: [PEPoint] {
        peBandData.compactMap { dict in
            guard let dateStr = dict["date"]?.value as? String,
                  let pe = dict["pe"]?.value as? Double else { return nil }

            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let date = formatter.date(from: dateStr)
                ?? ISO8601DateFormatter().date(from: dateStr)
                ?? Date()

            return PEPoint(
                date: date,
                pe: pe,
                peLow: dict["pe_low"]?.value as? Double,
                peAvg: dict["pe_avg"]?.value as? Double,
                peHigh: dict["pe_high"]?.value as? Double
            )
        }
        .sorted { $0.date < $1.date }
    }

    private var latestPE: Double? {
        parsedPoints.last?.pe
    }

    private var avgPE: Double {
        let values = parsedPoints.map { $0.pe }
        guard !values.isEmpty else { return 0 }
        return values.reduce(0, +) / Double(values.count)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("HISTORICAL P/E BAND")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if parsedPoints.isEmpty {
                Text("Historical P/E data unavailable")
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, Theme.Spacing.xLarge)
            } else {
                historicalChartContent
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private var historicalChartContent: some View {
        VStack(spacing: Theme.Spacing.standard) {
            // Chart summary stats
            HStack(spacing: Theme.Spacing.standard) {
                if let latest = latestPE {
                    summaryChip(label: "LATEST", value: String(format: "%.1f", latest), color: Theme.securityGold)
                }
                summaryChip(label: "AVG", value: String(format: "%.1f", avgPE), color: Theme.inkSecondary)
                if let low = parsedPoints.map({ $0.pe }).min() {
                    summaryChip(label: "LOW", value: String(format: "%.1f", low), color: Theme.bullGreen)
                }
                if let high = parsedPoints.map({ $0.pe }).max() {
                    summaryChip(label: "HIGH", value: String(format: "%.1f", high), color: Theme.bearRed)
                }
            }

            // Chart
            Chart {
                // PE line
                ForEach(parsedPoints) { pt in
                    LineMark(
                        x: .value("Date", pt.date),
                        y: .value("P/E", pt.pe)
                    )
                    .foregroundStyle(Theme.securityGold)
                    .interpolationMethod(.catmullRom)
                }

                // PE Low band (if available)
                let lowPoints = parsedPoints.filter { $0.peLow != nil }
                if !lowPoints.isEmpty {
                    ForEach(lowPoints) { pt in
                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("P/E Low", pt.peLow!)
                        )
                        .foregroundStyle(Theme.bullGreen.opacity(0.5))
                        .interpolationMethod(.catmullRom)
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                    }
                }

                // PE High band (if available)
                let highPoints = parsedPoints.filter { $0.peHigh != nil }
                if !highPoints.isEmpty {
                    ForEach(highPoints) { pt in
                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("P/E High", pt.peHigh!)
                        )
                        .foregroundStyle(Theme.bearRed.opacity(0.5))
                        .interpolationMethod(.catmullRom)
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [4, 4]))
                    }
                }

                // PE Avg band (if available)
                let avgPoints = parsedPoints.filter { $0.peAvg != nil }
                if !avgPoints.isEmpty {
                    ForEach(avgPoints) { pt in
                        LineMark(
                            x: .value("Date", pt.date),
                            y: .value("P/E Avg", pt.peAvg!)
                        )
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                        .interpolationMethod(.catmullRom)
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [2, 6]))
                    }
                }

                // Area between low and high
                let bandPoints = parsedPoints.filter { $0.peLow != nil && $0.peHigh != nil }
                if !bandPoints.isEmpty {
                    ForEach(bandPoints) { pt in
                        AreaMark(
                            x: .value("Date", pt.date),
                            yStart: .value("P/E Low", pt.peLow!),
                            yEnd: .value("P/E High", pt.peHigh!)
                        )
                        .foregroundStyle(
                            LinearGradient(
                                colors: [Theme.bullGreen.opacity(0.06), Theme.bearRed.opacity(0.06)],
                                startPoint: .bottom,
                                endPoint: .top
                            )
                        )
                    }
                }
            }
            .chartXAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisValueLabel(format: .dateTime.month(.abbreviated).year(.twoDigits))
                        .font(Theme.microLabel(size: 8))
                }
            }
            .chartYAxis {
                AxisMarks(values: .automatic(desiredCount: 4)) { _ in
                    AxisValueLabel()
                        .font(Theme.microLabel(size: 8))
                }
            }
            .frame(height: UIScreen.main.bounds.height * 0.25)

            // Legend
            HStack(spacing: Theme.Spacing.standard) {
                chartLegend(color: Theme.securityGold, label: "P/E")
                chartLegend(color: Theme.bullGreen.opacity(0.5), label: "Low Band")
                chartLegend(color: Theme.inkTertiary.opacity(0.5), label: "Avg Band")
                chartLegend(color: Theme.bearRed.opacity(0.5), label: "High Band")
            }
            .font(Theme.microLabel(size: 9))
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private func summaryChip(label: String, value: String, color: Color) -> some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 7))
                .tracking(0.5)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                .foregroundStyle(color)
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.small)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }

    private func chartLegend(color: Color, label: String) -> some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Rectangle()
                .fill(color)
                .frame(width: Theme.Spacing.standard, height: 2)
            Text(label)
                .foregroundStyle(Theme.inkSecondary)
        }
    }
}
