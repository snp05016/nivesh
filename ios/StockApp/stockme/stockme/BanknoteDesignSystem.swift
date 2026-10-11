import SwiftUI

// MARK: - Emil Kowalski Button Press Style

struct EKPressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .opacity(configuration.isPressed ? 0.88 : 1.0)
            .animation(.spring(response: 0.25, dampingFraction: 0.85), value: configuration.isPressed)
    }
}

extension View {
    func ekPress() -> some View {
        buttonStyle(EKPressStyle())
    }
}

// MARK: - Security Thread

struct SecurityThread: View {
    var body: some View { EmptyView() }
}

// MARK: - Rupee Medallion Watermark (₹ at 320pt, behind hero content)

struct RupeeWatermark: View {
    var body: some View { EmptyView() }
}

// MARK: - Corner Ornament (4 concentric offset circles, top-right of hero card)

struct CornerOrnament: View {
    var body: some View {
        ZStack {
            ForEach([20.0, 35.0, 50.0, 65.0], id: \.self) { r in
                Circle()
                    .stroke(Theme.borderSage, lineWidth: 0.5)
                    .frame(width: r * 2, height: r * 2)
                    .offset(x: r * 0.15, y: -r * 0.15)
            }
        }
        .allowsHitTesting(false)
    }
}

// MARK: - Banknote Signal Badge (replaces TellerStamp everywhere)

struct BanknoteSignalBadge: View {
    let text: String
    let tintColor: Color
    var rotation: Double = -2

    init(signal: Signal, rotation: Double = -2) {
        self.text = signal.rawValue
        self.rotation = rotation
        switch signal {
        case .bullish, .cautiously_bullish:
            self.tintColor = Theme.bullGreen
        case .bearish, .cautiously_bearish:
            self.tintColor = Theme.bearRed
        case .hold:
            self.tintColor = Theme.holdAmber
        case .neutral:
            self.tintColor = Theme.inkSecondary
        }
    }

    init(text: String, color: Color, rotation: Double = -2) {
        self.text = text.uppercased()
        self.tintColor = color
        self.rotation = rotation
    }

    var body: some View {
        Text(text.uppercased())
            .font(Theme.officialStampFont(size: 9))
            .tracking(2)
            .foregroundStyle(tintColor)
            .padding(.horizontal, Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.small)
            .background(tintColor.opacity(0.07))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .stroke(tintColor.opacity(0.4), lineWidth: 1)
            )
            .rotationEffect(.degrees(rotation))
            .cornerRadius(2)
    }
}

// MARK: - Portfolio Value Display (₹ in gold, number in inkPrimary, animated)

struct PortfolioValueDisplay: View {
    let target: Double
    let fontSize: CGFloat
    @State private var current: Double = 0

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.xSmall) {
            Text("₹")
                .font(Theme.engravedSerif(size: fontSize, weight: .bold))
                .foregroundStyle(Theme.securityGold)
            Text(IndianFormatter.priceWithoutSymbol(current))
            .lineLimit(1)
            .minimumScaleFactor(0.6)
                .contentTransition(.numericText())
                .font(Theme.serialNumberFont(size: fontSize))
                .foregroundStyle(Theme.inkPrimary)
                .monospacedDigit()
        }
        .onAppear {
            withAnimation(.easeOut(duration: 1.2)) { current = target }
        }
        .onChange(of: target) { _, newVal in
            withAnimation(.easeOut(duration: 0.6)) { current = newVal }
        }
    }
}

// MARK: - Stamp Press Animation

struct StampAppear: ViewModifier {
    @State private var isStamped = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(isStamped ? 1.0 : 1.2)
            .rotationEffect(.degrees(isStamped ? -2 : 0))
            .onAppear {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) {
                    isStamped = true
                }
            }
    }
}

extension View {
    func stampAppear() -> some View {
        modifier(StampAppear())
    }
}

// MARK: - Governor Seal Avatar (user initials in RBI-seal style circle)

struct GovernorSealAvatar: View {
    let initials: String

    private var avatarSize: CGFloat { UIScreen.main.bounds.width * 0.11 }

    var body: some View {
        ZStack {
            Circle()
                .fill(Theme.canvasDeep)
            Circle()
                .stroke(Theme.securityGold.opacity(0.5), lineWidth: 1.5)
                .frame(width: avatarSize, height: avatarSize)
            Circle()
                .stroke(Theme.securityGold.opacity(0.2), lineWidth: 0.5)
                .frame(width: avatarSize * 0.83, height: avatarSize * 0.83)
            Text(initials.uppercased())
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
        }
        .frame(width: avatarSize * 1.08, height: avatarSize * 1.08)
    }
}

// MARK: - Section Header (Phase 1 redesign)

struct SectionHeaderView: View {
    let title: String
    var actionLabel: String? = nil
    var onAction: (() -> Void)? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
            HStack {
                Text(title)
                    .font(Theme.sectionCapsLabel())
                    .tracking(1.2)
                    .foregroundStyle(Theme.inkPrimary)

                Spacer()

                if let label = actionLabel, let action = onAction {
                    Button(action: {
                        HapticManager.selection()
                        action()
                    }) {
                        Text(label)
                            .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .footnote))
                            .foregroundStyle(Theme.goldPrimary)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .padding(.horizontal, Theme.screenPadding)

            // Gold underline — 2pt × 24pt, left-aligned
            Rectangle()
                .fill(Theme.goldPrimary.opacity(0.6))
                .frame(width: 24, height: 2)
                .padding(.leading, Theme.screenPadding)
        }
    }
}

