import Combine
import SwiftUI

// MARK: - Risk Signals Tab

struct StockRiskSignalsView: View {
    let ticker: String
    @ObservedObject var vm: StockProfileViewModel

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.card) {
                if vm.overviewLoading {
                    SPSkeletonBlock(rows: 4)
                    SPSkeletonBlock(rows: 3)
                } else if let info = vm.quickInfo {
                    RiskScoreHeaderView(info: info)
                    RiskSignalCardsView(info: info)
                    GuillocheDivider()
                    RiskGovernanceSectionView(info: info)
                    GuillocheDivider()
                    RiskPledgeSectionView(info: info)
                    GuillocheDivider()
                    RiskFiiDiiSectionView(info: info)
                    GuillocheDivider()
                    RiskDebtSectionView(info: info)
                } else {
                    SPEmptyStateView(message: "Risk data unavailable")
                }
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.card)
        }
        .task { await vm.fetchOverview() }
        .task { await vm.fetchFinancials() }
    }
}

// MARK: - Risk Score Computation

private enum RiskScoreCalculator {
    /// Compute overall risk score 0–100 from available QuickInfo data.
    /// Higher = more risk. Graded: 0–29=LOW, 30–59=MODERATE, 60–79=HIGH, 80–100=CRITICAL.
    static func compute(using info: QuickInfo) -> Int {
        var score = 0

        // Governance score (0–100, inverted)
        if let gs = info.governanceScore {
            if gs < 30 { score += 25 }
            else if gs < 50 { score += 15 }
            else if gs < 70 { score += 5 }
        }

        // Governance red flags
        if let flags = info.governanceRedFlags, !flags.isEmpty {
            score += min(flags.count * 5, 20)
        }

        // Surveillance status
        if let status = info.asmGsmStatus?.uppercased() {
            if status == "GSM" { score += 20 }
            else if status == "ASM" { score += 10 }
        }

        // Promoter pledged
        if let pledged = info.promoterPledgedPct {
            if pledged >= 50 { score += 30 }
            else if pledged >= 30 { score += 20 }
            else if pledged >= 20 { score += 10 }
        }

        // Debt/Equity
        if let dte = info.debtToEquity {
            if dte > 3 { score += 20 }
            else if dte > 2 { score += 15 }
            else if dte > 1 { score += 8 }
        }

        // Promoter holding (low promoter stake = weak alignment)
        if let promoter = info.promoterHoldingPct {
            if promoter < 15 { score += 12 }
            else if promoter < 25 { score += 6 }
        }

        // Market signal risk
        if let signal = info.signal {
            switch signal {
            case .bearish: score += 15
            case .cautiously_bearish: score += 8
            case .neutral, .hold: score += 0
            case .bullish, .cautiously_bullish: score -= 5
            }
        }

        // PE ratio extremes (negative PE = loss-making)
        if let pe = info.peRatio {
            if pe < 0 { score += 15 }
            else if pe > 100 { score += 8 }
        }

        return max(0, min(100, score))
    }

    static func level(for score: Int) -> RiskLevel {
        switch score {
        case 0..<30: return .low
        case 30..<60: return .moderate
        case 60..<80: return .high
        default: return .critical
        }
    }

    enum RiskLevel: String {
        case low = "LOW"
        case moderate = "MODERATE"
        case high = "HIGH"
        case critical = "CRITICAL"

        var color: Color {
            switch self {
            case .low: return Theme.bullGreen
            case .moderate: return Theme.holdAmber
            case .high: return Theme.bearRed
            case .critical: return Theme.bearRed
            }
        }

        var labelColor: Color {
            switch self {
            case .low: return Theme.bullGreen
            case .moderate: return Theme.holdAmber
            case .high: return Theme.bearRed
            case .critical: return Theme.bearRed
            }
        }
    }
}

// MARK: - 1. Risk Score Header (Speedometer Gauge)

struct RiskScoreHeaderView: View {
    let info: QuickInfo

