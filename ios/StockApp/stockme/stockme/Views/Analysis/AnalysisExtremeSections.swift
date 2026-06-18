import SwiftUI

struct AnalysisExtremeSections: View {
    let analysis: StockAnalysis
    let previousAnalysis: StockAnalysis?
    @ObservedObject var viewModel: AnalysisViewModel

    var body: some View {
        Group {
            if let fs = analysis.factorScores {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "FACTOR RADAR")
                    factorScoreGrid(fs)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let sc = analysis.scenarios, sc.bull != nil || sc.base != nil || sc.bear != nil {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "SCENARIO ANALYSIS")
                    scenarioTable(sc)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let ft = analysis.financialTrends, let years = ft.years, !years.isEmpty {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "FINANCIAL TRENDS")
                    financialTrendsView(ft)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let ot = analysis.ownershipTrends, let dates = ot.dates, !dates.isEmpty {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "PROMOTER PLEDGING TREND")
                    ownershipTrendView(ot)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let vb = analysis.valuationBands {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "VALUATION")
                    valuationBandView(vb)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let peers = analysis.peerComparison, !peers.isEmpty {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "PEER COMPARISON")
                    peerTable(peers)
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let ni = analysis.nicheInsights, !ni.isEmpty {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    SectionHeaderView(title: "NICHE INSIGHTS")
                    ForEach(Array(ni.enumerated()), id: \.offset) { _, insight in
                        NiveshBulletRow(text: stripEmoji(insight))
                    }
                }
                .padding(.vertical, Theme.Spacing.tight)
            }

            if let et = analysis.extendedThesis {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    SectionHeaderView(title: "EXTENDED THESIS")
                    if let bd = et.bullDeepDive, !bd.isEmpty {
                        thesisBlock(title: "BULL CASE", text: stripEmoji(bd), color: Theme.bullGreen)
                    }
                    if let bd = et.bearDeepDive, !bd.isEmpty {
                        thesisBlock(title: "BEAR CASE (1.5\u{00D7} DIALECTICAL)", text: stripEmoji(bd), color: Theme.bearRed)
                    }
                    if let mq = et.managementQuality, !mq.isEmpty {
                        thesisBlock(title: "MANAGEMENT QUALITY", text: stripEmoji(mq), color: Theme.securityGold)
                    }
                    if let cm = et.competitiveMoat, !cm.isEmpty {
                        thesisBlock(title: "COMPETITIVE MOAT", text: stripEmoji(cm), color: Theme.inkPrimary)
                    }
                    if let sp = et.sectorPositioning, !sp.isEmpty {
                        thesisBlock(title: "SECTOR POSITIONING", text: stripEmoji(sp), color: Theme.holdAmber)
                    }
                }
                .padding(Theme.Spacing.card)
                .frame(maxWidth: .infinity, alignment: .leading)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
            }