// MARK: - Index Chip (Phase 1 redesign)

struct IndexChipView: View {
    let abbreviation: String
    let value: String
    let changePercent: Double
    var onTap: (() -> Void)? = nil

    private var changeColor: Color {
        changePercent >= 0 ? Theme.dataPositive : Theme.dataNegative
    }

    private var changeText: String {
        let sign = changePercent >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.2f", changePercent))%"
    }

    var body: some View {
        Button(action: {
            HapticManager.selection()
            onTap?()
        }) {
            HStack(spacing: Theme.Spacing.tight) {
                Text(abbreviation)
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote).weight(.bold))
                    .foregroundStyle(Theme.inkPrimary)

                Text(value)
                    .font(Theme.monoTabular(size: 12, relativeTo: .caption))
                    .foregroundStyle(Theme.inkSecondary)

                Text(changeText)
                    .font(Theme.monoTabular(size: 11, relativeTo: .caption2))
                    .foregroundStyle(changeColor)
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(changeColor.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }
            .padding(.horizontal, Theme.Spacing.standard)
            .padding(.vertical, Theme.Spacing.medium)
            .background(Theme.surfaceElevated)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.pill)
                    .stroke(Theme.goldMuted.opacity(0.6), lineWidth: 0.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
        }
        .buttonStyle(EKPressStyle())
    }
}

// MARK: - P&L Badge (Phase 1 redesign)

struct PnlBadge: View {
    let value: Double
    var showPercentage: Bool = true

    private var isPositive: Bool { value >= 0 }
    private var color: Color { isPositive ? Theme.dataPositive : Theme.dataNegative }
    private var bgColor: Color { isPositive ? Theme.dataPositiveMuted : Theme.dataNegativeMuted }
    private var prefix: String { isPositive ? "▲" : "▼" }

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Text(prefix)
                .font(Theme.monoTabular(size: 11, relativeTo: .caption2))
                .foregroundStyle(color)

            if showPercentage {
                Text("\(String(format: "%.2f", abs(value)))%")
                    .font(Theme.monoTabular(size: 13, relativeTo: .footnote))
                    .foregroundStyle(color)
            } else {
                Text(IndianFormatter.priceCompact(abs(value)))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                    .font(Theme.monoTabular(size: 13, relativeTo: .footnote))
                    .foregroundStyle(color)
            }
        }
        .padding(.horizontal, Theme.Spacing.medium)
        .padding(.vertical, Theme.Spacing.small)
        .background(bgColor)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
    }
}

// MARK: - Gold Vertical Bar (Phase 1 redesign)

struct GoldVerticalBar: View {
    var body: some View {
        Rectangle()
            .fill(Theme.goldPrimary.opacity(0.7))
            .frame(width: 4)
    }
}

// MARK: - Confidence Arc View (Phase 1 redesign)

struct ConfidenceArcView: View {
    let score: Int // 0-100
    var size: CGFloat = 56

    private var normalizedScore: Double {
        Double(max(0, min(100, score))) / 100.0
    }

    var body: some View {
        ZStack {
            // Background arc
            Circle()
                .trim(from: 0, to: 1)
                .stroke(Theme.inkTertiary.opacity(0.2), lineWidth: 4)
                .frame(width: size, height: size)
                .rotationEffect(.degrees(-90))

            // Score arc
            Circle()
                .trim(from: 0, to: normalizedScore)
                .stroke(Theme.goldPrimary, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                .frame(width: size, height: size)
                .rotationEffect(.degrees(-90))
                .animation(.easeOut(duration: 1.0), value: score)

            // Center number
            Text("\(score)")
                .font(Theme.monoTabular(size: 16, relativeTo: .headline))
                .foregroundStyle(Theme.goldPrimary)
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Severity Dot (Phase 1 redesign)

struct SeverityDot: View {
    enum Severity {
        case high, medium, low

        var color: Color {
            switch self {
            case .high: return Theme.dataNegative
            case .medium: return Theme.holdAmber
            case .low: return Theme.dataPositive
            }
        }

        var label: String {
            switch self {
            case .high: return "HIGH"
            case .medium: return "MEDIUM"
            case .low: return "LOW"
            }
        }
    }

    let severity: Severity

    @State private var isPulsing = false

    var body: some View {
        Circle()
            .fill(severity.color)
            .frame(width: 8, height: 8)
            .scaleEffect(isPulsing && severity == .high ? 1.4 : 1.0)
            .opacity(isPulsing && severity == .high ? 0.6 : 1.0)
            .animation(
                severity == .high
                    ? .easeInOut(duration: 1.0).repeatForever(autoreverses: true)
                    : .default,
                value: isPulsing
            )
            .onAppear {
                if severity == .high && !MotionPolicy.isReduced() { isPulsing = true }
            }
    }
}