    private var riskScore: Int { RiskScoreCalculator.compute(using: info) }
    private var riskLevel: RiskScoreCalculator.RiskLevel { RiskScoreCalculator.level(for: riskScore) }

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            // Label
            Text("RISK ASSESSMENT SCORE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            // Gauge
            RiskGaugeView(score: riskScore, level: riskLevel)

            // Level label
            Text(riskLevel.rawValue)
                .font(Theme.officialStampFont(size: 11))
                .tracking(2.0)
                .foregroundStyle(riskLevel.labelColor)
                .padding(.horizontal, Theme.Spacing.standard)
                .padding(.vertical, Theme.Spacing.small)
                .background(riskLevel.labelColor.opacity(0.10))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Speedometer Gauge

struct RiskGaugeView: View {
    let score: Int
    let level: RiskScoreCalculator.RiskLevel

    private let gaugeSize: CGFloat = UIScreen.main.bounds.width * 0.38
    private let startAngle: Double = 135  // bottom-left start
    private let endAngle: Double = 405    // bottom-right end (270 degree sweep)

    var body: some View {
        ZStack {
            // Background arc track with gradient segments
            GaugeTrackBackground(startAngle: startAngle, endAngle: endAngle, lineWidth: 14, size: gaugeSize)

            // Filled arc
            GaugeFillArc(score: score, startAngle: startAngle, endAngle: endAngle, lineWidth: 14, size: gaugeSize, level: level)

            // Needle
            GaugeNeedle(score: score, startAngle: startAngle, endAngle: endAngle, size: gaugeSize, level: level)

            // Center display
            VStack(spacing: 0) {
                Text("\(score)")
                    .font(Theme.dataXL(size: 36, relativeTo: .largeTitle))
                    .foregroundStyle(level.labelColor)
                Text("/100")
                    .font(Theme.microLabel(size: 9))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(width: gaugeSize, height: gaugeSize * 0.72)
    }
}

// MARK: - Gauge Track Background

private struct GaugeTrackBackground: View {
    let startAngle: Double
    let endAngle: Double
    let lineWidth: CGFloat
    let size: CGFloat

    var body: some View {
        Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height * 0.85)
            let radius = min(canvasSize.width, canvasSize.height) * 0.78

            // Segment colors: green → amber → red → deep red
            let segments: [(Color, Double, Double)] = [
                (Theme.bullGreen.opacity(0.18), startAngle, startAngle + 67.5),       // green zone
                (Theme.holdAmber.opacity(0.18), startAngle + 67.5, startAngle + 135),   // amber zone
                (Theme.bearRed.opacity(0.18), startAngle + 135, startAngle + 202.5),  // red zone
                (Theme.bearRed.opacity(0.22), startAngle + 202.5, endAngle),          // deep red zone
            ]

            for (color, from, to) in segments {
                var path = Path()
                path.addArc(center: center, radius: radius, startAngle: .degrees(from), endAngle: .degrees(to), clockwise: false)
                context.stroke(path, with: .color(color), style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
            }
        }
    }
}

// MARK: - Gauge Fill Arc

private struct GaugeFillArc: View {
    let score: Int
    let startAngle: Double
    let endAngle: Double
    let lineWidth: CGFloat
    let size: CGFloat
    let level: RiskScoreCalculator.RiskLevel

    var body: some View {
        let progress = Double(score) / 100.0
        let sweep = endAngle - startAngle
        let fillTo = startAngle + sweep * progress

        Canvas { context, canvasSize in
            let center = CGPoint(x: canvasSize.width / 2, y: canvasSize.height * 0.85)
            let radius = min(canvasSize.width, canvasSize.height) * 0.78

            var path = Path()
            path.addArc(center: center, radius: radius, startAngle: .degrees(startAngle), endAngle: .degrees(fillTo), clockwise: false)
            context.stroke(path, with: .color(level.labelColor), style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
        }
        .animation(.easeOut(duration: 1.2), value: score)
    }
}

// MARK: - Gauge Needle

private struct GaugeNeedle: View {
    let score: Int
    let startAngle: Double
    let endAngle: Double
    let size: CGFloat
    let level: RiskScoreCalculator.RiskLevel

    var body: some View {
        let progress = Double(score) / 100.0
        let sweep = endAngle - startAngle
        let needleAngle = startAngle + sweep * progress
        let radius = min(size, size * 0.72) * 0.78
        let centerX = size / 2
        let centerY = size * 0.72 * 0.85

        Canvas { context, canvasSize in
            let center = CGPoint(x: centerX, y: centerY)
            let angleRad = (needleAngle - 90) * .pi / 180
            let needleLength = radius * 0.65
            let endPoint = CGPoint(
                x: center.x + cos(angleRad) * needleLength,
                y: center.y + sin(angleRad) * needleLength
            )

            // Needle shaft
            var needlePath = Path()
            needlePath.move(to: center)
            needlePath.addLine(to: endPoint)
            context.stroke(needlePath, with: .color(level.labelColor), style: StrokeStyle(lineWidth: 3, lineCap: .round))

            // Needle base circle
            let baseCircle = Path(ellipseIn: CGRect(x: center.x - 5, y: center.y - 5, width: 10, height: 10))
            context.fill(baseCircle, with: .color(level.labelColor))
        }
        .animation(.easeOut(duration: 1.0), value: score)
    }
}

// MARK: - 2. Risk Signal Cards

struct RiskSignalCardsView: View {
    let info: QuickInfo

    private var signals: [RiskSignalCard] {
        buildSignals(from: info)
    }

    var body: some View {
        if signals.isEmpty {
            RiskEmptySignalsView()
        } else {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                Text("ACTIVE RISK SIGNALS")
                    .font(Theme.officialStampFont(size: 9))
                    .tracking(1.5)
                    .foregroundStyle(Theme.inkTertiary)

                ForEach(signals, id: \.id) { signal in
                    RiskSignalCardView(signal: signal)
                }
            }
        }
    }

    private func buildSignals(from info: QuickInfo) -> [RiskSignalCard] {
        var signals: [RiskSignalCard] = []

        // Governance score check
        if let gs = info.governanceScore {
            if gs < 30 {
                signals.append(RiskSignalCard(
                    severity: .critical,
                    title: "Governance Score Critical",
                    description: "AI governance assessment scores only \(gs)/100, indicating severe corporate governance deficiencies.",
                    metricLabel: "Score",
                    metricValue: "\(gs)/100",
                    threshold: "Threshold: 70",
                    date: nil
                ))
            } else if gs < 50 {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "Governance Score Weak",
                    description: "Governance score of \(gs)/100 suggests significant oversight gaps. Monitor for improvements.",
                    metricLabel: "Score",
                    metricValue: "\(gs)/100",
                    threshold: "Threshold: 70",
                    date: nil
                ))
            } else if gs < 70 {
                signals.append(RiskSignalCard(
                    severity: .medium,
                    title: "Governance Score Moderate",
                    description: "Governance score of \(gs)/100 has room for improvement. Review flagged issues for details.",
                    metricLabel: "Score",
                    metricValue: "\(gs)/100",
                    threshold: "Threshold: 70",
                    date: nil
                ))
            }
        }

        // Governance red flags
        if let flags = info.governanceRedFlags {
            for flag in flags {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "Governance Red Flag",
                    description: flag,
                    metricLabel: nil,
                    metricValue: nil,
                    threshold: nil,
                    date: nil
                ))
            }
        }

