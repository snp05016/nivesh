import SwiftUI

struct AnalysisCoreSections: View {
    let analysis: StockAnalysis
    let previousAnalysis: StockAnalysis?
    let ticker: String
    let livePrice: Double?
    @ObservedObject var viewModel: AnalysisViewModel
    @State private var showFullSummary = false

    var body: some View {
        LazyVStack(spacing: 48) { // Premium Spacing (Rule 8: White space increases perceived importance)
            ArchivedReportBanner()
            stockHeaderSectionView
            aiSummarySectionView
            
            if let prev = previousAnalysis, prev.analysisDate != analysis.analysisDate,
               prev.currentPriceInr != analysis.currentPriceInr {
                whatChangedSectionView(previous: prev)
            }
            dialecticDebateSectionView
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
                    if let info = viewModel.quickInfo, let change = info.change {
                        HStack(spacing: Theme.Spacing.tight) {
                            Image(systemName: change >= 0 ? "arrowtriangle.up.fill" : "arrowtriangle.down.fill")
                                .font(.caption2)
                            Text(IndianFormatter.signedPrice(change))
                            Text("(\(info.changePercent.map { $0.percentFormatted } ?? "—"))")
                        }
                        .font(Theme.monoTabular(size: 14, relativeTo: .footnote))
                        .foregroundStyle(change >= 0 ? Theme.dataPositive : Theme.dataNegative)
                    }
                    if livePrice != nil {
                        HStack(spacing: Theme.Spacing.small) {
                            Circle().fill(Theme.dataPositive).frame(width: 6, height: 6)
                            Text("LIVE").font(Theme.microLabel(size: 9)).foregroundStyle(Theme.dataPositive)
                        }
                    }
                }
                Spacer()
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

    private var aiSummarySectionView: some View {
        let summ = analysis.keyFactors.fundamentalsSummary
        
        return VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("EXECUTIVE SUMMARY")
                .font(Theme.sectionCapsLabel(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)
                
            Button {
                HapticManager.selection()
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    showFullSummary.toggle()
                }
            } label: {
                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    Text(summ)
                        .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineSpacing(7)
                        .lineLimit(showFullSummary ? nil : 4)
                        .multilineTextAlignment(.leading)
                    
                    HStack {
                        Spacer()
                        Text(showFullSummary ? "Read less" : "Read full summary")
                            .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.securityGold)
                            .padding(.top, Theme.Spacing.small)
                    }
                }
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(Theme.Spacing.cardInset)
        .background(Theme.surfaceElevated)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }

