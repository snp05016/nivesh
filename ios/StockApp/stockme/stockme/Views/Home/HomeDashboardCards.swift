import SwiftUI

// MARK: - Design System Constants (Phase 1 redesign — all Theme.* tokens)

private let cardHPad: CGFloat = Theme.Spacing.card
private let cardVPad: CGFloat = Theme.Spacing.standard
private let rowSpacing: CGFloat = Theme.Spacing.medium
private let sectionGap: CGFloat = Theme.Spacing.tight

private let bullGreen  = Theme.dataPositive
private let bearRed    = Theme.dataNegative
private let neutralAmber = Theme.holdAmber
private let goldAccent = Theme.goldPrimary
private let dimText    = Theme.inkSecondary
private let subtleText = Theme.inkTertiary

// MARK: - Daily Action Card

struct DailyActionCard: View {
    let response: DailyActionResponse

    private var borderColor: Color {
        switch response.urgency {
        case "high":   return Theme.bearRed
        case "medium": return Theme.holdAmber
        default:       return Theme.bullGreen
        }
    }

    private var urgencyLabel: String {
        switch response.urgency {
        case "high":   return "URGENT"
        case "medium": return "WATCH"
        default:       return "INFO"
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.none) {
            Rectangle()
                .fill(borderColor)
                .frame(width: 3)

            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                HStack {
                    Text("TODAY'S ACTION")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkSecondary)
                    Spacer()
                    Text(urgencyLabel)
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(borderColor)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(borderColor, lineWidth: 0.5))
                }

                Text(stripEmoji(response.action))
                    .font(.body).fontDesign(.serif).italic()
                    .foregroundStyle(Theme.inkPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .lineSpacing(3)
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.standard)
        }
        .background(Theme.canvasDeep)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(borderColor.opacity(0.3), lineWidth: 0.5))
        .cornerRadius(Theme.CornerRadius.medium)
    }
}



struct MorningDecreeCard: View {
    let briefData: MorningSummaryResponse