        // Surveillance
        if let status = info.asmGsmStatus?.uppercased() {
            if status == "GSM" {
                signals.append(RiskSignalCard(
                    severity: .critical,
                    title: "GSM Surveillance Active",
                    description: "Stock is under Graded Surveillance Measure. Trading restricted to delivery-only with no intraday permitted.",
                    metricLabel: "Status",
                    metricValue: "GSM",
                    threshold: nil,
                    date: nil
                ))
            } else if status == "ASM" {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "ASM Surveillance Active",
                    description: "Stock is under Additional Surveillance Measures with higher margins. Monitor for potential GSM escalation.",
                    metricLabel: "Status",
                    metricValue: "ASM",
                    threshold: nil,
                    date: nil
                ))
            }
        }

        // Pledge risk
        if let pledged = info.promoterPledgedPct {
            if pledged >= 50 {
                signals.append(RiskSignalCard(
                    severity: .critical,
                    title: "Extreme Promoter Pledging",
                    description: "\(String(format: "%.1f", pledged))% of promoter holding is pledged — severe margin-call cascade risk exists.",
                    metricLabel: "Pledged",
                    metricValue: "\(String(format: "%.1f", pledged))%",
                    threshold: "Threshold: 20%",
                    date: nil
                ))
            } else if pledged >= 30 {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "High Promoter Pledging",
                    description: "\(String(format: "%.1f", pledged))% of promoter holding pledged. Elevated risk of forced sell-off in market downturns.",
                    metricLabel: "Pledged",
                    metricValue: "\(String(format: "%.1f", pledged))%",
                    threshold: "Threshold: 20%",
                    date: nil
                ))
            } else if pledged >= 20 {
                signals.append(RiskSignalCard(
                    severity: .medium,
                    title: "Moderate Promoter Pledging",
                    description: "\(String(format: "%.1f", pledged))% of promoter holding pledged. Within elevated range — monitor quarterly.",
                    metricLabel: "Pledged",
                    metricValue: "\(String(format: "%.1f", pledged))%",
                    threshold: "Threshold: 20%",
                    date: nil
                ))
            }
        }

        // Debt concern
        if let dte = info.debtToEquity {
            if dte > 3 {
                signals.append(RiskSignalCard(
                    severity: .critical,
                    title: "Severe Debt Load",
                    description: "Debt/Equity ratio of \(String(format: "%.2f", dte))x far exceeds safe thresholds. Interest burden may strain earnings.",
                    metricLabel: "D/E Ratio",
                    metricValue: String(format: "%.2f", dte),
                    threshold: "Safe: < 1.0",
                    date: nil
                ))
            } else if dte > 2 {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "High Debt Concern",
                    description: "Debt/Equity ratio of \(String(format: "%.2f", dte))x signals elevated leverage. Review interest coverage and free cash flow.",
                    metricLabel: "D/E Ratio",
                    metricValue: String(format: "%.2f", dte),
                    threshold: "Safe: < 1.0",
                    date: nil
                ))
            } else if dte > 1 {
                signals.append(RiskSignalCard(
                    severity: .medium,
                    title: "Elevated Debt Levels",
                    description: "Debt/Equity ratio of \(String(format: "%.2f", dte))x is above conservative thresholds. Keep on watch for increasing trend.",
                    metricLabel: "D/E Ratio",
                    metricValue: String(format: "%.2f", dte),
                    threshold: "Safe: < 1.0",
                    date: nil
                ))
            }
        }

        // Low promoter holding
        if let promoter = info.promoterHoldingPct {
            if promoter < 15 {
                signals.append(RiskSignalCard(
                    severity: .high,
                    title: "Very Low Promoter Stake",
                    description: "Promoter holding is only \(String(format: "%.1f", promoter))% — weak alignment with minority shareholders.",
                    metricLabel: "Promoter",
                    metricValue: "\(String(format: "%.1f", promoter))%",
                    threshold: "Min: 25%",
                    date: nil
                ))
            } else if promoter < 25 {
                signals.append(RiskSignalCard(
                    severity: .medium,
                    title: "Low Promoter Stake",
                    description: "Promoter holding at \(String(format: "%.1f", promoter))% is below 25% — limited skin in the game.",
                    metricLabel: "Promoter",
                    metricValue: "\(String(format: "%.1f", promoter))%",
                    threshold: "Min: 25%",
                    date: nil
                ))
            }
        }

        // Bearish signal
        if let signal = info.signal, signal == .bearish || signal == .cautiously_bearish {
            signals.append(RiskSignalCard(
                severity: signal == .bearish ? .high : .medium,
                title: signal == .bearish ? "Bearish Market Signal" : "Cautious Market Signal",
                description: "Multi-agent AI analysis classifies this stock as \(signal.rawValue). Review the full analysis for detailed rationale.",
                metricLabel: "Signal",
                metricValue: signal.rawValue,
                threshold: nil,
                date: nil
            ))
        }

        // Negative PE
        if let pe = info.peRatio, pe < 0 {
            signals.append(RiskSignalCard(
                severity: .high,
                title: "Negative Earnings",
                description: "PE ratio is negative — the company is currently loss-making. Recovery timeline is uncertain.",
                metricLabel: "PE Ratio",
                metricValue: "Negative",
                threshold: nil,
                date: nil
            ))
        }

        return signals
    }
}