    private var dialecticDebateSectionView: some View {
        VStack(spacing: Theme.Spacing.standard) {
            SectionHeaderView(title: "DIALECTICAL ANALYSIS")
            
            // Premium UI uses stacking on mobile to avoid horizontal text squishing
            VStack(spacing: Theme.Spacing.card) {
                // BULL CASE
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.up.fill").font(.caption).foregroundStyle(Theme.dataPositive)
                        Text("BULL CASE").font(Theme.sectionCapsLabel()).foregroundStyle(Theme.dataPositive)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    
                    ForEach(Array(analysis.bullCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 11)).tracking(1.2)
                                .foregroundStyle(Theme.securityGold)
                                .frame(width: 24, height: 24)
                                .background(Theme.securityGold.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(4)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataPositiveMuted.opacity(0.2))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                
                // BEAR CASE
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "arrowtriangle.down.fill").font(.caption).foregroundStyle(Theme.dataNegative)
                        Text("BEAR CASE").font(Theme.sectionCapsLabel(size: 12)).foregroundStyle(Theme.dataNegative)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    
                    ForEach(Array(analysis.bearCase.prefix(3).enumerated()), id: \.offset) { idx, point in
                        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
                            Text("\(idx + 1)")
                                .font(Theme.officialStampFont(size: 11)).tracking(1.2)
                                .foregroundStyle(Theme.bearRed)
                                .frame(width: 24, height: 24)
                                .background(Theme.bearRed.opacity(0.15))
                                .clipShape(Circle())
                            Text(stripEmoji(point))
                                .font(Theme.engravedSerif(size: 14, weight: .medium, relativeTo: .body))
                                .foregroundStyle(Theme.inkPrimary).lineSpacing(4)
                        }
                    }
                }
                .padding(Theme.Spacing.card).frame(maxWidth: .infinity)
                .background(Theme.dataNegativeMuted.opacity(0.2))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
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
                // Eager 3-col layout (2 rows). A LazyVGrid here nests a vertical-lazy
                // container inside the parent LazyVStack/ScrollView (same-axis), which
                // causes main-thread layout thrash and a scroll hang at this section.
                VStack(spacing: Theme.Spacing.standard) {
                    HStack(spacing: Theme.Spacing.standard) {
                        AnalysisMetricCell(label: "P/E", term: "P/E Ratio",
                                           value: info.peRatio.map { String(format: "%.1f", $0) } ?? "\u{2014}")
                        AnalysisMetricCell(label: "DEBT/EQ", term: "Debt/Equity",
                                           value: info.debtToEquity.map { String(format: "%.2f", $0) } ?? "\u{2014}")
                        AnalysisMetricCell(label: "PROMOTER", term: "Promoter Pledging",
                                           value: info.promoterHoldingPct.map { String(format: "%.1f%%", $0) } ?? "\u{2014}")
                    }
                    HStack(spacing: Theme.Spacing.standard) {
                        AnalysisMetricCell(label: "52W HIGH", term: "52W High",
                                           value: info.week52High.map { IndianFormatter.price($0) } ?? "\u{2014}")
                        AnalysisMetricCell(label: "52W LOW", term: "52W Low",
                                           value: info.week52Low.map { IndianFormatter.price($0) } ?? "\u{2014}")
                        AnalysisMetricCell(label: "VOLUME", term: "Bulk Deal",
                                           value: info.volume.map { "\($0)" } ?? "\u{2014}")
                    }
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
                NewsSectionView(news: news)
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
                // Only the observed price is compared; legacy signal, confidence and target rows were removed (spec 10.4).
                diffRow(label: "PRICE", oldVal: IndianFormatter.priceCompact(previous.currentPriceInr), newVal: IndianFormatter.priceCompact(analysis.currentPriceInr), isPositive: analysis.currentPriceInr > previous.currentPriceInr)
            }
            .padding(Theme.Spacing.card)
            .background(Theme.surfaceElevated)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.borderSubtle, lineWidth: 0.5))
        }
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

    private func diffRow(label: String, oldVal: String, newVal: String, isPositive: Bool) -> some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(spacing: Theme.Spacing.medium) {
            Text(label).font(Theme.microLabel()).foregroundStyle(Theme.inkSecondary).frame(width: colW * 0.23, alignment: .leading)
            Text(oldVal).font(Theme.monoTabular(size: 13)).foregroundStyle(Theme.inkTertiary).strikethrough()
            Image(systemName: "arrow.right").font(.caption2).foregroundStyle(Theme.inkTertiary)
            Text(newVal).font(Theme.monoTabular(size: 13).weight(.bold)).foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            Spacer()
        }
    }
}

/// Shown at the top of every saved legacy report (spec 10.4). Those blobs stay decodable,
/// but their figures came from the retired pipeline and were never validated.
private struct ArchivedReportBanner: View {
    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            Image(systemName: "archivebox")
                .font(.footnote)
                .foregroundStyle(Theme.inkSecondary)
                .accessibilityHidden(true)
            Text("Archived report from the previous engine. Its figures were not computed or validated by the current method.")
                .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
                .lineSpacing(3)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.card)
        .background(Theme.surfaceElevated)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderSubtle, lineWidth: 0.5))
        .accessibilityElement(children: .combine)
    }
}
