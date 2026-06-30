import SwiftUI

struct AnalysisExtremeSections: View {
    let analysis: StockAnalysis
    let previousAnalysis: StockAnalysis?
    @ObservedObject var viewModel: AnalysisViewModel
    @State private var selectedTab = 0

    private let tabs = ["OVERVIEW", "QUANT MODELS", "DEEP THESIS"]

    var body: some View {
        LazyVStack(spacing: 0) {
            ExtremeTabBar(tabs: tabs, selectedTab: $selectedTab)
                .padding(.bottom, Theme.Spacing.card)

            switch selectedTab {
            case 0:
                ExtremeOverviewSections(analysis: analysis)
            case 1:
                ExtremeQuantSections(analysis: analysis)
            default:
                ExtremeThesisSections(analysis: analysis)
            }
        }
    }
}

// MARK: - Sticky Tab Bar

private struct ExtremeTabBar: View {
    let tabs: [String]
    @Binding var selectedTab: Int

    var body: some View {
        HStack(spacing: Theme.Spacing.small) {
            ForEach(Array(tabs.enumerated()), id: \.offset) { idx, label in
                Button { HapticManager.selection(); 
    HapticManager.selection()
                    HapticManager.selection()
                    withAnimation(.easeInOut(duration: 0.2)) {
                        selectedTab = idx
                    }
                } label: {
                    Text(label)
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.2)
                        .foregroundStyle(selectedTab == idx ? Theme.canvas : Theme.inkSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.medium)
                        .background(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                .fill(selectedTab == idx ? Theme.securityGold : Theme.surfaceElevated)
                        )
                }
                .buttonStyle(EKPressStyle())
            }
        }
    }
}

// MARK: - Overview Tab (Factor Radar, Scenarios, Valuation, Target Bounds)

private struct ExtremeOverviewSections: View {
    let analysis: StockAnalysis

    var body: some View {
        Group {
            if let fs = analysis.factorScores {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "FACTOR RADAR")
                    FactorScoreGridView(scores: fs)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let sc = analysis.scenarios, sc.bull != nil || sc.base != nil || sc.bear != nil {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "SCENARIO ANALYSIS")
                    ScenarioTableView(scenarios: sc)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let vb = analysis.valuationBands {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "VALUATION")
                    ValuationBandBlockView(bands: vb)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let tb = analysis.targetPriceBounds {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                TargetPriceBoundsBlockView(bounds: tb)
            }
        }
    }
}

// MARK: - Quant Models Tab (Financial Trends, Ownership, Peers)

private struct ExtremeQuantSections: View {
    let analysis: StockAnalysis

    var body: some View {
        Group {
            if let ft = analysis.financialTrends, let years = ft.years, !years.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "FINANCIAL TRENDS")
                    FinancialTrendsBlockView(trends: ft)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let ot = analysis.ownershipTrends, let dates = ot.dates, !dates.isEmpty {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "PROMOTER PLEDGING TREND")
                    OwnershipTrendBlockView(trends: ot)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let peers = analysis.peerComparison, !peers.isEmpty {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "PEER COMPARISON")
                    PeerTableView(peers: peers)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }
        }
    }
}

// MARK: - Deep Thesis Tab (Insights, Thesis, Governance, Calibration)

private struct ExtremeThesisSections: View {
    let analysis: StockAnalysis