// MARK: - Risk Signal Data Model

private struct RiskSignalCard {
    let id = UUID()
    let severity: RiskSeverity
    let title: String
    let description: String
    let metricLabel: String?
    let metricValue: String?
    let threshold: String?
    let date: String?

    enum RiskSeverity: String {
        case low = "LOW"
        case medium = "MEDIUM"
        case high = "HIGH"
        case critical = "CRITICAL"

        var color: Color {
            switch self {
            case .low: return Theme.bullGreen
            case .medium: return Theme.holdAmber
            case .high: return Theme.bearRed
            case .critical: return Theme.bearRed
            }
        }

        var bgColor: Color {
            color.opacity(0.08)
        }
    }
}

// MARK: - Risk Signal Card

struct RiskSignalCardView: View {
    let signal: RiskSignalCard

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Severity badge + title
            HStack(spacing: Theme.Spacing.medium) {
                Text(signal.severity.rawValue)
                    .font(Theme.officialStampFont(size: 8))
                    .tracking(1.2)
                    .foregroundStyle(signal.severity.color)
                    .padding(.horizontal, Theme.Spacing.medium)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(signal.severity.bgColor)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .stroke(signal.severity.color.opacity(0.35), lineWidth: 0.5)
                    )

                Text(signal.title)
                    .font(Theme.engravedSerif(size: 13, weight: .bold))
                    .foregroundStyle(Theme.inkPrimary)
                    .lineLimit(2)

                Spacer(minLength: 0)
            }

            // Description
            Text(signal.description)
                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .lineSpacing(3)
                .lineLimit(4)

            // Metric value vs threshold
            if let label = signal.metricLabel, let value = signal.metricValue {
                HStack(spacing: Theme.Spacing.tight) {
                    Text(label.uppercased())
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                        .tracking(0.8)

                    Text(value)
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                        .foregroundStyle(signal.severity.color)

                    if let threshold = signal.threshold {
                        Text("•")
                            .font(Theme.microLabel(size: 6))
                            .foregroundStyle(Theme.inkTertiary)
                        Text(threshold)
                            .font(Theme.microLabel(size: 8))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }
                .padding(.top, Theme.Spacing.xSmall)
            }

            // Detected date if available
            if let date = signal.date {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "clock")
                        .font(Theme.officialStampFont(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("Detected \(date)")
                        .font(Theme.microLabel(size: 8))
                        .foregroundStyle(Theme.inkTertiary)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .background(Theme.canvasDeep)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(signal.severity.color.opacity(0.12), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }
}

// MARK: - Empty Signals State

struct RiskEmptySignalsView: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "checkmark.shield.fill")
                .font(.largeTitle)
                .foregroundStyle(Theme.bullGreen)

            Text("No significant risk signals detected")
                .font(Theme.engravedSerif(size: 13, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)

            Text("The current data does not indicate any elevated risk factors. Continue monitoring for changes.")
                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
                .multilineTextAlignment(.center)
                .lineSpacing(2)
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.xLarge)
        .banknoteCard()
    }
}

// MARK: - 3. Governance Risk Section