            if let gf = analysis.governanceFlags, !gf.isEmpty {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                    SectionHeaderView(title: "GOVERNANCE FLAGS")
                    ForEach(Array(gf.enumerated()), id: \.offset) { _, f in
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

            if let cc = analysis.confidenceCalibration,
               let note = cc.calibrationNote, !note.isEmpty,
               note != "Calibration engine did not run." {
                GuillocheDivider().padding(.horizontal, Theme.screenPadding)
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

            if let tb = analysis.targetPriceBounds {
                let st = tb.shortTerm3m
                let mt = tb.mediumTerm12m
                let lt = tb.longTerm36m
                let stMid = st?.mid ?? 0
                let mtMid = mt?.mid ?? 0
                let ltMid = lt?.mid ?? 0
                if stMid > 0 || mtMid > 0 || ltMid > 0 {
                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        SectionHeaderView(title: "TARGET PRICE BOUNDS (90%)")
                        HStack(spacing: Theme.Spacing.standard) {
                            if stMid > 0 {
                                VStack(spacing: Theme.Spacing.xSmall) {
                                    Text("3M").font(Theme.officialStampFont(size: 9, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                    Text(IndianFormatter.priceCompact(stMid)).font(Theme.serialNumberFont(size: 16, relativeTo: .callout)).foregroundStyle(Theme.inkPrimary)
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.6)
                                    Text("\(IndianFormatter.priceCompact(st?.lower ?? 0)) \u{2013} \(IndianFormatter.priceCompact(st?.upper ?? 0))").font(Theme.serialNumberFont(size: 10, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                }.frame(maxWidth: .infinity)
                            }
                            if mtMid > 0 {
                                VStack(spacing: Theme.Spacing.xSmall) {
                                    Text("12M").font(Theme.officialStampFont(size: 9, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                    Text(IndianFormatter.priceCompact(mtMid)).font(Theme.serialNumberFont(size: 16, relativeTo: .callout)).foregroundStyle(Theme.inkPrimary)
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.6)
                                    Text("\(IndianFormatter.priceCompact(mt?.lower ?? 0)) \u{2013} \(IndianFormatter.priceCompact(mt?.upper ?? 0))").font(Theme.serialNumberFont(size: 10, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                }.frame(maxWidth: .infinity)
                            }
                            if ltMid > 0 {
                                VStack(spacing: Theme.Spacing.xSmall) {
                                    Text("36M").font(Theme.officialStampFont(size: 9, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                    Text(IndianFormatter.priceCompact(ltMid)).font(Theme.serialNumberFont(size: 16, relativeTo: .callout)).foregroundStyle(Theme.inkPrimary)
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.6)
                                    Text("\(IndianFormatter.priceCompact(lt?.lower ?? 0)) \u{2013} \(IndianFormatter.priceCompact(lt?.upper ?? 0))").font(Theme.serialNumberFont(size: 10, relativeTo: .caption2)).foregroundStyle(Theme.inkTertiary)
                                }.frame(maxWidth: .infinity)
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
    }

    private func factorScoreGrid(_ fs: FactorScores) -> some View {
        let items: [(String, Int?)] = [
            ("Value", fs.value), ("Quality", fs.quality),
            ("Momentum", fs.momentum), ("Growth", fs.growth),
            ("Low Vol", fs.lowVolatility)
        ]
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        let barWidth = colW - colW * 0.23 - colW * 0.09 - Theme.Spacing.medium * 2
        return VStack(spacing: Theme.Spacing.standard) {
            ForEach(items, id: \.0) { label, score in
                HStack {
                    Text(label)
                        .font(.caption).foregroundStyle(Theme.inkSecondary)
                        .frame(width: colW * 0.23, alignment: .leading)
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Theme.inkTertiary.opacity(0.12))
                            .frame(width: barWidth, height: 8)
                        if let s = score {
                            RoundedRectangle(cornerRadius: 2)
                                .fill(Theme.securityGold)
                                .frame(width: barWidth * CGFloat(s) / 100.0, height: 8)
                                .animation(.easeOut(duration: 0.5), value: s)
                        }
                    }
                    .frame(width: barWidth, height: 8)
                    Text(score.map { "\($0)" } ?? "-")
                        .font(Theme.serialNumberFont(size: 12))
                        .foregroundStyle(Theme.inkPrimary)
                        .frame(width: colW * 0.09, alignment: .trailing)
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }

    private func scenarioTable(_ sc: ScenarioBundle) -> some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(spacing: 0) {
            ForEach(["bull", "base", "bear"], id: \.self) { flavor in
                let pt = flavor == "bull" ? sc.bull : flavor == "base" ? sc.base : sc.bear
                if let p = pt {
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(flavor.uppercased())
                            .font(Theme.officialStampFont(size: 9))
                            .foregroundStyle(flavor == "bull" ? Theme.bullGreen :
                                             flavor == "bear" ? Theme.bearRed : Theme.securityGold)
                            .frame(width: colW * 0.12, alignment: .leading)
                        Text(IndianFormatter.priceCompact(p.price3m ?? 0))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 11)).frame(width: colW * 0.20, alignment: .trailing)
                        Text("3m")
                            .font(.caption2).foregroundStyle(Theme.inkTertiary)
                        Spacer()
                        Text(IndianFormatter.priceCompact(p.price12m ?? 0))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 11)).frame(width: colW * 0.20, alignment: .trailing)
                        Text("12m")
                            .font(.caption2).foregroundStyle(Theme.inkTertiary)
                        Spacer()
                        if let prob = p.probabilityPct {
                            Text("\(prob)%")
                                .font(Theme.serialNumberFont(size: 12))
                                .foregroundStyle(Theme.securityGold)
                                .frame(width: colW * 0.11, alignment: .trailing)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .padding(.horizontal, Theme.screenPadding)
                    if let narrative = p.narrative, !narrative.isEmpty {
                        Text(stripEmoji(narrative))
                            .font(.caption)
                            .foregroundStyle(Theme.inkSecondary)
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.bottom, Theme.Spacing.tight)
                    }
                }
            }
        }
    }

    private func financialTrendsView(_ ft: FinancialTrends) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let rev = ft.revenueCr, let years = ft.years, !rev.isEmpty {
                financialTrendRow(title: "Revenue (Cr)", values: rev, years: years, color: Theme.bullGreen)
            }
            if let np = ft.netProfitCr, let years = ft.years, !np.isEmpty {
                financialTrendRow(title: "Net Profit (Cr)", values: np, years: years, color: Theme.bearRed)
            }
            if let m = ft.netMarginPct, let years = ft.years, !m.isEmpty {
                financialTrendRow(title: "Net Margin %", values: m, years: years, color: Theme.securityGold)
            }
        }
    }

    private func financialTrendRow(title: String, values: [Double?], years: [String], color: Color) -> some View {
        let maxVal = values.compactMap { $0 }.max() ?? 1
        return VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(title)
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkTertiary)
                .padding(.horizontal, Theme.screenPadding)
            HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                ForEach(Array(zip(values.indices, zip(values, years))), id: \.0) { i, pair in
                    let (val, yr) = pair
                    VStack(spacing: 2) {
                        if let v = val {
                            Rectangle()
                                .fill(color)
                                .frame(width: 20, height: CGFloat(v / maxVal) * 60)
                                .cornerRadius(2)
                            Text(yr.suffix(2))
                                .font(Theme.microLabel(size: 8))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
    }

    private func ownershipTrendView(_ ot: OwnershipTrends) -> some View {
        VStack(spacing: Theme.Spacing.tight) {
            if let dates = ot.dates, let vals = ot.promoterPledgedPct {
                HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
                    ForEach(Array(zip(dates.indices, zip(dates, vals))), id: \.0) { i, pair in
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

    private func valuationBandView(_ vb: ValuationBands) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            if let curr = vb.currentPrice, let fair = vb.fairValue {
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
                if let method = vb.method {
                    Text("Method: \(method)")
                        .font(.caption2).foregroundStyle(Theme.inkTertiary)
                }
            }
            if let pe = vb.peBand {
                HStack(spacing: Theme.Spacing.standard) {
                    labelValueStack("P/E Low", pe.low)
                    labelValueStack("P/E Mid", pe.mid)
                    labelValueStack("P/E High", pe.high)
                }
                .padding(.top, Theme.Spacing.tight)
            }
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity)
    }

    private func labelValueStack(_ label: String, _ val: Double?) -> some View {
        VStack(spacing: 2) {
            Text(val.map { String(format: "%.1f", $0) } ?? "-")
                .font(Theme.serialNumberFont(size: 14))
                .foregroundStyle(Theme.inkPrimary)
            Text(label)
                .font(Theme.microLabel(size: 8))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }

    private func peerTable(_ peers: [PeerRow]) -> some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(spacing: 0) {
            HStack {
                Text("Ticker").font(.caption2.weight(.bold)).frame(width: colW * 0.17, alignment: .leading)
                Text("P/E").font(.caption2.weight(.bold)).frame(width: colW * 0.11, alignment: .trailing)
                Text("ROE%").font(.caption2.weight(.bold)).frame(width: colW * 0.12, alignment: .trailing)
                Text("D/E").font(.caption2.weight(.bold)).frame(width: colW * 0.11, alignment: .trailing)
                Text("MCap").font(.caption2.weight(.bold)).frame(maxWidth: .infinity, alignment: .trailing)
            }
            .foregroundStyle(Theme.inkTertiary)
            .padding(.vertical, Theme.Spacing.xSmall)
            .padding(.horizontal, Theme.screenPadding)

            ForEach(peers.prefix(8)) { p in
                HStack {
                    Text(p.ticker ?? p.name ?? "-")
                        .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.securityGold)
                        .frame(width: colW * 0.17, alignment: .leading)
                    Text(p.pe.map { String(format: "%.1f", $0) } ?? "-")
                        .font(.caption).frame(width: colW * 0.11, alignment: .trailing)
                    Text(p.roePct.map { String(format: "%.1f", $0) } ?? "-")
                        .font(.caption).frame(width: colW * 0.12, alignment: .trailing)
                    Text(p.debtToEquity.map { String(format: "%.1f", $0) } ?? "-")
                        .font(.caption).frame(width: colW * 0.11, alignment: .trailing)
                    Text(p.marketcapCr.map { "\u{20B9}\(Int($0))Cr" } ?? "-")
                        .font(.caption).frame(maxWidth: .infinity, alignment: .trailing)
                }
                .foregroundStyle(Theme.inkPrimary)
                .padding(.vertical, Theme.Spacing.xSmall)
                .padding(.horizontal, Theme.screenPadding)
            }
        }
    }

    private func thesisBlock(title: String, text: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(spacing: Theme.Spacing.small) {
                RoundedRectangle(cornerRadius: 1)
                    .fill(color)
                    .frame(width: 3, height: 16)
                Text(title)
                    .font(Theme.officialStampFont(size: 10))
                    .tracking(1.2)
                    .foregroundStyle(color)
            }
            Text(text)
                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(7)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .stroke(color.opacity(0.15), lineWidth: 0.5)
        )
    }
}
