import SwiftUI
import Charts

// MARK: - Governance Tab

struct GovernanceTabView: View {
    let ticker: String
    @ObservedObject var vm: StockProfileViewModel
    @State private var governanceCards: [HarvestedCard] = []
    // One surveillance source on screen: when the risk-flags card covers ASM/GSM, hide the /quick-info banner.
    @State private var riskFlagsCoverSurveillance = false

    var body: some View {
        LazyVStack(spacing: Theme.Spacing.card) {
            if vm.overviewLoading {
                SPSkeletonBlock(rows: 4)
                SPSkeletonBlock(rows: 4)
            } else if let info = vm.quickInfo {
                if !riskFlagsCoverSurveillance {
                    GovernanceSurveillanceBannerView(info: info)
                }
                GovernanceScoreCardView(info: info)
                GovernancePromoterSectionView(info: info, promoterHistory: vm.promoterHistory)
                GovernanceInstitutionalSectionView(info: info)
                GovernanceLeadershipSectionView(officers: info.officers ?? [])
                GovernanceDebtGaugeView(info: info)
            } else {
                SPEmptyStateView(message: "Governance data unavailable")
            }

            GuillocheDivider()
            HarvesterGovernanceSectionView(ticker: ticker, cards: governanceCards)
        }
        .padding(.horizontal, Theme.screenPadding)
        .padding(.vertical, Theme.Spacing.card)
        .task { await vm.fetchOverview() }
        .task { await vm.fetchFinancials() }
        .task { governanceCards = (try? await NetworkManager.shared.fetchGovernanceCards(ticker: ticker)) ?? [] }
        .task {
            riskFlagsCoverSurveillance = (try? await NetworkManager.shared.fetchRiskFlags(symbol: ticker))?.checks?.contains("surveillance") ?? false
        }
    }
}

// MARK: - Surveillance Banner

struct GovernanceSurveillanceBannerView: View {
    let info: QuickInfo

    var body: some View {
        let status = info.asmGsmStatus ?? "UNKNOWN"
        let isGSM = status == "GSM"
        let isASM = status == "ASM"

        VStack(spacing: Theme.Spacing.small) {
            HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: isGSM ? "exclamationmark.triangle.fill" :
                               isASM ? "exclamationmark.shield.fill" :
                               "checkmark.shield.fill")
                    .font(.title3)
                    .foregroundStyle(isGSM ? Theme.bearRed : isASM ? Theme.holdAmber : Theme.bullGreen)

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("SURVEILLANCE STATUS")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(status)
                        .font(Theme.serialNumberFont(size: 16, relativeTo: .title3))
                        .foregroundStyle(isGSM ? Theme.bearRed : isASM ? Theme.holdAmber : Theme.bullGreen)
                }
                Spacer()
            }

            if isGSM {
                Text("This stock is on the GSM (Graded Surveillance Measure) list. Trading is restricted — delivery-only, no intraday. Settlement may be blocked by some brokers.")
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.bearRed)
                    .lineSpacing(3)
            } else if isASM {
                Text("This stock is under Additional Surveillance Measures (ASM). Higher margins apply. Monitor for potential GSM escalation.")
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                    .foregroundStyle(Theme.holdAmber)
                    .lineSpacing(3)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .explainableTerm("ASM/GSM")
    }
}

// MARK: - AI Governance Score Card

struct GovernanceScoreCardView: View {
    let info: QuickInfo

