import SwiftUI

struct AnalysisCoreSections: View {
    let analysis: StockAnalysis
    let previousAnalysis: StockAnalysis?
    let ticker: String
    let livePrice: Double?
    @ObservedObject var viewModel: AnalysisViewModel
    @State private var showFullSummary = false

    var body: some View {
        LazyVStack(spacing: Theme.sectionSpacing) {
            stockHeaderSectionView
            aiVerdictCardView
            if let prev = previousAnalysis, prev.analysisDate != analysis.analysisDate {
                whatChangedSectionView(previous: prev)
            }
            signalTimelineSectionView
            dialecticDebateSectionView
            timeHorizonSectionView
            riskFactorsSectionView
            fundamentalsSectionView
            newsSectionView
            whatToWatchSectionView
            disclaimerSectionView
        }
    }

    private var stockHeaderSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(analysis.companyName)
                        .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                        .foregroundStyle(Theme.inkPrimary).lineLimit(2)
                    HStack(spacing: Theme.Spacing.tight) {
                        Text(analysis.exchange ?? "NSE")
                            .font(Theme.monoTabular(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.surfaceElevated).clipShape(Capsule())
                            .overlay(Capsule().stroke(Theme.goldMuted, lineWidth: 0.5))
                        Text(analysis.ticker)
                            .font(Theme.monoTabular(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.goldPrimary)
                            .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                            .background(Theme.goldMuted).clipShape(Capsule())
                    }
                }
                Spacer()
            }
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.medium) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.small) {
                        Text("\u{20B9}")
                            .font(Theme.dataXL(size: 28, relativeTo: .title))
                            .foregroundStyle(Theme.goldPrimary)
                        Text((livePrice ?? analysis.currentPriceInr).inrFormatted.replacingOccurrences(of: "\u{20B9}", with: ""))
                            .font(Theme.dataXL(size: 38, relativeTo: .largeTitle))
                            .foregroundStyle(Theme.inkPrimary)
                            .contentTransition(.numericText())
                    }
                    if let info = viewModel.quickInfo {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: (info.change ?? 0.0) >= 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                                .font(.caption2)
                            Text("\((info.change ?? 0.0) >= 0 ? "+" : "")\((info.change ?? 0.0).inrFormatted)")
                            Text("(\((info.changePercent ?? 0.0).percentFormatted))")
                        }
                        .font(Theme.monoTabular(size: 14, relativeTo: .footnote))
                        .foregroundStyle((info.change ?? 0.0) >= 0 ? Theme.dataPositive : Theme.dataNegative)
                    }
                    if livePrice != nil {
                        HStack(spacing: Theme.Spacing.small) {
                            Circle().fill(Theme.dataPositive).frame(width: 6, height: 6)
                            Text("LIVE").font(Theme.microLabel(size: 9)).foregroundStyle(Theme.dataPositive)
                        }
                    }
                }
                Spacer()
                BanknoteSignalBadge(signal: analysis.signal, rotation: -3).stampAppear()
            }
            if let perf = analysis.pricePerformance {
                HStack(spacing: Theme.Spacing.medium) {
                    pricePerformanceChip(label: "3M", pct: perf.change3mPct)
                    pricePerformanceChip(label: "6M", pct: perf.change6mPct)
                    pricePerformanceChip(label: "1Y", pct: perf.change12mPct)
                    Spacer()
                }
            }
            GuillocheDivider()
            if let prices = viewModel.quickInfo?.priceHistory90d, !prices.isEmpty {
                PriceHistoryChart(
                    prices: prices,
                    ticker: ticker,
                    week52High: viewModel.quickInfo?.week52High,
                    week52Low: viewModel.quickInfo?.week52Low
                )
                .padding(.horizontal, -Theme.screenPadding)
                .immersiveChartTint(isPositive: (viewModel.quickInfo?.changePercent ?? 0) >= 0)
            }
        }
    }

    private var aiVerdictCardView: some View {
        let sig = analysis.signal.rawValue
        // Prefer calibrated confidence from quant engine; fall back to legacy confidencePercent
        let conf = analysis.calibratedConfidence != nil
            ? Int((analysis.calibratedConfidence ?? 0) * 100)
            : analysis.confidencePercent
        let summ = analysis.keyFactors.fundamentalsSummary
        let tier = analysis.analysisTier
        let segs = confidenceSegments(conf)

        return VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            HStack {
                Text("AI VERDICT")
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Text(analysis.analysisDate)
                    .font(Theme.microLabel())
                    .foregroundStyle(Theme.inkTertiary)
            }

            HStack(spacing: Theme.Spacing.standard) {
                Text(sig)
                    .font(Theme.engravedSerif(size: 18, weight: .bold))
                    .foregroundStyle(signalBadgeTextColor(analysis.signal))
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, Theme.Spacing.medium)
                    .background(signalBadgeBgColor(analysis.signal))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
                Spacer()
                ConfidenceArcView(score: conf, size: 64)
            }

            Text("CALIBRATED PROBABILITY")
                .font(Theme.microLabel())
                .foregroundStyle(Theme.inkTertiary)
                .explainableTerm("Mathematically Calibrated Confidence")

            HStack(spacing: Theme.Spacing.xSmall) {
                ForEach(0..<5, id: \.self) { i in
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                        .fill(i < segs ? Theme.goldPrimary : Theme.inkTertiary.opacity(0.15))
                        .frame(height: 6)
                }
            }

            Button {
                HapticManager.selection()
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    showFullSummary.toggle()
                }
            } label: {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(summ)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineSpacing(6)
                        .lineLimit(showFullSummary ? nil : 4)
                        .multilineTextAlignment(.leading)
                    HStack {
                        Spacer()
                        Text(showFullSummary ? "Show less" : "Tap to read more")
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.securityGold)
                    }
                }
            }
            .buttonStyle(EKPressStyle())

            VStack(spacing: Theme.Spacing.medium) {
                horizonRow(label: "3 MONTHS", target: analysis.targetPrices.shortTerm3m, upside: analysis.upsideDownsidePct.shortTerm)
                horizonRow(label: "12 MONTHS", target: analysis.targetPrices.mediumTerm12m, upside: analysis.upsideDownsidePct.mediumTerm, featured: true)
                horizonRow(label: "3 YEARS", target: analysis.targetPrices.longTerm36m, upside: analysis.upsideDownsidePct.longTerm)
                conformalBoundsView
            }

            Text("Analysis by Nivesh AI \u{2024} Dalal Street weighted")
                .font(Theme.microLabel(size: 9))
                .foregroundStyle(Theme.inkTertiary)
                .frame(maxWidth: .infinity, alignment: .center)

            if let t = tier {
                HStack(spacing: Theme.Spacing.tight) {
                    Text(t.uppercased())
                        .font(Theme.microLabel(size: 7))
                        .foregroundStyle(t == "extreme" ? Theme.bearRed : Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, 2)
                        .background((t == "extreme" ? Theme.bearRed : Theme.inkSecondary).opacity(0.12))
                        .clipShape(Capsule())
                    if let js = viewModel.jobStatus {
                        let cs = js.status == "SUCCEEDED" ? "generated" : js.status.lowercased()
                        Text(cs)
                            .font(Theme.microLabel(size: 7))
                            .foregroundStyle(js.status == "SUCCEEDED" ? Theme.bullGreen : Theme.inkTertiary)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, 2)
                            .background(js.status == "SUCCEEDED" ? Theme.bullGreen.opacity(0.12) : Theme.inkSecondary.opacity(0.06))
                            .clipShape(Capsule())
                    }
                }
            }
        }
        .padding(Theme.Spacing.cardInset)
        .background(Theme.surfaceElevated)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderStrong, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }

    private var signalTimelineSectionView: some View {
        Group {
            if let prices = viewModel.quickInfo?.priceHistory90d, !prices.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    SectionHeaderView(title: "SIGNAL ACCURACY TIMELINE")
                    AnalysisHistoryTimelineView(ticker: ticker, priceHistory: prices)
                }
            }
        }
    }

    private var dialecticDebateSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "DIALECTICAL ANALYSIS")
            HStack(alignment: .top, spacing: Theme.Spacing.tight) {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.up.fill").font(.caption).foregroundStyle(Theme.dataPositive)
                        Text("BULL CASE").font(Theme.sectionCapsLabel()).foregroundStyle(Theme.dataPositive)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(Array(analysis.bullCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 10)).tracking(1.2)
                                .foregroundStyle(Theme.securityGold)
                                .frame(width: 20, height: 20)
                                .background(Theme.securityGold.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .caption))
                                .foregroundStyle(Theme.inkSecondary).lineSpacing(3)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataPositiveMuted.opacity(0.3))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.down.fill").font(.caption).foregroundStyle(Theme.dataNegative)
                        Text("BEAR CASE").font(Theme.sectionCapsLabel(size: 12)).foregroundStyle(Theme.dataNegative)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(Array(analysis.bearCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 10)).tracking(1.2)
                                .foregroundStyle(Theme.bearRed)
                                .frame(width: 20, height: 20)
                                .background(Theme.bearRed.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 13, weight: .medium, relativeTo: .caption))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataNegativeMuted.opacity(0.3))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            }
        }
    }

    private var timeHorizonSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "PRICE PROJECTIONS")
            HStack(spacing: Theme.Spacing.card) {
                horizonCard(label: "3M", target: analysis.targetPrices.shortTerm3m, upside: analysis.upsideDownsidePct.shortTerm)
                horizonCard(label: "12M", target: analysis.targetPrices.mediumTerm12m, upside: analysis.upsideDownsidePct.mediumTerm, featured: true)
                horizonCard(label: "3Y", target: analysis.targetPrices.longTerm36m, upside: analysis.upsideDownsidePct.longTerm)
            }
        }
    }

    private var riskFactorsSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "RISK FACTORS")
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(Array(analysis.keyRisks.enumerated()), id: \.offset) { idx, risk in
                    let severity: SeverityDot.Severity = idx == 0 ? .high : (idx == 1 ? .medium : .low)
                    HStack(spacing: Theme.Spacing.medium) {
                        SeverityDot(severity: severity)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(severity.label).font(Theme.microLabel(size: 9)).foregroundStyle(severity.color)
                            Text(stripEmoji(risk))
                                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        }
                        Spacer()
                    }
                    .padding(Theme.Spacing.card)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
        }
    }

    private var fundamentalsSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "FUNDAMENTALS")

            if let info = viewModel.quickInfo {
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())],
                          spacing: Theme.Spacing.standard) {
                    AnalysisMetricCell(label: "P/E", term: "P/E Ratio",
                                       value: info.peRatio.map { String(format: "%.1f", $0) } ?? "\u{2014}")
                    AnalysisMetricCell(label: "DEBT/EQ", term: "Debt/Equity",
                                       value: info.debtToEquity.map { String(format: "%.2f", $0) } ?? "\u{2014}")
                    AnalysisMetricCell(label: "PROMOTER", term: "Promoter Pledging",
                                       value: info.promoterHoldingPct.map { String(format: "%.1f%%", $0) } ?? "\u{2014}")
                    AnalysisMetricCell(label: "52W HIGH", term: "52W High",
                                       value: info.week52High.map { IndianFormatter.price($0) } ?? "\u{2014}")
                    AnalysisMetricCell(label: "52W LOW", term: "52W Low",
                                       value: info.week52Low.map { IndianFormatter.price($0) } ?? "\u{2014}")
                    AnalysisMetricCell(label: "VOLUME", term: "Bulk Deal",
                                       value: info.volume.map { "\($0)" } ?? "\u{2014}")
                }
            }

            let factors: [(String, String)] = [
                ("MANAGEMENT QUALITY", analysis.keyFactors.managementQuality),
                ("GEOPOLITICAL CONTEXT", analysis.keyFactors.geopoliticalContext),
                ("PROMOTER / FII / DII", analysis.keyFactors.promoterFiiDiiActivity),
                ("TURNAROUND STORY", analysis.keyFactors.turnaroundStory),
                ("GLOBAL MACRO IMPACT", analysis.keyFactors.globalMacroImpact),
                ("NEWS SENTIMENT", analysis.keyFactors.newsSentiment),
            ]
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(factors, id: \.0) { label, text in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(label).font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                        Text(stripEmoji(text))
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                    }
                    .padding(Theme.Spacing.card).frame(maxWidth: .infinity, alignment: .leading)
                    .background( Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSubtle, lineWidth: 0.5))
                }
            }
        }
    }

    private var newsSectionView: some View {
        Group {
            if let news = analysis.recentNews, !news.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    GuillocheDivider()
                    HStack {
                        Text("RECENT NEWS")
                            .font(Theme.officialStampFont(size: 9))
                            .tracking(1.5)
                            .foregroundStyle(Theme.inkSecondary)
                        Spacer()
                        Text("\(news.count) articles")
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    ForEach(news.prefix(5)) { item in
                        NewsItemCard(item: item)
                    }
                }
            }
        }
    }

    private var whatToWatchSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "WHAT TO WATCH")
            VStack(spacing: Theme.Spacing.tight) {
                ForEach(analysis.whatToWatch, id: \.self) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                        Circle().fill(Theme.goldPrimary).frame(width: 6, height: 6).padding(.top, Theme.Spacing.tight)
                        Text(stripEmoji(item))
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.inkPrimary).lineSpacing(3)
                        Spacer()
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.surfaceElevated)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }
            }
        }
    }

    private var disclaimerSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            GuillocheDivider()
            Text(stripEmoji(analysis.disclaimer))
                .font(Theme.microLabel(size: 9)).foregroundStyle(Theme.inkTertiary)
                .lineSpacing(4).frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.card)
                .background(Theme.surfaceElevated.opacity(0.5))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
    }

    private func whatChangedSectionView(previous: StockAnalysis) -> some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "WHAT CHANGED SINCE LAST ANALYSIS")

            VStack(spacing: Theme.Spacing.medium) {
                if analysis.signal != previous.signal {
                    diffRow(label: "AI SIGNAL", oldVal: previous.signal.rawValue, newVal: analysis.signal.rawValue, isPositive: analysis.signal == .bullish)
                }

                if analysis.currentPriceInr != previous.currentPriceInr {
                    let pctChange = ((analysis.currentPriceInr - previous.currentPriceInr) / previous.currentPriceInr) * 100
                    diffRow(label: "PRICE", oldVal: IndianFormatter.priceCompact(previous.currentPriceInr), newVal: IndianFormatter.priceCompact(analysis.currentPriceInr), isPositive: pctChange > 0)
                }

                if analysis.confidencePercent != previous.confidencePercent {
                    let diff = analysis.confidencePercent - previous.confidencePercent
                    diffRow(label: "CONFIDENCE", oldVal: "\(previous.confidencePercent)%", newVal: "\(analysis.confidencePercent)%", isPositive: diff > 0)
                }

                if analysis.targetPrices.mediumTerm12m != previous.targetPrices.mediumTerm12m {
                    let diff = analysis.targetPrices.mediumTerm12m - previous.targetPrices.mediumTerm12m
                    diffRow(label: "12M TARGET", oldVal: IndianFormatter.priceCompact(previous.targetPrices.mediumTerm12m), newVal: IndianFormatter.priceCompact(analysis.targetPrices.mediumTerm12m), isPositive: diff > 0)
                }
            }
            .padding(Theme.Spacing.card)
            .background(Theme.surfaceElevated)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
        }
    }

    private func horizonRow(label: String, target: Double, upside: Double, featured: Bool = false) -> some View {
        HStack(spacing: Theme.Spacing.standard) {
            Text(label)
                .font(featured ? Theme.monoTabular(size: 13).weight(.bold) : Theme.monoTabular(size: 12))
                .foregroundStyle(featured ? Theme.goldPrimary : Theme.inkSecondary)
                .frame(width: 80, alignment: .leading)
            Image(systemName: upside >= 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                .font(.caption2)
                .foregroundStyle(upside >= 0 ? Theme.dataPositive : Theme.dataNegative)
            Text(IndianFormatter.priceCompact(target))
                .font(Theme.monoTabular(size: 14)).foregroundStyle(Theme.inkPrimary)
            Spacer()
            PnlBadge(value: upside, showPercentage: true)
        }
        .padding(.horizontal, Theme.Spacing.medium).padding(.vertical, Theme.Spacing.small)
        .background(featured ? Theme.goldMuted.opacity(0.5) : Color.clear)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }

    private func signalBadgeTextColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish, .cautiously_bullish: return .white
        case .bearish, .cautiously_bearish: return .white
        case .hold, .neutral: return Theme.goldPrimary
        }
    }

    private func signalBadgeBgColor(_ signal: Signal) -> Color {
        switch signal {
        case .bullish, .cautiously_bullish: return Theme.dataPositive
        case .bearish, .cautiously_bearish: return Theme.dataNegative
        case .hold, .neutral: return Theme.goldMuted
        }
    }

    private func confidenceSegments(_ pct: Int) -> Int {
        if pct >= 80 { return 5 }
        if pct >= 60 { return 4 }
        if pct >= 40 { return 3 }
        if pct >= 20 { return 2 }
        return 1
    }

    @ViewBuilder
    private func pricePerformanceChip(label: String, pct: Double?) -> some View {
        if let pct = pct {
            let isPositive = pct >= 0
            HStack(spacing: Theme.Spacing.xSmall) {
                Image(systemName: isPositive ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                    .font(Theme.officialStampFont(size: 7))
                Text("\(label)  \(isPositive ? "+" : "")\(String(format: "%.1f", pct))%")
                    .font(Theme.serialNumberFont(size: 11))
            }
            .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.xSmall)
            .background((isPositive ? Theme.bullGreen : Theme.bearRed).opacity(0.10))
            .clipShape(Capsule())
        }
    }

    private func horizonCard(label: String, target: Double, upside: Double, featured: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(label)
                .font(Theme.sectionCapsLabel(size: 9))
                .foregroundStyle(featured ? Theme.goldPrimary : Theme.inkSecondary)
                .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                .background(featured ? Theme.goldMuted : Theme.inkTertiary.opacity(0.1))
                .clipShape(Capsule())
            Text(IndianFormatter.priceCompact(target))
                .font(Theme.dataLarge(size: featured ? 24 : 20, relativeTo: featured ? .title : .title2))
                .foregroundStyle(Theme.inkPrimary)
            PnlBadge(value: upside, showPercentage: true)
        }
        .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
        .background(featured ? Theme.surfaceFloat : Theme.surfaceElevated)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
            .stroke(featured ? Theme.borderStrong : Theme.borderSubtle, lineWidth: featured ? 1 : 0.5))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }

    private func diffRow(label: String, oldVal: String, newVal: String, isPositive: Bool) -> some View {
        HStack(spacing: Theme.Spacing.medium) {
            Text(label).font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary).frame(width: 80, alignment: .leading)
            Text(oldVal).font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkTertiary).strikethrough()
            Image(systemName: "arrow.right").font(.caption2).foregroundStyle(Theme.inkTertiary)
            Text(newVal).font(Theme.monoTabular(size: 13).weight(.bold)).foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            Spacer()
        }
    }

    @ViewBuilder
    private var conformalBoundsView: some View {
        if let upper = analysis.conformalTargetUpper3m,
           let lower = analysis.conformalTargetLower3m,
           upper > 0, lower > 0 {
            ConformalBoundsRow(upper: upper, lower: lower)
        }
    }
}

// Separate struct — prevents chkstk_darwin (AGENTS.md §6.6)
struct ConformalBoundsRow: View {
    let upper: Double
    let lower: Double

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("3M CONFORMAL BOUNDS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                HStack(spacing: Theme.Spacing.small) {
                    Text(IndianFormatter.priceCompact(lower))
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.bearRed)
                    Text("→")
                        .font(Theme.engravedSerif(size: 11, relativeTo: .caption2))
                        .foregroundStyle(Theme.inkTertiary)
                    Text(IndianFormatter.priceCompact(upper))
                        .font(Theme.serialNumberFont(size: 13))
                        .foregroundStyle(Theme.bullGreen)
                }
            }
            Spacer()
            Text("90% CI")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.small)
        .background(Theme.canvasDeep.opacity(0.4))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
    }
}