struct RiskGovernanceSectionView: View {
    let info: QuickInfo

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("GOVERNANCE HEALTH")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if let score = info.governanceScore {
                // Governance score gauge
                HStack(spacing: Theme.Spacing.card) {
                    // Mini gauge
                    GovernanceMiniGaugeView(score: score)

                    // Score interpretation
                    VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                        Text(governanceLabel(for: score))
                            .font(Theme.engravedSerif(size: 14, weight: .bold))
                            .foregroundStyle(governanceColor(for: score))

                        Text("Based on multi-agent AI analysis of corporate filings, promoter activity, and regulatory compliance data.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineLimit(3)
                            .lineSpacing(2)
                    }
                    Spacer(minLength: 0)
                }

                // Warning for very low governance
                if score < 50 {
                    HStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(Theme.engravedSerif(size: 13))
                            .foregroundStyle(Theme.bearRed)

                        Text("Governance score below 50 — significant risk of value destruction from poor oversight, related-party transactions, or regulatory issues.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.bearRed)
                            .lineSpacing(2)
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.bearRed.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }

                // Red flags list
                if let flags = info.governanceRedFlags, !flags.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        Text("FLAGGED CONCERNS")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.bearRed)

                        ForEach(Array(flags.enumerated()), id: \.offset) { _, flag in
                            HStack(alignment: .top, spacing: Theme.Spacing.small) {
                                Circle()
                                    .fill(Theme.bearRed)
                                    .frame(width: 5, height: 5)
                                    .padding(.top, 4)
                                Text(flag)
                                    .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                                    .foregroundStyle(Theme.inkPrimary)
                                    .lineSpacing(2)
                            }
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .background(Theme.bearRed.opacity(0.04))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                            .stroke(Theme.bearRed.opacity(0.15), lineWidth: 0.5)
                    )
                }

                // Surveillance status
                if let status = info.asmGsmStatus?.uppercased(), status != "UNKNOWN" {
                    HStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: status == "GSM" ? "exclamationmark.triangle.fill" : "exclamationmark.shield.fill")
                            .font(Theme.engravedSerif(size: 13))
                            .foregroundStyle(status == "GSM" ? Theme.bearRed : Theme.holdAmber)

                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text("SURVEILLANCE: \(status)")
                                .font(Theme.officialStampFont(size: 8))
                                .tracking(1.0)
                                .foregroundStyle(Theme.inkTertiary)

                            Text(status == "GSM"
                                 ? "Delivery-only trading. Brokers may block settlement. No intraday permitted."
                                 : "Additional Surveillance Measures active — higher margins apply.")
                                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                .foregroundStyle(status == "GSM" ? Theme.bearRed : Theme.holdAmber)
                                .lineSpacing(2)
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .background(status == "GSM" ? Theme.bearRed.opacity(0.07) : Theme.holdAmber.opacity(0.07))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func governanceColor(for score: Int) -> Color {
        switch score {
        case 70...100: return Theme.bullGreen
        case 40..<70: return Theme.holdAmber
        default: return Theme.bearRed
        }
    }

    private func governanceLabel(for score: Int) -> String {
        switch score {
        case 80...100: return "Strong Governance"
        case 60..<80: return "Satisfactory"
        case 40..<60: return "Moderate Concerns"
        case 20..<40: return "Weak Governance"
        default: return "Governance FAIL"
        }
    }
}

// MARK: - Mini Governance Gauge

struct GovernanceMiniGaugeView: View {
    let score: Int
    private let gaugeSize: CGFloat = UIScreen.main.bounds.width * 0.20

    private var color: Color {
        switch score {
        case 70...100: return Theme.bullGreen
        case 40..<70: return Theme.holdAmber
        default: return Theme.bearRed
        }
    }

    var body: some View {
        ZStack {
            Circle()
                .stroke(Theme.inkTertiary.opacity(0.12), lineWidth: 6)
                .frame(width: gaugeSize, height: gaugeSize)

            Circle()
                .trim(from: 0, to: CGFloat(score) / 100.0)
                .stroke(color, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                .frame(width: gaugeSize, height: gaugeSize)
                .rotationEffect(.degrees(-90))
                .animation(.easeOut(duration: 1.0), value: score)

            VStack(spacing: 0) {
                Text("\(score)")
                    .font(Theme.serialNumberFont(size: 18, relativeTo: .title3))
                    .foregroundStyle(Theme.inkPrimary)
                Text("/100")
                    .font(Theme.microLabel(size: 7))
                    .foregroundStyle(Theme.inkTertiary)
            }
        }
        .frame(width: gaugeSize, height: gaugeSize)
    }
}

// MARK: - 4. Pledge Risk Section

struct RiskPledgeSectionView: View {
    let info: QuickInfo

    private var pledgePct: Double { info.promoterPledgedPct ?? 0 }
    private var promoterPct: Double { info.promoterHoldingPct ?? 0 }

    private var pledgeRiskLevel: RiskScoreCalculator.RiskLevel {
        if pledgePct >= 50 { return .critical }
        if pledgePct >= 30 { return .high }
        if pledgePct >= 20 { return .moderate }
        return .low
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("PROMOTER PLEDGE RISK")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if let _ = info.promoterPledgedPct {
                // Pledge bar and stats
                HStack(alignment: .bottom, spacing: Theme.Spacing.card) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("\(String(format: "%.1f", pledgePct))%")
                            .font(Theme.serialNumberFont(size: 30, relativeTo: .title))
                            .foregroundStyle(pledgeRiskColor)

                        Text("Pledged")
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text("\(String(format: "%.1f", promoterPct))%")
                            .font(Theme.serialNumberFont(size: 20, relativeTo: .title2))
                            .foregroundStyle(Theme.securityGold)
                        Text("Promoter Stake")
                            .font(Theme.microLabel(size: 9))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                }

                // Pledge progress bar with thresholds
                PledgeThresholdBarView(pledgePct: pledgePct)

                // Risk indicator
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: pledgeRiskIcon)
                        .font(Theme.engravedSerif(size: 13))
                        .foregroundStyle(pledgeRiskColor)