    var body: some View {
        if let score = info.governanceScore {
            VStack(spacing: Theme.Spacing.standard) {
                Text("AI GOVERNANCE SCORE")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                HStack(spacing: Theme.Spacing.card) {
                    ZStack {
                        Circle()
                            .stroke(Theme.inkTertiary.opacity(0.15), lineWidth: 6)
                            .frame(width: UIScreen.main.bounds.width * 0.18, height: UIScreen.main.bounds.width * 0.18)
                        Circle()
                            .trim(from: 0, to: CGFloat(score) / 100.0)
                            .stroke(
                                score >= 70 ? Theme.bullGreen :
                                score >= 40 ? Theme.holdAmber : Theme.bearRed,
                                style: StrokeStyle(lineWidth: 6, lineCap: .round)
                            )
                            .frame(width: UIScreen.main.bounds.width * 0.18, height: UIScreen.main.bounds.width * 0.18)
                            .rotationEffect(.degrees(-90))
                        VStack(spacing: Theme.Spacing.xSmall) {
                            Text("\(score)")
                                .font(Theme.serialNumberFont(size: 18, relativeTo: .title3))
                                .foregroundStyle(Theme.inkPrimary)
                            Text("/100")
                                .font(Theme.microLabel(size: 7))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }

                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text(score >= 70 ? "Strong Governance" :
                             score >= 40 ? "Moderate Concerns" : "Governance FAIL")
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .body))
                            .foregroundStyle(score >= 70 ? Theme.bullGreen :
                                           score >= 40 ? Theme.holdAmber : Theme.bearRed)
                        Text("Based on multi-agent AI analysis of corporate filings, promoter activity, and regulatory data")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(3)
                    }
                    Spacer()
                }

                if let flags = info.governanceRedFlags, !flags.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        Text("FLAGGED ISSUES")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.bearRed)
                        ForEach(flags, id: \.self) { flag in
                            HStack(alignment: .top, spacing: Theme.Spacing.small) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.caption2)
                                    .foregroundStyle(Theme.bearRed)
                                Text(flag)
                                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                    .foregroundStyle(Theme.inkPrimary)
                            }
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.bearRed.opacity(0.06))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

// MARK: - Promoter Section

struct GovernancePromoterSectionView: View {
    let info: QuickInfo
    let promoterHistory: [PromoterHistoryPoint]

    var body: some View {
        let promoter = info.promoterHoldingPct ?? 0
        let pledged = info.promoterPledgedPct
        let barWidth = UIScreen.main.bounds.width - (Theme.screenPadding * 2) - (Theme.Spacing.card * 2)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER HOLDING")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack(spacing: Theme.Spacing.card) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("\(String(format: "%.1f", promoter))%")
                        .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                        .foregroundStyle(Theme.securityGold)
                    Text("Promoter Stake")
                        .font(Theme.microLabel(size: 9))
                        .foregroundStyle(Theme.inkTertiary)
                }

                Spacer()