    private var moodColor: Color {
        switch briefData.mood {
        case "positive": return Theme.bullGreen
        case "negative": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }

    private var bulletPoints: [String] {
        // Try newline-separated bullets first (ideal format)
        let newlineBullets = briefData.summary
            .components(separatedBy: "\n")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { $0.hasPrefix("•") }
            .map { String($0.dropFirst()).trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        if !newlineBullets.isEmpty { return newlineBullets }

        // Fall back: AI returned inline "• Point 1 • Point 2 • Point 3"
        return briefData.summary
            .components(separatedBy: "•")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    private var leadSentence: String {
        if let first = bulletPoints.first {
            return stripEmoji(first)
        }
        return stripEmoji(briefData.summary)
    }

    private var remainingBullets: [String] {
        if bulletPoints.count > 1 {
            return Array(bulletPoints.dropFirst())
        }
        return []
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // SecurityThread on left edge
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        HStack {
                            Text("MORNING BRIEF")
                                .font(.caption.weight(.semibold)).monospaced()
                                .tracking(2.0)
                                .foregroundStyle(Theme.inkPrimary)
                            Spacer()
                            BanknoteSignalBadge(text: "VERIFIED", color: Theme.securityGold, rotation: -8)
                        }
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, Theme.Spacing.medium)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Lead sentence with priority pill detection
                    VStack(alignment: .leading, spacing: sectionGap) {
                        if briefData.mood == "negative" {
                            PriorityPill(label: "ALERT", color: bearRed)
                        } else if briefData.mood == "positive" {
                            PriorityPill(label: "SIGNAL", color: bullGreen)
                        } else {
                            PriorityPill(label: "INFO", color: neutralAmber)
                        }

                        Text(leadSentence)
                            .font(.subheadline.weight(.medium))
                            .foregroundStyle(.primary.opacity(0.85))
                            .fixedSize(horizontal: false, vertical: true)
                            .lineSpacing(3)
                    }
                    .padding(.horizontal, cardHPad)

                    // Fine rule separator
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                        .opacity(0.08)
                        .padding(.horizontal, cardHPad)
                        .padding(.vertical, Theme.Spacing.standard)

                    // Bullet points
                    if !remainingBullets.isEmpty {
                        VStack(alignment: .leading, spacing: rowSpacing) {
                            ForEach(remainingBullets, id: \.self) { point in
                                NiveshBulletRow(text: point)
                            }
                        }
                        .padding(.horizontal, cardHPad)
                    }

                    // Priority items
                    if let items = briefData.priorityItems, !items.isEmpty {
                        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                            .opacity(0.08)
                            .padding(.horizontal, cardHPad)
                            .padding(.top, Theme.Spacing.standard)
                            .padding(.bottom, Theme.Spacing.medium)

                        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                            Text("TODAY'S PRIORITIES")
                                .font(.caption2.weight(.semibold)).monospaced()
                                .tracking(1.5)
                                .foregroundStyle(dimText)

                            ForEach(items.prefix(5)) { item in
                                HStack(spacing: Theme.Spacing.medium) {
                                    PriorityPill(
                                        label: item.type == "alert_triggered" ? "ALERT" : "SIGNAL",
                                        color: item.type == "alert_triggered" ? bearRed : goldAccent
                                    )
                                    Text(stripEmoji(item.message))
                                        .font(.caption)
                                        .foregroundStyle(.primary.opacity(0.70))
                                        .lineLimit(2)
                                }
                            }
                        }
                        .padding(.horizontal, cardHPad)
                    }

                    // Timestamp footer
                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)

                    HStack {
                        Text("Updated \(briefData.generatedAt)")
                            .font(.caption2)
                            .foregroundStyle(subtleText)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(subtleText)
                    }
                    .padding(.horizontal, cardHPad)
                    .padding(.bottom, cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

/// Screen D 12.5 — sector capsule pill ("Auto +1.80%").
struct SectorPill: View {
    let name: String
    let change: Double
    var body: some View {
        let up = change >= 0
        Text(name + " " + IndianFormatter.percent(change))
            .font(Theme.serialNumberFont(size: 11, relativeTo: .footnote))
            .foregroundStyle(up ? Theme.bullGreen : Theme.bearRed)
            .padding(.horizontal, Theme.Spacing.card - 4)
            .padding(.vertical, Theme.Spacing.tight)
            .background((up ? Theme.bullGreen : Theme.bearRed).opacity(0.12))
            .clipShape(Capsule())
    }
}

// MARK: - Timeframe Conflicts Banner

struct TimeframeConflictsBanner: View {
    let conflicts: [TimeframeConflict]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("TIMING INSIGHTS")
                .font(Theme.sectionCapsLabel())
                .tracking(1.5)
                .foregroundStyle(Theme.securityGold)
                .padding(.horizontal, Theme.screenPadding)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(conflicts) { conflict in
                        NavigationLink(value: conflict.ticker) {
                            TimeframeConflictCard(conflict: conflict)
                        }
                        .buttonStyle(.plain)
                        .ekPressHaptic()
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
            .scrollIndicators(.hidden)
        }
    }
}

private struct TimeframeConflictCard: View {
    let conflict: TimeframeConflict

    var isBottomFishing: Bool { conflict.conflictType == "BUY_THE_DIP" }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack {
                Text(conflict.ticker)
                    .font(Theme.monoTabular(size: 15, relativeTo: .subheadline).weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Text(isBottomFishing ? "BUY THE DIP" : "TAKE PROFITS")
                    .font(Theme.microLabel(size: 10).weight(.bold))
                    .foregroundStyle(Theme.onStatus)
                    .padding(.horizontal, Theme.Spacing.tight).padding(.vertical, Theme.Spacing.xSmall)
                    .background(isBottomFishing ? Theme.signalEmerald : Theme.signalRuby)
                    .cornerRadius(3)
            }

            if let hint = conflict.actionHint {
                Text(stripEmoji(hint))
                    .font(.caption).fontDesign(.serif).italic()
                    .foregroundStyle(Theme.inkSecondary)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(Theme.Spacing.medium)
        .frame(width: UIScreen.main.bounds.width * 0.42)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).stroke(Theme.borderFine, lineWidth: 0.5))
    }
}

struct DashboardLoadingCard: View {
    let label: String
    var isLoading: Bool = true
    var body: some View {
        HStack {
            if isLoading {
                ProgressView().tint(Theme.securityGold)
                Text("Loading \(label)…")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.inkTertiary)
            } else {
                Text("\(label) unavailable")
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.medium)
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Market Pulse Dashboard Card

struct MarketPulseDashCard: View {
    let pulse: MarketPulseResponse

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // SecurityThread on left
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("बाजार की नब्ज")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MARKET PULSE")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, Theme.Spacing.medium)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // A/D Breadth Bar
                    if pulse.advances + pulse.declines > 0 {
                        ADBreathBar(advancing: pulse.advances, declining: pulse.declines)
                            .padding(.horizontal, cardHPad)
                        if let sampleSize = pulse.breadthSampleSize {
                            Text("Sample of \(sampleSize) large caps")
                                .font(.caption2).monospaced()
                                .foregroundStyle(Theme.inkTertiary)
                                .padding(.horizontal, cardHPad)
                                .padding(.top, Theme.Spacing.small)
                        }
                    }

                    // Fine rule
                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                        .padding(.horizontal, cardHPad)
                        .padding(.vertical, Theme.Spacing.standard)

                    // Index rows
                    VStack(spacing: Theme.Spacing.none) {
                        ForEach(pulse.indices.prefix(4)) { idx in
                            let valueStr: String = {
                                if idx.name.lowercased().contains("usd") || idx.name.lowercased().contains("inr") {
                                    return idx.value
                                }
                                return idx.value
                            }()
                            let changeVal: Double = {
                                if idx.changePct.contains("%") {
                                    return Double(idx.changePct.replacingOccurrences(of: "%", with: "")) ?? 0
                                }
                                return Double(idx.changePct) ?? 0
                            }()

                            IndexRow(
                                name: idx.name,
                                value: valueStr,
                                change: changeVal
                            )

                            if idx.id != pulse.indices.prefix(4).last?.id {
                                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                            }
                        }
                    }
                    .padding(.horizontal, cardHPad)
                    .padding(.bottom, cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Momentum Dashboard Card

struct MomentumDashCard: View {
    let momentum: MomentumResponse

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("गति विश्लेषण")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MOMENTUM SCAN")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, Theme.Spacing.medium)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Bullish section
                    if !momentum.bullish.isEmpty {
                        MomentumSectionView(
                            stance: "BULLISH",
                            stocks: Array(momentum.bullish.prefix(3))
                        )
                        .padding(.horizontal, cardHPad)
                    }

                    if !momentum.bullish.isEmpty && !momentum.bearish.isEmpty {
                        Spacer().frame(height: Theme.Spacing.standard)
                    }

                    // Bearish section
                    if !momentum.bearish.isEmpty {
                        MomentumSectionView(
                            stance: "BEARISH",
                            stocks: Array(momentum.bearish.prefix(3))
                        )
                        .padding(.horizontal, cardHPad)
                    }

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - Macro Dashboard Card

struct MacroDashCard: View {
    let macro: MacroAlternativesResponse

    private let macroGroups: [(title: String, keys: [String])] = [
        ("COMMODITIES & FOREX", ["Brent Crude", "Gold", "Silver", "USD/INR"]),
        ("RATES & VOLATILITY", ["US 10Y Yield", "India VIX"]),
        ("INDIA INSTRUMENTS", ["Nifty BeES", "Gold BeES", "Nifty IT", "Nifty Pharma"]),
    ]

    private func itemsForGroup(_ keys: [String]) -> [MacroItem] {
        macro.items.filter { item in
            keys.contains { key in
                item.name.localizedCaseInsensitiveContains(key)
            }
        }
    }

    private var ungroupedItems: [MacroItem] {
        let allGrouped = macroGroups.flatMap { itemsForGroup($0.keys) }
        return macro.items.filter { item in
            !allGrouped.contains { $0.id == item.id }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("वृहद अर्थव्यवस्था")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("MACRO & ALTERNATIVES")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, Theme.Spacing.medium)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    // Grouped sections
                    VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                        ForEach(macroGroups, id: \.title) { group in
                            let items = itemsForGroup(group.keys)
                            if !items.isEmpty {
                                MacroGroupView(groupTitle: group.title, rows: items)

                                if group.title != macroGroups.last?.title || !ungroupedItems.isEmpty {
                                    Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                                        .padding(.vertical, Theme.Spacing.small)
                                }
                            }
                        }

                        // Ungrouped items
                        if !ungroupedItems.isEmpty {
                            MacroGroupView(groupTitle: "OTHER", rows: ungroupedItems)
                        }
                    }
                    .padding(.horizontal, cardHPad)

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}

// MARK: - 14.4 Market Mood Gauge (Advance/Decline horizontal bar)

struct MarketMoodGauge: View {
    /// advances / (advances + declines), range 0…1
    let ratio: Double

    private var moodLabel: String {
        switch ratio {
        case 0..<0.35: return "EXTREME FEAR"
        case 0.35..<0.45: return "FEAR"
        case 0.45..<0.55: return "NEUTRAL"
        case 0.55..<0.65: return "GREED"
        default: return "EXTREME GREED"
        }
    }

    private var needleColor: Color {
        switch ratio {
        case 0..<0.45: return Theme.bearRed
        case 0.45..<0.55: return Theme.holdAmber
        default: return Theme.bullGreen
        }
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text("MARKET MOOD")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(2)
                .foregroundStyle(Theme.inkSecondary)

            // Linear Horizontal Gauge instead of Radial
            VStack(spacing: Theme.Spacing.small) {
                HStack(spacing: 0) {
                    Rectangle().fill(Theme.bearRed).frame(height: 12)
                    Rectangle().fill(Theme.holdAmber).frame(height: 12)
                    Rectangle().fill(Theme.bullGreen).frame(height: 12)
                }
                .clipShape(Capsule())
                .overlay(
                    GeometryReader { geo in
                        let xPos = geo.size.width * CGFloat(ratio)
                        Rectangle()
                            .fill(Theme.inkPrimary)
                            .frame(width: 4, height: 20)
                            .position(x: xPos, y: geo.size.height / 2)
                    }
                )
                .frame(height: 20)
            }
            .padding(.horizontal, Theme.screenPadding)

            VStack(spacing: Theme.Spacing.xSmall) {
                Text(moodLabel)
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .footnote))
                    .foregroundStyle(needleColor)
                Text(String(format: "A/D Ratio: %.2f", ratio))
                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.standard)
        .banknoteCard()
    }
}


// MARK: - 14.4 IndexCardView (snapping horizontal index chip)

struct IndexCardView: View {
    let index: LiveMarketIndex

    private var valueStr: String {
        index.ticker == "USDINR=X"
            ? IndianFormatter.price(index.value)
            : IndianFormatter.points(index.value)
    }
    private var isPositive: Bool { index.changePct >= 0 }
    private var changeStr: String {
        (isPositive ? "+" : "") + String(format: "%.2f%%", index.changePct)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(index.name)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(Theme.inkSecondary)
                .lineLimit(1)

            Text(valueStr)
                .contentTransition(.numericText())
                .font(.headline.weight(.bold)).monospaced()
                .foregroundStyle(Theme.inkPrimary)
                .monospacedDigit()

            HStack(spacing: Theme.Spacing.small) {
                Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
                Text(changeStr)
                    .contentTransition(.numericText())
                    .sensoryFeedback(trigger: index.changePct) { _, _ in
                        HapticManager.isEnabled() ? (isPositive ? SensoryFeedback.increase : SensoryFeedback.decrease) : nil
                    }
                    .font(.caption.weight(.bold)).monospaced()
                    .foregroundStyle(isPositive ? Theme.bullGreen : Theme.bearRed)
            }
        }
        .padding(Theme.Spacing.standard)
        .frame(width: UIScreen.main.bounds.width * 0.32)
        .banknoteCard()
    }
}

// MARK: - 14.4 MomentumRowView (backed by Swift Charts sparkline)

struct MomentumRowView: View {
    let ticker: MomentumTicker
    let isBullish: Bool

    private var signalColor: Color { isBullish ? Theme.bullGreen : Theme.bearRed }
    private var crossoverLabel: String {
        switch ticker.crossover {
        case "golden_cross": return "Golden Cross"
        case "death_cross": return "Death Cross"
        default: return isBullish ? "Above MA50" : "Below MA50"
        }
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                HStack(spacing: Theme.Spacing.tight) {
                    Text(ticker.ticker)
                        .font(.footnote.weight(.bold)).monospaced()
                        .foregroundStyle(Theme.inkPrimary)
                    Text(crossoverLabel.uppercased())
                        .font(.caption2.weight(.bold)).monospaced()
                        .tracking(0.8)
                        .foregroundStyle(signalColor)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(signalColor.opacity(0.10))
                        .cornerRadius(3)
                }
                HStack(spacing: Theme.Spacing.standard) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("LTP").font(.caption2).foregroundStyle(Theme.inkTertiary)
                        Text(IndianFormatter.price(ticker.lastPrice))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(.caption.weight(.semibold)).monospaced()
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("SINCE").font(.caption2).foregroundStyle(Theme.inkTertiary)
                        Text(ticker.trendDate)
                            .font(.caption2).monospaced()
                            .foregroundStyle(Theme.inkSecondary)
                    }
                }
            }
            Spacer()
            // Native Swift Charts trend sparkline
            if !ticker.sparkline.isEmpty {
                SparklineView(values: ticker.sparkline, color: signalColor)
                    .frame(width: 48, height: 28)
            }
        }
        .padding(.horizontal, Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.standard)
    }
}