                    Text(pledgeRiskMessage)
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(pledgeRiskColor)
                        .lineSpacing(2)
                }
                .padding(Theme.Spacing.standard)
                .background(pledgeRiskColor.opacity(0.07))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))

                // Threshold warnings
                if pledgePct >= 50 {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.bearRed)
                        Text("Extreme Risk: Over 50% pledged — margin-call cascade is a real and present danger.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.bearRed)
                            .lineSpacing(2)
                    }
                } else if pledgePct >= 20 {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.holdAmber)
                        Text("Elevated Risk: Above 20% pledge threshold. Review quarterly shareholding patterns for changes.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.holdAmber)
                            .lineSpacing(2)
                    }
                }
            } else {
                // No pledge data
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(Theme.engravedSerif(size: 14))
                        .foregroundStyle(Theme.bullGreen)
                    Text("No promoter shares pledged — zero pledge risk.")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private var pledgeRiskColor: Color {
        switch pledgeRiskLevel {
        case .low: return Theme.bullGreen
        case .moderate: return Theme.holdAmber
        case .high: return Theme.bearRed
        case .critical: return Theme.bearRed
        }
    }

    private var pledgeRiskIcon: String {
        switch pledgeRiskLevel {
        case .low: return "checkmark.shield.fill"
        case .moderate, .high, .critical: return "exclamationmark.shield.fill"
        }
    }

    private var pledgeRiskMessage: String {
        if pledgePct == 0 {
            return "Pledge risk is NONE — no promoter shares are pledged."
        }
        return "Pledge risk is \(pledgeRiskLevel.rawValue) — \(String(format: "%.1f", pledgePct))% of promoter holding is pledged."
    }
}

// MARK: - Pledge Threshold Bar

struct PledgeThresholdBarView: View {
    let pledgePct: Double

    private var barWidth: CGFloat {
        UIScreen.main.bounds.width - (Theme.screenPadding * 2) - (Theme.Spacing.card * 2)
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.tight) {
            // Gradient bar
            ZStack(alignment: .leading) {
                // Track
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.08))
                    .frame(height: 10)

                // Green zone (< 20%)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bullGreen.opacity(0.18))
                    .frame(width: barWidth * 0.2, height: 10)

                // Amber zone (20–50%)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.holdAmber.opacity(0.18))
                    .frame(width: barWidth * 0.3, height: 10)
                    .offset(x: barWidth * 0.2)

                // Red zone (> 50%)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bearRed.opacity(0.15))
                    .frame(width: barWidth * 0.5, height: 10)
                    .offset(x: barWidth * 0.5)

                // Indicator
                let clamped = min(max(pledgePct, 0), 100)
                let indicatorX = barWidth * CGFloat(clamped / 100.0)

                Circle()
                    .fill(pledgeIndicatorColor)
                    .frame(width: 12, height: 12)
                    .offset(x: max(0, min(indicatorX - 6, barWidth - 12)))
            }
            .frame(height: 12)

            // Labels
            HStack {
                Text("Safe <20%")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bullGreen)
                Spacer()
                Text("Moderate 20–50%")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.holdAmber)
                Spacer()
                Text("Critical >50%")
                    .font(Theme.microLabel(size: 8))
                    .foregroundStyle(Theme.bearRed)
            }
        }
    }

    private var pledgeIndicatorColor: Color {
        if pledgePct >= 50 { return Theme.bearRed }
        if pledgePct >= 20 { return Theme.holdAmber }
        return Theme.bullGreen
    }
}

// MARK: - 5. FII / DII Trend Section

struct RiskFiiDiiSectionView: View {
    let info: QuickInfo