    var body: some View {
        Group {
            if let ni = analysis.nicheInsights, !ni.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    SectionHeaderView(title: "NICHE INSIGHTS")
                    ForEach(Array(ni.enumerated()), id: \.offset) { _, insight in
                        NiveshBulletRow(text: stripEmoji(insight))
                    }
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let et = analysis.extendedThesis {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                ExtendedThesisBlockView(thesis: et)
            }

            if let gf = analysis.governanceFlags, !gf.isEmpty {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                GovernanceFlagsBlockView(flags: gf)
            }

            if let cc = analysis.confidenceCalibration,
               let note = cc.calibrationNote, !note.isEmpty,
               note != "Calibration engine did not run." {
                Spacer().frame(height: Theme.Spacing.sectionBreath)
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    SectionHeaderView(title: "CONFIDENCE CALIBRATION")
                    Text(stripEmoji(note))
                        .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(3)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(Theme.Spacing.card)
                .frame(maxWidth: .infinity, alignment: .leading)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }
}

// MARK: - Factor Score Grid

private struct FactorScoreGridView: View {
    let scores: FactorScores

    var body: some View {
        let items: [(String, Int?)] = [
            ("Value", scores.value), ("Quality", scores.quality),
            ("Momentum", scores.momentum), ("Growth", scores.growth),
            ("Low Vol", scores.lowVolatility)
        ]
        
        let barWidth = UIScreen.main.bounds.width - (2 * Theme.screenPadding) - 65 - 30 - (2 * Theme.Spacing.standard)
        
        VStack(spacing: Theme.Spacing.standard) {
            ForEach(items, id: \.0) { label, score in
                HStack(spacing: Theme.Spacing.standard) {
                    Text(label)
                        .font(.caption).foregroundStyle(Theme.inkSecondary)
                        .frame(width: 65, alignment: .leading)

                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Theme.inkTertiary.opacity(0.12))
                        if let s = score {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(Theme.securityGold)
                                .frame(width: barWidth * CGFloat(max(0, s)) / 100.0)
                                .animation(.easeOut(duration: 0.5), value: s)
                        }
                    }
                    .frame(width: barWidth, height: 8)

                    Text(score.map { "\($0)" } ?? "-")
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: 30, alignment: .trailing)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Scenario Table

private struct ScenarioTableView: View {
    let scenarios: ScenarioBundle

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            ForEach(["bull", "base", "bear"], id: \.self) { flavor in
                let pt = flavor == "bull" ? scenarios.bull : flavor == "base" ? scenarios.base : scenarios.bear
                if let p = pt {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        HStack {
                            Text(flavor.uppercased())
                                .font(Theme.officialStampFont(size: 11))
                                .foregroundStyle(flavor == "bull" ? Theme.bullGreen :
                                                 flavor == "bear" ? Theme.bearRed : Theme.securityGold)
                            Spacer()
                            if let prob = p.probabilityPct {
                                Text("\(prob)% Probability")
                                    .font(Theme.serialNumberFont(size: 12))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                        }

                        HStack(spacing: Theme.Spacing.large) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("3M TARGET")
                                    .font(.caption2).foregroundStyle(Theme.inkTertiary)
                                Text(IndianFormatter.priceCompact(p.price3m ?? 0))
                                    .font(Theme.serialNumberFont(size: 15))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                            VStack(alignment: .leading, spacing: 2) {
                                Text("12M TARGET")
                                    .font(.caption2).foregroundStyle(Theme.inkTertiary)
                                Text(IndianFormatter.priceCompact(p.price12m ?? 0))
                                    .font(Theme.serialNumberFont(size: 15))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                        }
                        .padding(.vertical, Theme.Spacing.xSmall)

                        if let narrative = p.narrative, !narrative.isEmpty {
                            Text(stripEmoji(narrative))
                                .font(Theme.engravedSerif(size: 13, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineSpacing(3)
                        }
                    }
                    .padding(Theme.Spacing.card)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Theme.surfaceElevated)
                    .cornerRadius(Theme.CornerRadius.medium)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Financial Trends

private struct FinancialTrendsBlockView: View {
    let trends: FinancialTrends

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let rev = trends.revenueCr, let years = trends.years, !rev.isEmpty {
                FinancialTrendRowView(title: "Revenue (Cr)", values: rev, years: years, color: Theme.bullGreen)
            }
            if let np = trends.netProfitCr, let years = trends.years, !np.isEmpty {
                FinancialTrendRowView(title: "Net Profit (Cr)", values: np, years: years, color: Theme.bearRed)
            }
            if let m = trends.netMarginPct, let years = trends.years, !m.isEmpty {
                FinancialTrendRowView(title: "Net Margin %", values: m, years: years, color: Theme.securityGold)
            }
        }
    }
}

private struct FinancialTrendRowView: View {
    let title: String
    let values: [Double?]
    let years: [String]
    let color: Color

    var body: some View {
        let compacted = values.compactMap { $0 }
        let maxAbs = compacted.map { abs($0) }.max() ?? 1
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(title)
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)
            HStack(alignment: .center, spacing: Theme.Spacing.tight) {
                ForEach(Array(zip(values.indices, zip(values, years))), id: \.0) { _, pair in
                    let (val, yr) = pair
                    VStack(spacing: 0) {
                        if let v = val {
                            Rectangle()
                                .fill(color)
                                .frame(width: 20, height: v > 0 ? max(2, CGFloat(v / maxAbs) * 35) : 0)
                                .opacity(v > 0 ? 1 : 0)

                            Rectangle()
                                .fill(Theme.inkTertiary.opacity(0.3))
                                .frame(width: 24, height: 2)

                            Rectangle()
                                .fill(Theme.bearRed.opacity(0.8))
                                .frame(width: 20, height: v < 0 ? max(2, CGFloat(abs(v) / maxAbs) * 35) : 0)
                                .opacity(v < 0 ? 1 : 0)

                            Text(yr.suffix(2))
                                .font(Theme.microLabel(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                                .padding(.top, Theme.Spacing.small)
                        }
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

// MARK: - Ownership Trend

private struct OwnershipTrendBlockView: View {
    let trends: OwnershipTrends

    var body: some View {
        VStack(spacing: Theme.Spacing.tight) {
            if let dates = trends.dates, let vals = trends.promoterPledgedPct {
                HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                    ForEach(Array(zip(dates.indices, zip(dates, vals))), id: \.0) { _, pair in
                        let (date, val) = pair
                        VStack(spacing: 2) {
                            Text("\(Int(val))%")
                                .font(.caption2).foregroundStyle(
                                    val > 30 ? Theme.signalRuby : Theme.inkSecondary)
                            Rectangle()
                                .fill(val > 30 ? Theme.signalRuby : Theme.securityGold)
                                .frame(width: 24, height: max(4, CGFloat(val) * 1.2))
                                .cornerRadius(2)
                            Text(String(date.suffix(5)))
                                .font(Theme.microLabel(size: 7)).foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Valuation Band

private struct ValuationBandBlockView: View {
    let bands: ValuationBands

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let curr = bands.currentPrice, let fair = bands.fairValue {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("CURRENT").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.priceCompact(curr))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 18)).foregroundStyle(Theme.inkPrimary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("FAIR VALUE").font(Theme.officialStampFont(size: 8)).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.priceCompact(fair))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 18))
                            .foregroundStyle(fair > curr ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                if let method = bands.method {
                    Text("Method: \(method)")
                        .font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
            }
            if let pe = bands.peBand {
                HStack(spacing: Theme.Spacing.standard) {
                    ValuationLabelValueView(label: "P/E Low", value: pe.low)
                    ValuationLabelValueView(label: "P/E Mid", value: pe.mid)
                    ValuationLabelValueView(label: "P/E High", value: pe.high)
                }
                .padding(.top, Theme.Spacing.tight)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity)
    }
}

private struct ValuationLabelValueView: View {
    let label: String
    let value: Double?

    var body: some View {
        VStack(spacing: 2) {
            Text(value.map { String(format: "%.1f", $0) } ?? "-")
                .font(Theme.serialNumberFont(size: 14))
                .foregroundStyle(Theme.inkPrimary)
            Text(label)
                .font(Theme.microLabel(size: 8))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Peer Table (horizontally scrollable)

private struct PeerTableView: View {
    let peers: [PeerRow]

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        ScrollView(.horizontal, showsIndicators: false) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: Theme.Spacing.standard) {
                    Text("Ticker").font(.caption2.weight(.bold)).frame(width: colW * 0.34, alignment: .leading)
                    Text("P/E").font(.caption2.weight(.bold)).frame(width: colW * 0.15, alignment: .trailing)
                    Text("ROE%").font(.caption2.weight(.bold)).frame(width: colW * 0.16, alignment: .trailing)
                    Text("D/E").font(.caption2.weight(.bold)).frame(width: colW * 0.15, alignment: .trailing)
                    Text("MCap").font(.caption2.weight(.bold)).frame(width: colW * 0.20, alignment: .trailing)
                }
                .foregroundStyle(Theme.inkTertiary)
                .padding(.vertical, Theme.Spacing.xSmall)

                ForEach(peers.prefix(8)) { p in
                    HStack(spacing: Theme.Spacing.standard) {
                        Text(p.ticker ?? p.name ?? "-")
                            .font(Theme.serialNumberFont(size: 11)).foregroundStyle(Theme.securityGold)
                            .frame(width: colW * 0.34, alignment: .leading)
                            .lineLimit(1)
                            .truncationMode(.tail)
                        Text(p.pe.map { String(format: "%.1f", $0) } ?? "-")
                            .font(.caption).frame(width: colW * 0.15, alignment: .trailing)
                        Text(p.roePct.map { String(format: "%.1f", $0) } ?? "-")
                            .font(.caption).frame(width: colW * 0.16, alignment: .trailing)
                        Text(p.debtToEquity.map { String(format: "%.1f", $0) } ?? "-")
                            .font(.caption).frame(width: colW * 0.15, alignment: .trailing)
                        Text(p.marketcapCr.map { "\u{20B9}\(Int($0))Cr" } ?? "-")
                            .font(.caption).frame(width: colW * 0.20, alignment: .trailing)
                    }
                    .foregroundStyle(Theme.inkPrimary)
                    .padding(.vertical, Theme.Spacing.xSmall)
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

// MARK: - Extended Thesis (desaturated — monochrome titles, accent bars only)

private struct ExtendedThesisBlockView: View {
    let thesis: ExtendedThesis

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            SectionHeaderView(title: "EXTENDED THESIS")
            if let bd = thesis.bullDeepDive, !bd.isEmpty {
                ThesisBlockView(title: "BULL CASE", text: stripEmoji(bd), accentColor: Theme.bullGreen)
            }
            if let bd = thesis.bearDeepDive, !bd.isEmpty {
                ThesisBlockView(title: "BEAR CASE (1.5\u{00D7} DIALECTICAL)", text: stripEmoji(bd), accentColor: Theme.bearRed)
            }
            if let mq = thesis.managementQuality, !mq.isEmpty {
                ThesisBlockView(title: "MANAGEMENT QUALITY", text: stripEmoji(mq), accentColor: Theme.securityGold)
            }
            if let cm = thesis.competitiveMoat, !cm.isEmpty {
                ThesisBlockView(title: "COMPETITIVE MOAT", text: stripEmoji(cm), accentColor: Theme.inkPrimary)
            }
            if let sp = thesis.sectorPositioning, !sp.isEmpty {
                ThesisBlockView(title: "SECTOR POSITIONING", text: stripEmoji(sp), accentColor: Theme.holdAmber)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

private struct ThesisBlockView: View {
    let title: String
    let text: String
    let accentColor: Color

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.small) {
                RoundedRectangle(cornerRadius: 1)
                    .fill(accentColor)
                    .frame(width: 3, height: 16)
                Text(title)
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.2)
                    .foregroundStyle(Theme.inkPrimary)
            }
            Text(text)
                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(7)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.surfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(Theme.borderSubtle, lineWidth: 0.5)
        )
    }
}

// MARK: - Governance Flags

private struct GovernanceFlagsBlockView: View {
    let flags: [GovernanceFlag]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            SectionHeaderView(title: "GOVERNANCE FLAGS")
            ForEach(Array(flags.enumerated()), id: \.offset) { _, f in
                HStack(spacing: Theme.Spacing.tight) {
                    Circle()
                        .fill(f.severity == "high" ? Theme.signalRuby :
                                f.severity == "medium" ? Theme.holdAmber : Theme.inkTertiary)
                        .frame(width: 6, height: 6)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(stripEmoji(f.flag ?? ""))
                            .font(.caption.weight(.medium))
                            .foregroundStyle(Theme.inkPrimary)
                        if let d = f.detail {
                            Text(stripEmoji(d))
                                .font(.caption2)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
        .padding(.vertical, Theme.Spacing.tight)
    }
}

// MARK: - Target Price Bounds

private struct TargetPriceBoundsBlockView: View {
    let bounds: TargetPriceBounds

    var body: some View {
        let st = bounds.shortTerm3m
        let mt = bounds.mediumTerm12m
        let lt = bounds.longTerm36m
        let stMid = st?.mid ?? 0
        let mtMid = mt?.mid ?? 0
        let ltMid = lt?.mid ?? 0

        if stMid > 0 || mtMid > 0 || ltMid > 0 {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                SectionHeaderView(title: "TARGET PRICE BOUNDS (90%)")
                VStack(spacing: Theme.Spacing.standard) {
                    if stMid > 0 {
                        TargetPriceRowView(label: "3M", mid: stMid, lower: st?.lower ?? 0, upper: st?.upper ?? 0)
                    }
                    if mtMid > 0 {
                        TargetPriceRowView(label: "12M", mid: mtMid, lower: mt?.lower ?? 0, upper: mt?.upper ?? 0)
                    }
                    if ltMid > 0 {
                        TargetPriceRowView(label: "36M", mid: ltMid, lower: lt?.lower ?? 0, upper: lt?.upper ?? 0)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
            .padding(.horizontal, Theme.screenPadding)
        }
    }
}

private struct TargetPriceRowView: View {
    let label: String
    let mid: Double
    let lower: Double
    let upper: Double

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(label)
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkTertiary)
                .frame(width: 40, alignment: .leading)

            VStack(alignment: .leading, spacing: 2) {
                Text(IndianFormatter.priceCompact(mid))
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .callout))
                    .foregroundStyle(Theme.inkPrimary)

                Text("\(IndianFormatter.priceCompact(lower)) \u{2013} \(IndianFormatter.priceCompact(upper))")
                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)
            }
            Spacer()
        }
    }
}
