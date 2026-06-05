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
    var body: some View {
        ZStack {
            Rectangle()
                .fill(Theme.securityGold.opacity(0.11))
                .frame(width: 12)
            VStack(spacing: 2) {
                ForEach(0..<20, id: \.self) { _ in
                    Text("NIVESH ₹ RBI ")
                        .font(Theme.serialNumberFont(size: 5))
                        .foregroundStyle(Theme.securityGold.opacity(0.38))
                        .rotationEffect(.degrees(-90))
                        .fixedSize()
                }
            }
        }
        .frame(width: 12)
        .clipped()
        .allowsHitTesting(false)
    }
}

// MARK: - Rupee Medallion Watermark (₹ at 320pt, behind hero content)

struct RupeeWatermark: View {
    var body: some View {
        Text("₹")
            .font(Font.custom("Georgia-Bold", size: 320))
            .foregroundStyle(Theme.securityGold.opacity(0.035))
            .offset(x: 60, y: -40)
            .allowsHitTesting(false)
    }
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
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(tintColor.opacity(0.07))
            .overlay(
                RoundedRectangle(cornerRadius: 2)
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
        HStack(alignment: .firstTextBaseline, spacing: 1) {
            Text("₹")
                .font(Theme.engravedSerif(size: fontSize, weight: .bold))
                .foregroundStyle(Theme.securityGold)
            Text(IndianFormatter.priceWithoutSymbol(current))
                .font(Theme.engravedSerif(size: fontSize, weight: .bold))
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

    var body: some View {
        ZStack {
            Circle()
                .fill(Theme.canvasDeep)
            Circle()
                .stroke(Theme.securityGold.opacity(0.5), lineWidth: 1.5)
                .frame(width: 48, height: 48)
            Circle()
                .stroke(Theme.securityGold.opacity(0.2), lineWidth: 0.5)
                .frame(width: 40, height: 40)
            Text(initials.uppercased())
                .font(Theme.engravedSerif(size: 16, weight: .bold))
                .foregroundStyle(Theme.inkPrimary)
        }
        .frame(width: 52, height: 52)
    }
}