    private var fiiPct: Double { info.fiiHoldingPct ?? 0 }
    private var diiPct: Double { info.diiHoldingPct ?? 0 }
    private var promoterPct: Double { info.promoterHoldingPct ?? 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("FII / DII OWNERSHIP")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            // FII row
            if fiiPct > 0 || diiPct > 0 {
                HStack(spacing: Theme.Spacing.card) {
                    // FII block
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("FII")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)

                        Text("\(String(format: "%.1f", fiiPct))%")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.bullGreen)

                        // FII trend indicator (simplified — derived from holding percentage vs threshold)
                        FiiDiiTrendIndicator(holding: fiiPct, entity: "FII")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Spacing.standard)
                    .background(Theme.canvasDeep)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))

                    // DII block
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("DII")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)

                        Text("\(String(format: "%.1f", diiPct))%")
                            .font(Theme.serialNumberFont(size: 22, relativeTo: .title2))
                            .foregroundStyle(Theme.avatarBlue)

                        FiiDiiTrendIndicator(holding: diiPct, entity: "DII")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Spacing.standard)
                    .background(Theme.canvasDeep)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                }

                // Ownership summary bar
                let publicPct = max(0, 100 - promoterPct - fiiPct - diiPct)
                if promoterPct + fiiPct + diiPct > 0 {
                    VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                        Text("OWNERSHIP BREAKDOWN")
                            .font(Theme.officialStampFont(size: 8))
                            .tracking(1.0)
                            .foregroundStyle(Theme.inkTertiary)

                        OwnershipStackedBarView(
                            promoterPct: promoterPct,
                            fiiPct: fiiPct,
                            diiPct: diiPct,
                            publicPct: publicPct
                        )
                    }
                }

                // Commentary
                if fiiPct < 1 && diiPct < 1 {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.holdAmber)
                        Text("Negligible institutional ownership — no institutional confidence signal available.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.holdAmber)
                            .lineSpacing(2)
                    }
                } else if fiiPct + diiPct > 30 {
                    HStack(spacing: Theme.Spacing.small) {
                        Image(systemName: "checkmark.shield.fill")
                            .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                            .foregroundStyle(Theme.bullGreen)
                        Text("Strong institutional presence (\(String(format: "%.1f", fiiPct + diiPct))% combined) — adds governance oversight.")
                            .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkSecondary)
                            .lineSpacing(2)
                    }
                }
            } else {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "chart.bar.doc.horizontal")
                        .font(Theme.engravedSerif(size: 14))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("FII/DII data not available for this stock.")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - FII / DII Trend Indicator

struct FiiDiiTrendIndicator: View {
    let holding: Double
    let entity: String

    private var trend: String {
        // Trend heuristic: relative holding size indicates conviction level
        // In production this would use qoq change data
        if holding >= 10 { return "ACCUMULATING" }
        if holding >= 2 { return "STABLE" }
        if holding > 0 { return "MARGINAL" }
        return "NO DATA"
    }

    private var trendColor: Color {
        switch trend {
        case "ACCUMULATING": return Theme.bullGreen
        case "STABLE": return Theme.securityGold
        case "MARGINAL": return Theme.holdAmber
        default: return Theme.inkTertiary
        }
    }

    private var arrowIcon: String {
        switch trend {
        case "ACCUMULATING": return "arrow.up.right"
        case "STABLE": return "arrow.forward"
        case "MARGINAL": return "arrow.down.right"
        default: return "minus"
        }
    }

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: arrowIcon)
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(trendColor)

            Text(trend)
                .font(Theme.microLabel(size: 8))
                .foregroundStyle(trendColor)
        }
        .padding(.horizontal, Theme.Spacing.tight)
        .padding(.vertical, Theme.Spacing.xSmall)
        .background(trendColor.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
    }
}

// MARK: - Ownership Stacked Bar

struct OwnershipStackedBarView: View {
    let promoterPct: Double
    let fiiPct: Double
    let diiPct: Double
    let publicPct: Double

    private var barWidth: CGFloat {
        UIScreen.main.bounds.width - (Theme.screenPadding * 2) - (Theme.Spacing.card * 2)
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.tight) {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.08))
                    .frame(height: 6)

                HStack(spacing: 0) {
                    if promoterPct > 0 {
                        RoundedRectangle(cornerRadius: 0)
                            .fill(Theme.securityGold)
                            .frame(width: barWidth * CGFloat(promoterPct / 100.0), height: 6)
                    }
                    if fiiPct > 0 {
                        RoundedRectangle(cornerRadius: 0)
                            .fill(Theme.bullGreen)
                            .frame(width: barWidth * CGFloat(fiiPct / 100.0), height: 6)
                    }
                    if diiPct > 0 {
                        RoundedRectangle(cornerRadius: 0)
                            .fill(Theme.avatarBlue)
                            .frame(width: barWidth * CGFloat(diiPct / 100.0), height: 6)
                    }
                    if publicPct > 0 {
                        RoundedRectangle(cornerRadius: 0)
                            .fill(Theme.inkTertiary.opacity(0.15))
                            .frame(width: barWidth * CGFloat(publicPct / 100.0), height: 6)
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }

            HStack(spacing: Theme.Spacing.standard) {
                SPLegendDot(color: Theme.securityGold, label: "Promoter", value: promoterPct)
                SPLegendDot(color: Theme.bullGreen, label: "FII", value: fiiPct)
                SPLegendDot(color: Theme.avatarBlue, label: "DII", value: diiPct)
                Spacer(minLength: 0)
            }
        }
    }
}

// MARK: - 6. Debt Concern Section

struct RiskDebtSectionView: View {
    let info: QuickInfo

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("DEBT & LEVERAGE")
                .font(Theme.officialStampFont(size: 9))
                .tracking(1.5)
                .foregroundStyle(Theme.inkTertiary)