                if let pledged = pledged {
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("\(String(format: "%.1f", pledged))%")
                            .font(Theme.serialNumberFont(size: 20, relativeTo: .title2))
                            .foregroundStyle(pledged > 30 ? Theme.bearRed : Theme.holdAmber)
                        Text("Pledged")
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    .explainableTerm("Promoter Pledging")
                }
            }

            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.1))
                    .frame(height: 8)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(promoter > 50 ? Theme.bullGreen : promoter > 25 ? Theme.holdAmber : Theme.bearRed)
                    .frame(width: barWidth * CGFloat(min(promoter / 100.0, 1.0)), height: 8)
            }
            .frame(height: 8)

            HStack {
                Text("0%")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("Low promoter stake = weak alignment with shareholders")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                Spacer()
                Text("100%")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
            }

            if pledged ?? 0 > 30 {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.caption2)
                        .foregroundStyle(Theme.bearRed)
                    Text("Promoter pledge exceeds 30% — margin-call cascade risk exists")
                        .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                        .foregroundStyle(Theme.bearRed)
                }
            }

            if !promoterHistory.isEmpty {
                GuillocheDivider()
                Text("HISTORICAL TREND")
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(1.0)
                    .foregroundStyle(Theme.inkTertiary)

                Chart {
                    ForEach(promoterHistory, id: \.period) { pt in
                        LineMark(
                            x: .value("Period", pt.period),
                            y: .value("Holding", pt.promoter)
                        )
                        .foregroundStyle(Theme.securityGold)
                        PointMark(
                            x: .value("Period", pt.period),
                            y: .value("Holding", pt.promoter)
                        )
                        .symbolSize(20)
                        .foregroundStyle(Theme.securityGold)
                    }
                }
                .chartXAxis {
                    AxisMarks { _ in AxisValueLabel() }
                }
                .chartYAxis {
                    AxisMarks { _ in AxisValueLabel() }
                }
                .frame(height: UIScreen.main.bounds.height * 0.30)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Institutional Section

struct GovernanceInstitutionalSectionView: View {
    let info: QuickInfo

    var body: some View {
        let fii = info.fiiHoldingPct ?? 0
        let dii = info.diiHoldingPct ?? 0
        let institutional = info.institutionalTotalPct
        let promoter = info.promoterHoldingPct ?? 0
        let publicHolding = max(0, 100 - promoter - institutional)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("INSTITUTIONAL OWNERSHIP")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            Chart {
                BarMark(x: .value("Pct", promoter), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.securityGold)
                if info.hasFiiDiiSplit {
                    BarMark(x: .value("Pct", fii), y: .value("Type", "Holding"))
                        .foregroundStyle(Theme.bullGreen)
                    BarMark(x: .value("Pct", dii), y: .value("Type", "Holding"))
                        .foregroundStyle(Theme.avatarBlue)
                } else {
                    BarMark(x: .value("Pct", institutional), y: .value("Type", "Holding"))
                        .foregroundStyle(Theme.bullGreen)
                }
                BarMark(x: .value("Pct", publicHolding), y: .value("Type", "Holding"))
                    .foregroundStyle(Theme.inkTertiary.opacity(0.3))
            }
            .chartXAxis {
                AxisMarks { _ in AxisValueLabel() }
            }
            .frame(height: 36)

            HStack(spacing: Theme.Spacing.standard) {
                SPLegendDot(color: Theme.securityGold, label: "Promoter", value: promoter)
                if info.hasFiiDiiSplit {
                    SPLegendDot(color: Theme.bullGreen, label: "FII", value: fii)
                    SPLegendDot(color: Theme.avatarBlue, label: "DII", value: dii)
                } else {
                    SPLegendDot(color: Theme.bullGreen, label: "FII+DII", value: institutional)
                }
                SPLegendDot(color: Theme.inkTertiary.opacity(0.4), label: "Public", value: publicHolding)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Leadership Section

struct GovernanceLeadershipSectionView: View {
    let officers: [String]

    var body: some View {
        if !officers.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("KEY OFFICERS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                ForEach(Array(officers.enumerated()), id: \.offset) { idx, name in
                    HStack(spacing: Theme.Spacing.standard) {
                        Text("\(idx + 1).")
                            .font(Theme.officialStampFont(size: 10))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(name)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                        Spacer()
                    }
                    if idx < officers.count - 1 {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .explainableTerm("KEY OFFICERS")
        }
    }
}

// MARK: - Debt Gauge

struct GovernanceDebtGaugeView: View {
    let info: QuickInfo

    var body: some View {
        let dte = info.debtToEquity ?? 0
        let gaugeWidth = UIScreen.main.bounds.width - (Theme.screenPadding * 2) - (Theme.Spacing.card * 2)

        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("DEBT HEALTH")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            HStack {
                Text("D/E Ratio:")
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .body))
                    .foregroundStyle(Theme.inkSecondary)
                Text(String(format: "%.2f", dte))
                    .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                    .foregroundStyle(dte > 2 ? Theme.bearRed : dte > 1 ? Theme.holdAmber : Theme.bullGreen)
                Spacer()
            }

            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.1))
                    .frame(height: 8)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bullGreen.opacity(0.35))
                    .frame(width: gaugeWidth * 0.33, height: 8)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.holdAmber.opacity(0.35))
                    .frame(width: gaugeWidth * 0.33, height: 8)
                    .offset(x: gaugeWidth * 0.33)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bearRed.opacity(0.3))
                    .frame(width: gaugeWidth * 0.34, height: 8)
                    .offset(x: gaugeWidth * 0.66)
                Circle()
                    .fill(dte > 2 ? Theme.bearRed : dte > 1 ? Theme.holdAmber : Theme.bullGreen)
                    .frame(width: 10, height: 10)
                    .offset(x: gaugeWidth * CGFloat(min(dte / 3.0, 1.0)) - 5)
            }
            .frame(height: 10)

            HStack {
                Text("Safe <1.0")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bullGreen)
                Spacer()
                Text("Moderate 1–2")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.holdAmber)
                Spacer()
                Text("High >2.0")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bearRed)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .explainableTerm("Debt/Equity")
    }
}