#Preview("IndexCardView") {
    IndexCardView(index: LiveMarketIndex(
        name: "NIFTY 50", ticker: "^NSEI",
        value: 22_547.85, changePct: 0.43, changeAbs: 96.5
    ))
    .padding()
    .background(Theme.canvas)
}

#Preview("MarketMoodGauge") {
    MarketMoodGauge(ratio: 0.62)
        .padding()
        .background(Theme.canvas)
}

#Preview("MomentumRowView") {
    MomentumRowView(
        ticker: MomentumTicker(
            ticker: "RELIANCE", lastPrice: 2847.5, ma20: 2780.0,
            ma50: 2650.0, sparkline: [2600, 2640, 2680, 2720, 2780, 2820, 2847],
            trendDate: "12 May 2026", crossover: "golden_cross"
        ),
        isBullish: true
    )
    .padding()
    .background(Theme.canvas)
}

// MARK: - Institutional Flow Dashboard Card

struct InstitutionalDashCard: View {
    let flow: InstitutionalFlowResponse

    private var maxAbsReturn: Double {
        flow.funds.prefix(6).map { abs($0.oneYearReturnPct) }.max() ?? 1.0
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            HStack(alignment: .top, spacing: Theme.Spacing.none) {
                SecurityThread()

                VStack(alignment: .leading, spacing: Theme.Spacing.none) {
                    // Header
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("संस्थागत प्रवाह")
                            .font(.caption2)
                            .foregroundStyle(Theme.inkSecondary)
                        Text("INSTITUTIONAL ALLOCATION")
                            .font(.caption.weight(.semibold)).monospaced()
                            .tracking(2.0)
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .padding(.top, cardVPad)
                    .padding(.leading, Theme.Spacing.medium)
                    .padding(.trailing, cardHPad)

                    GuillocheDivider()
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.top, Theme.Spacing.tight)
                        .padding(.bottom, Theme.Spacing.standard)

                    Text("TOP PERFORMING MUTUAL FUNDS — 1Y RETURN")
                        .font(.caption2.weight(.semibold)).monospaced()
                        .tracking(1.5)
                        .foregroundStyle(dimText)
                        .padding(.horizontal, cardHPad)
                        .padding(.bottom, Theme.Spacing.standard)

                    if flow.funds.isEmpty {
                        Text("Fund data unavailable")
                            .font(.caption)
                            .foregroundStyle(dimText)
                            .padding(.horizontal, cardHPad)
                    }

                    // Fund rows
                    VStack(spacing: Theme.Spacing.none) {
                        ForEach(Array(flow.funds.prefix(6).enumerated()), id: \.offset) { i, fund in
                            FundReturnRow(
                                rank: i + 1,
                                fundName: fund.name,
                                returnPercent: fund.oneYearReturnPct,
                                maxAbsReturn: maxAbsReturn
                            )

                            if i < min(flow.funds.count, 6) - 1 {
                                Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
                            }
                        }
                    }
                    .padding(.horizontal, cardHPad)

                    Spacer().frame(height: cardVPad)
                }
            }
        }
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderFine, lineWidth: 0.5)
        )
    }
}