            if let dte = info.debtToEquity {
                // D/E gauge
                HStack(spacing: Theme.Spacing.card) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("Debt/Equity")
                            .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                            .foregroundStyle(Theme.inkSecondary)

                        Text(String(format: "%.2f", dte))
                            .font(Theme.serialNumberFont(size: 28, relativeTo: .title))
                            .foregroundStyle(debtColor(dte))
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text(debtLabel(dte))
                            .font(Theme.engravedSerif(size: 13, weight: .bold))
                            .foregroundStyle(debtColor(dte))

                        if let pe = info.peRatio, pe > 0 {
                            Text("PE: \(String(format: "%.1f", pe))")
                                .font(Theme.microLabel(size: 9))
                                .foregroundStyle(Theme.inkTertiary)
                        }
                    }
                }

                // D/E threshold gauge bar
                DebtGaugeBarView(dte: dte)

                // Commentary
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: debtIcon(dte))
                        .font(Theme.engravedSerif(size: 13))
                        .foregroundStyle(debtColor(dte))

                    Text(debtCommentary(dte))
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                        .foregroundStyle(debtColor(dte))
                        .lineSpacing(2)
                }
                .padding(Theme.Spacing.standard)
                .background(debtColor(dte).opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.tight))

                // Additional financial health indicators
                if let roe = info.roePct {
                    HStack(spacing: Theme.Spacing.card) {
                        RiskFinancialChipView(
                            label: "ROE",
                            value: "\(String(format: "%.1f", roe))%",
                            isHealthy: roe >= 15
                        )
                        if let roce = info.rocePct {
                            RiskFinancialChipView(
                                label: "ROCE",
                                value: "\(String(format: "%.1f", roce))%",
                                isHealthy: roce >= 15
                            )
                        }
                        RiskFinancialChipView(
                            label: "D/E",
                            value: String(format: "%.2f", dte),
                            isHealthy: dte < 1
                        )
                    }
                }
            } else {
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "chart.bar.doc.horizontal")
                        .font(Theme.engravedSerif(size: 14))
                        .foregroundStyle(Theme.inkTertiary)
                    Text("Debt data not available for this stock.")
                        .font(Theme.serialNumberFont(size: 12, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                }
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }

    private func debtColor(_ dte: Double) -> Color {
        if dte > 3 { return Theme.bearRed }
        if dte > 2 { return Theme.bearRed }
        if dte > 1 { return Theme.holdAmber }
        return Theme.bullGreen
    }

    private func debtLabel(_ dte: Double) -> String {
        if dte > 3 { return "Severe" }
        if dte > 2 { return "High" }
        if dte > 1 { return "Moderate" }
        return "Healthy"
    }

    private func debtIcon(_ dte: Double) -> String {
        dte > 2 ? "exclamationmark.triangle.fill" :
        dte > 1 ? "exclamationmark.shield.fill" :
        "checkmark.shield.fill"
    }

    private func debtCommentary(_ dte: Double) -> String {
        if dte > 3 {
            return "High debt levels — Debt/Equity of \(String(format: "%.2f", dte))x vs industry avg of ~1.0x. Interest burden may significantly strain earnings."
        } else if dte > 2 {
            return "Elevated debt — Debt/Equity of \(String(format: "%.2f", dte))x. Review interest coverage and free cash flow for sustainability."
        } else if dte > 1 {
            return "Moderate leverage — Debt/Equity of \(String(format: "%.2f", dte))x is above conservative thresholds but may be manageable with strong cash flows."
        } else {
            return "Healthy leverage — Debt/Equity of \(String(format: "%.2f", dte))x is within conservative limits."
        }
    }
}

// MARK: - Debt Gauge Bar

struct DebtGaugeBarView: View {
    let dte: Double

    private var barWidth: CGFloat {
        UIScreen.main.bounds.width - (Theme.screenPadding * 2) - (Theme.Spacing.card * 2)
    }

    var body: some View {
        VStack(spacing: Theme.Spacing.tight) {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.inkTertiary.opacity(0.08))
                    .frame(height: 8)

                // Safe zone (0-1)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bullGreen.opacity(0.2))
                    .frame(width: barWidth * 0.33, height: 8)

                // Moderate zone (1-2)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.holdAmber.opacity(0.2))
                    .frame(width: barWidth * 0.33, height: 8)
                    .offset(x: barWidth * 0.33)

                // High zone (2-3)
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill(Theme.bearRed.opacity(0.15))
                    .frame(width: barWidth * 0.34, height: 8)
                    .offset(x: barWidth * 0.66)

                // Needle
                let clampedDte = min(dte, 3.0)
                Circle()
                    .fill(debtNeedleColor)
                    .frame(width: 10, height: 10)
                    .offset(x: max(0, min(barWidth * CGFloat(clampedDte / 3.0) - 5, barWidth - 10)))
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
    }

    private var debtNeedleColor: Color {
        if dte > 2 { return Theme.bearRed }
        if dte > 1 { return Theme.holdAmber }
        return Theme.bullGreen
    }
}

// MARK: - Financial Health Chip

struct RiskFinancialChipView: View {
    let label: String
    let value: String
    let isHealthy: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            Text(label)
                .font(Theme.officialStampFont(size: 8))
                .tracking(0.8)
                .foregroundStyle(Theme.inkTertiary)
            Text(value)
                .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                .foregroundStyle(isHealthy ? Theme.bullGreen : Theme.bearRed)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, Theme.Spacing.medium)
        .padding(.horizontal, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }
}
