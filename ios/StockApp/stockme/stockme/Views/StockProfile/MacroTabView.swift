import SwiftUI

struct MacroTabView: View {
    let ticker: String
    let exchange: String
    @ObservedObject var vm: StockProfileViewModel
    @State private var macroContext: MacroContextData?
    @State private var macroLoading = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.card) {
                if macroLoading {
                    SPSkeletonBlock(rows: 4)
                } else if let macro = macroContext {
                    MacroMoodGaugeView(mood: macro.marketMood)
                    MacroStripCardView(strip: macro.macroStrip)
                    MacroImpactListView(ticker: ticker, impacts: macro.stockImpact)
                    MacroAIInsightCardView(aiSummary: macro.aiSummary, aiSentiment: macro.aiSentiment)
                } else {
                    SPEmptyStateView(message: "Macro context unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await loadMacroContext() }
    }

    private func loadMacroContext() async {
        guard macroContext == nil else { return }
        macroLoading = true
        let sector = vm.quickInfo?.sector ?? ""
        macroContext = await NetworkManager.shared.fetchMacroContext(
            ticker: ticker, exchange: exchange, sector: sector
        )
        macroLoading = false
    }
}

// MARK: - Market Mood Gauge

struct MacroMoodGaugeView: View {
    let mood: MarketMoodData?

    var body: some View {
        if let mood = mood {
            VStack(spacing: Theme.Spacing.standard) {
                Text("MARKET MOOD INDEX")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                let score = Double(mood.score ?? 50)
                let zoneColor: Color = {
                    switch mood.zone ?? "" {
                    case "EXTREME_FEAR": return Theme.bearRed
                    case "FEAR": return Theme.bearRed.opacity(0.7)
                    case "EXTREME_GREED": return Theme.bullGreen
                    case "GREED": return Theme.bullGreen.opacity(0.7)
                    default: return Theme.holdAmber
                    }
                }()

                ZStack {
                    ForEach(0..<5, id: \.self) { seg in
                        let segStart = Double(seg) / 5.0
                        let segEnd = Double(seg + 1) / 5.0
                        let segColor: Color = {
                            switch seg {
                            case 0: return Theme.bearRed
                            case 1: return Theme.bearRed.opacity(0.6)
                            case 2: return Theme.holdAmber
                            case 3: return Theme.bullGreen.opacity(0.6)
                            default: return Theme.bullGreen
                            }
                        }()
                        Circle()
                            .trim(from: 0.25 + segStart * 0.5, to: 0.25 + segEnd * 0.5)
                            .stroke(segColor, style: StrokeStyle(lineWidth: 14, lineCap: .butt))
                            .frame(width: UIScreen.main.bounds.width * 0.40, height: UIScreen.main.bounds.width * 0.40)
                            .rotationEffect(.degrees(180))
                    }

                    ForEach([0, 25, 50, 75, 100], id: \.self) { tick in
                        let tickAngle = Angle(degrees: -90 + (Double(tick) / 100.0 * 180))
                        Rectangle()
                            .fill(Theme.inkTertiary.opacity(0.3))
                            .frame(width: 2, height: 12)
                            .offset(y: -78)
                            .rotationEffect(tickAngle)
                    }

                    let needleAngle = Angle(degrees: -90 + (score / 100.0 * 180))
                    Path { path in
                        path.move(to: CGPoint(x: 0, y: 8))
                        path.addLine(to: CGPoint(x: 0, y: -70))
                    }
                    .stroke(Theme.inkPrimary, style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                    .rotationEffect(needleAngle)

                    Circle()
                        .fill(Theme.inkPrimary)
                        .frame(width: 10, height: 10)
                }
                .frame(width: UIScreen.main.bounds.width * 0.40, height: UIScreen.main.bounds.height * 0.13)

                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("\(Int(score))")
                        .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                        .foregroundStyle(zoneColor)
                    Text(mood.zone?.replacingOccurrences(of: "_", with: " ") ?? "")
                        .font(Theme.officialStampFont(size: 10))
                        .tracking(1.0)
                        .foregroundStyle(zoneColor)
                }

                HStack {
                    Text("0").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Spacer()
                    Text("25").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Spacer()
                    Text("50").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Spacer()
                    Text("75").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                    Spacer()
                    Text("100").font(Theme.microLabel(size: 8)).foregroundStyle(Theme.inkTertiary)
                }
                .padding(.horizontal, Theme.Spacing.small)

                if let interp = mood.interpretation, !interp.isEmpty {
                    Text(interp)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .lineSpacing(3)
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .explainableTerm("MMI")
        }
    }
}

// MARK: - Macro Strip Card

struct MacroStripCardView: View {
    let strip: MacroStrip?

    var body: some View {
        if let strip = strip {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("MACRO INDICATORS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                HStack(spacing: Theme.Spacing.none) {
                    MacroStripItemView(
                        label: "BRENT",
                        value: strip.brentOilUsd.map { "$\(String(format: "%.0f", $0))" } ?? "N/A",
                        subtitle: "/bbl",
                        icon: "fuelpump.fill",
                        color: (strip.brentOilUsd ?? 0) > 85 ? Theme.bearRed : Theme.holdAmber
                    )
                    MacroStripItemView(
                        label: "USD/INR",
                        value: strip.usdInr.map { "Rs.\(String(format: "%.1f", $0))" } ?? "N/A",
                        subtitle: "Rs. per $",
                        icon: "dollarsign.arrow.circlepath",
                        color: (strip.usdInr ?? 0) > 85 ? Theme.bearRed : Theme.bullGreen
                    )
                    MacroStripItemView(
                        label: "VIX",
                        value: strip.indiaVix.map { String(format: "%.1f", $0) } ?? "N/A",
                        subtitle: "fear gauge",
                        icon: "waveform.path.ecg",
                        color: (strip.indiaVix ?? 0) > 20 ? Theme.bearRed : (strip.indiaVix ?? 0) > 15 ? Theme.holdAmber : Theme.bullGreen
                    )
                    MacroStripItemView(
                        label: "RBI",
                        value: strip.rbiRepoRatePct.map { "\(String(format: "%.2f", $0))%" } ?? "N/A",
                        subtitle: "repo rate",
                        icon: "building.columns.fill",
                        color: Theme.avatarBlue
                    )
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

struct MacroStripItemView: View {
    let label: String
    let value: String
    let subtitle: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: icon)
                .font(.caption)
                .foregroundStyle(color)
            Text(value)
                .font(Theme.serialNumberFont(size: 14, relativeTo: .footnote))
                .foregroundStyle(Theme.inkPrimary)
            Text(label)
                .font(Theme.microLabel(size: 7))
                .tracking(0.5)
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Macro Impact List

struct MacroImpactListView: View {
    let ticker: String
    let impacts: [StockMacroImpact]?

    var body: some View {
        if let impacts = impacts, !impacts.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("HOW MACRO AFFECTS \(ticker.uppercased())")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                ForEach(impacts) { item in
                    HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                        let impactColor: Color = item.impact == "POSITIVE" ? Theme.bullGreen : item.impact == "NEGATIVE" ? Theme.bearRed : Theme.holdAmber
                        Text(item.impact)
                            .font(Theme.microLabel(size: 7))
                            .tracking(0.5)
                            .foregroundStyle(impactColor)
                            .padding(.horizontal, Theme.Spacing.tight)
                            .padding(.vertical, Theme.Spacing.xSmall)
                            .background(
                                (item.impact == "POSITIVE" ? Theme.bullGreen :
                                 item.impact == "NEGATIVE" ? Theme.bearRed :
                                 Theme.holdAmber).opacity(0.12)
                            )
                            .clipShape(Capsule())

                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            HStack {
                                Text(item.factor)
                                    .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                    .foregroundStyle(Theme.inkPrimary)
                                Spacer()
                                Text(item.value)
                                    .font(Theme.microLabel(size: 9))
                                    .foregroundStyle(Theme.inkSecondary)
                            }
                            Text(item.detail)
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(Theme.inkSecondary)
                                .lineLimit(3)
                                .lineSpacing(2)
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.inkTertiary.opacity(0.03))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))

                    if item.id != impacts.last?.id {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                            .padding(.horizontal, Theme.Spacing.standard)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}

// MARK: - AI Macro Insight Card

struct MacroAIInsightCardView: View {
    let aiSummary: String?
    let aiSentiment: String?

    var body: some View {
        if let aiSummary = aiSummary, !aiSummary.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack(spacing: Theme.Spacing.small) {
                    Image(systemName: "sparkles")
                        .font(.caption)
                        .foregroundStyle(Theme.securityGold)
                    Text("AI MACRO ANALYSIS")
                        .font(Theme.officialStampFont(size: 9))
                        .tracking(1.5)
                        .foregroundStyle(Theme.securityGold)
                }

                Text(aiSummary)
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .body))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineSpacing(5)
                    .lineLimit(8)

                if let sentiment = aiSentiment, !sentiment.isEmpty {
                    SectionDivider()
                    HStack(spacing: Theme.Spacing.small) {
                        Text("SENTIMENT:")
                            .font(Theme.officialStampFont(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(sentiment)
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(3)
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
    }
}
