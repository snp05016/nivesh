import SwiftUI
import Charts

/// Risk (spec 10.1 item 4): volatility tiles, beta with its standard error, one-day
/// loss rows (only methods that passed their backtest) or the backtest-failed text,
/// the weekly drawdown chart and the descriptive historical return ranges.
struct ResearchRiskCard: View {
    let risk: ResearchRisk?
    let narrative: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            ResearchSectionTitle(title: "Risk")
            if let risk {
                ResearchNarrativeText(text: narrative)
                ResearchVolatilityTiles(risk: risk)
                if let beta = risk.beta {
                    ResearchBetaRows(beta: beta)
                }
                ResearchLossRows(status: risk.varStatus, rows: risk.var1d ?? [])
                ResearchDrawdownBlock(drawdown: risk.drawdown, series: risk.drawdownSeries?.points ?? [])
                ResearchReturnRanges(ranges: risk.returnRanges ?? [])
            } else {
                ResearchUnavailableText(reason: nil)
            }
        }
        .researchCardStyle()
    }
}

// MARK: - Volatility and beta

private struct ResearchVolatilityTiles: View {
    let risk: ResearchRisk

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Annualised volatility")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            HStack(spacing: Theme.Spacing.medium) {
                ResearchTile(caption: "Recent-weighted", fact: risk.volEwmaAnnPct)
                ResearchTile(caption: "Last 3 months", fact: risk.vol63dAnnPct)
                ResearchTile(caption: "Last 12 months", fact: risk.vol252dAnnPct)
            }
            if let pctl = risk.volPctl {
                ResearchFactRow(fact: pctl)
            }
        }
    }
}

private struct ResearchTile: View {
    let caption: String
    let fact: ResearchFact?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(caption)
                .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                .foregroundStyle(Theme.inkTertiary)
                .lineLimit(2)
            if let fact {
                ResearchFactValue(fact: fact, size: 16)
            } else {
                Text("Not available")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSage, lineWidth: 1))
        .accessibilityElement(children: .combine)
    }
}

private struct ResearchBetaRows: View {
    let beta: ResearchBeta

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            if let raw = beta.raw?.display, let se = beta.se?.display {
                ResearchKeyValueRow(key: "Beta to the Nifty 50", value: "\(raw) ± \(se)")
                    .researchFactDetail(beta.raw)
                Text("± is one standard error, from 252 trading days of daily returns.")
                    .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
            } else if let raw = beta.raw {
                ResearchFactRow(fact: raw)
            }
            if let blume = beta.blumeAdjusted {
                ResearchFactRow(fact: blume)
            }
        }
    }
}

// MARK: - One-day loss (VaR / CVaR)

private struct ResearchLossRows: View {
    let status: ResearchVaRStatus?
    let rows: [ResearchVaRRow]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("One-day losses")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            switch status {
            case .ok where !rows.isEmpty:
                ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                    ResearchLossRow(row: row)
                }
            case .backtestFailed:
                Text("The loss model failed its backtest for this stock")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundStyle(Theme.inkPrimary)
            default:
                ResearchUnavailableText(reason: nil)
            }
        }
    }
}

private struct ResearchLossRow: View {
    let row: ResearchVaRRow

    private var frequency: String {
        (row.level ?? 0) >= 0.985 ? "1 in 100" : "1 in 20"
    }

    private var sentence: String {
        let display = row.varPct?.display ?? "the reported figure"
        switch row.method {
        case .fhsEwma:
            return "Recent-weighted model: on about \(frequency) trading days, the one-day loss is estimated to be worse than \(display)."
        default:
            return "On about \(frequency) trading days over the last 500, the one-day loss was worse than \(display)."
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.small) {
            Text(sentence)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
                .researchFactDetail(row.varPct)
            if let cvar = row.cvarPct {
                ResearchFactRow(fact: cvar)
            }
            if let backtest = row.backtest {
                ResearchBacktestChip(backtest: backtest)
            }
        }
        .padding(.vertical, Theme.Spacing.small)
    }
}