// MARK: - Harvester Section

struct HarvesterGovernanceSectionView: View {
    let ticker: String
    let cards: [HarvestedCard]

    var body: some View {
        if !cards.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("REGULATORY & RATING INTELLIGENCE")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)
                    .padding(.horizontal, Theme.screenPadding)

                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Theme.Spacing.standard) {
                        ForEach(cards) { card in
                            GovernanceCompactCardView(card: card)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.vertical, Theme.Spacing.small)
                }
            }
        }
    }
}

struct GovernanceCompactCardView: View {
    let card: HarvestedCard

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            HStack(spacing: Theme.Spacing.tight) {
                Image(systemName: sourceIcon(for: card.sourceType))
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(credibilityColor(for: card.credibilityScore))
                Text("\(shortLabel(for: card.sourceType)) • \(card.credibilityScore)/10")
                    .font(Theme.serialNumberFont(size: 8))
                    .foregroundStyle(credibilityColor(for: card.credibilityScore))
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(credibilityColor(for: card.credibilityScore).opacity(0.10))
                    .cornerRadius(Theme.CornerRadius.small)
            }

            Text(card.title)
                .font(Theme.engravedSerif(size: 12, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
                .lineLimit(2)

            if let summary = card.reformattedSummary, !summary.isEmpty {
                Text(summary)
                    .font(Theme.engravedSerif(size: 11, weight: .regular))
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
                    .lineSpacing(2)
            }

            Spacer(minLength: 0)
        }
        .padding(Theme.Spacing.card)
        .frame(width: UIScreen.main.bounds.width * 0.7)
        .banknoteCard()
        .ekPress()
        .onTapGesture {
            SafeURL.open(card.sourceUrl)
        }
    }

    private func shortLabel(for sourceType: String) -> String {
        switch sourceType.uppercased() {
        case "CRISIL_RATING": return "CRISIL"
        case "ICRA_RATING": return "ICRA"
        case "CARE_RATING": return "CARE"
        case "INDIA_RATINGS": return "India Ratings"
        case "FUND_MANAGER_INTERVIEW": return "CNBC Expert"
        case "EXPERT_COLUMN": return "Columnist"
        case "SEBI_FILING", "EXCHANGE_FILING": return "NSE Filing"
        case "SEBI_RIA_NOTE": return "SEBI RIA"
        case "AMFI_DATA": return "AMFI"
        case "YOUTUBE": return "YouTube"
        default: return sourceType.capitalized
        }
    }

    private func sourceIcon(for sourceType: String) -> String {
        switch sourceType.uppercased() {
        case "SEBI_FILING", "EXCHANGE_FILING": return "building.columns.fill"
        case "CRISIL_RATING", "ICRA_RATING", "CARE_RATING", "INDIA_RATINGS": return "checkmark.shield.fill"
        case "FUND_MANAGER_INTERVIEW": return "person.fill.checkmark"
        case "EXPERT_COLUMN": return "newspaper.fill"
        case "SEBI_RIA_NOTE": return "person.badge.shield.checkmark.fill"
        case "AMFI_DATA": return "chart.bar.doc.horizontal.fill"
        case "YOUTUBE": return "play.rectangle.fill"
        default: return "doc.text.fill"
        }
    }

    private func credibilityColor(for score: Int) -> Color {
        switch score {
        case 10: return Theme.bullGreen
        case 8...9: return Theme.securityGold
        case 6...7: return Theme.inkSecondary
        default: return Theme.inkTertiary
        }
    }
}