/// Only methods whose backtest passed are ever sent, so this chip always reads as passed.
private struct ResearchBacktestChip: View {
    let backtest: ResearchVaRBacktest

    private var text: String {
        "Passed its \(backtest.windowDays ?? 250)-day backtest"
    }

    var body: some View {
        Label(text, systemImage: "checkmark.seal")
            .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
            .foregroundStyle(Theme.inkSecondary)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .overlay(Capsule().stroke(Theme.securityGold, lineWidth: 1))
    }
}

// MARK: - Drawdown

private struct ResearchDrawdownBlock: View {
    let drawdown: ResearchDrawdown?
    let series: [ResearchDrawdownPoint]

    private var dated: [(date: Date, pct: Double)] {
        series.compactMap { point in WireDate.day(point.date).map { (date: $0, pct: point.pct) } }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Falls from a peak")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            if dated.count > 1 {
                ResearchDrawdownChart(points: dated)
            }
            if let drawdown {
                ForEach(Array([drawdown.max1y, drawdown.max3y, drawdown.max5y, drawdown.current,
                               drawdown.daysSincePeak, drawdown.ulcer1y].compactMap { $0 }.enumerated()),
                        id: \.offset) { _, fact in
                    ResearchFactRow(fact: fact)
                }
            }
        }
    }
}

private struct ResearchDrawdownChart: View {
    let points: [(date: Date, pct: Double)]

    var body: some View {
        Chart {
            ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                AreaMark(x: .value("Week", point.date), y: .value("Below peak", point.pct))
                    .foregroundStyle(Theme.inkSecondary.opacity(0.25))
                LineMark(x: .value("Week", point.date), y: .value("Below peak", point.pct))
                    .foregroundStyle(Theme.securityGold)
            }
        }
        .chartYAxis {
            AxisMarks { value in
                AxisGridLine()
                AxisValueLabel {
                    if let pct = value.as(Double.self) {
                        Text("\(Int(pct.rounded()))%")
                    }
                }
            }
        }
        .frame(height: 140)
        .accessibilityLabel("Weekly chart of how far the price was below its running peak, last 3 years")
    }
}

// MARK: - Historical return ranges (descriptive, not a forecast)

private struct ResearchReturnRanges: View {
    let ranges: [ResearchReturnRange]

    private struct Bar: Identifiable {
        let id: Int
        let label: String
        let low: Double
        let high: Double
    }

    private var bars: [Bar] {
        ranges.enumerated().compactMap { index, range in
            guard let low = range.low?.value, let high = range.high?.value else { return nil }
            return Bar(id: index, label: "\(range.horizonDays ?? 0) trading days", low: low, high: high)
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Past returns over 21 and 63 trading days")
                .font(Theme.engravedSerif(size: 13, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            if !bars.isEmpty {
                Chart {
                    ForEach(bars) { bar in
                        BarMark(xStart: .value("Low", bar.low), xEnd: .value("High", bar.high),
                                y: .value("Period", bar.label), height: .fixed(14))
                            .foregroundStyle(Theme.inkSecondary.opacity(0.45))
                    }
                    RuleMark(x: .value("Zero", 0))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineStyle(StrokeStyle(lineWidth: 1))
                }
                .chartXAxis {
                    AxisMarks { value in
                        AxisGridLine()
                        AxisValueLabel {
                            if let pct = value.as(Double.self) {
                                Text("\(Int(pct.rounded()))%")
                            }
                        }
                    }
                }
                .frame(height: CGFloat(44 * bars.count + 24))
                .accessibilityHidden(true)
            }
            ForEach(Array(ranges.enumerated()), id: \.offset) { _, range in
                ResearchRangeSentence(range: range)
            }
        }
    }
}

private struct ResearchRangeSentence: View {
    let range: ResearchReturnRange

    var body: some View {
        if let text = range.text {
            Text(text)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
                .researchFactDetail(range.low)
        } else {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("\(range.horizonDays ?? 0) trading days")
                    .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
                ResearchUnavailableText(reason: range.low?.reason)
            }
        }
    }
}
