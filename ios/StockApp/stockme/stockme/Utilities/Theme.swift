import SwiftUI
import UIKit

// MARK: - UIColor Brightness Helper

extension UIColor {
    func withBrightness(offset: CGFloat) -> UIColor {
        var h: CGFloat = 0, s: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        getHue(&h, saturation: &s, brightness: &b, alpha: &a)
        return UIColor(hue: h, saturation: s, brightness: max(0, min(1, b + offset)), alpha: a)
    }
}

enum Theme {

    // MARK: - Adaptive Color Helper

    private static func uiColor(_ hex: String, alpha: CGFloat = 1) -> UIColor {
        var h = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: h).scanHexInt64(&int)
        let r = CGFloat((int >> 16) & 0xFF) / 255
        let g = CGFloat((int >> 8) & 0xFF) / 255
        let b = CGFloat(int & 0xFF) / 255
        return UIColor(red: r, green: g, blue: b, alpha: alpha)
    }

    // Creates a Color that automatically adapts to light/dark mode
    static func adaptive(_ light: String, _ dark: String, alpha: CGFloat = 1) -> Color {
        Color(UIColor { tc in
            tc.userInterfaceStyle == .dark
                ? uiColor(dark, alpha: alpha)
                : uiColor(light, alpha: alpha)
        })
    }

    // MARK: - The Paper (dynamic per ThemeManager)

    static var canvas: Color {
        Color(UIColor { tc in
            let scheme: ColorScheme = tc.userInterfaceStyle == .dark ? .dark : .light
            return UIColor(ThemeManager.shared.canvas(for: scheme))
        })
    }
    static var canvasDeep: Color {
        Color(UIColor { tc in
            let scheme: ColorScheme = tc.userInterfaceStyle == .dark ? .dark : .light
            let base = UIColor(ThemeManager.shared.canvas(for: scheme))
            return scheme == .dark
                ? base.withBrightness(offset: 0.04)
                : base.withBrightness(offset: -0.02)
        })
    }
    static var canvasShadow: Color {
        Color(UIColor { tc in
            let scheme: ColorScheme = tc.userInterfaceStyle == .dark ? .dark : .light
            let base = UIColor(ThemeManager.shared.canvas(for: scheme))
            return scheme == .dark
                ? base.withBrightness(offset: -0.03)
                : base.withBrightness(offset: -0.04)
        })
    }

    // MARK: - The Inks

    static let inkPrimary   = adaptive("2C2C2C", "E8E0D0") // charcoal / aged cream
    static let inkSecondary = adaptive("5C6B5A", "8A9E80") // sage green / lighter sage
    static let inkTertiary  = adaptive("8A8A7A", "5C5C52") // faded / dim

    // MARK: - The Accents

    static var securityGold: Color {
        Color(UIColor { tc in
            let scheme: ColorScheme = tc.userInterfaceStyle == .dark ? .dark : .light
            return UIColor(ThemeManager.shared.accent(for: scheme))
        })
    }
    static let securityGoldLight = adaptive("E8C96A", "E8C96A")

    // MARK: - Market Signals

    static let bullGreen      = adaptive("2D5A3D", "4A8A5D") // forest / lighter forest
    static let bullGreenLight = adaptive("4A7A5A", "5A9A6A")
    static let bearRed        = adaptive("8B3A2A", "C05540") // brick / brighter brick
    static let bearRedLight   = adaptive("B55A45", "D06A55")
    static let holdAmber      = adaptive("8B6914", "B08020") // aged / brighter amber

    // Legacy aliases — Signal.color in Models.swift uses these
    static let signalEmerald = bullGreen
    static let signalRuby    = bearRed

    // MARK: - Chart & Data Colors

    static let chartPromoter = adaptive("4A5A8A", "6A7AAA")
    static let avatarBackground = adaptive("E5E0D5", "3A3530")

    // MARK: - Denomination Tints (banknote-specific)
    // Use as .shadow(color:) or .overlay accents — NOT as full background fills

    enum NoteTint {
        static let ten: Color = adaptive("6B3A28", "9B6050")
        static let fifty: Color = adaptive("4A5A8A", "6A7AAA")
        static let hundred: Color = adaptive("7A6BA0", "9A8BC0")
        static let twoHundred: Color = adaptive("C85A20", "E87A40")
        static let fiveHundred: Color = adaptive("4A6B5A", "6A8B7A")
        static let twoThousand: Color = adaptive("B040A0", "D060C0")
    }

    // MARK: - Borders (toned down 10%)

    static let borderFine = adaptive("2C2C2C", "E8E0D0", alpha: 0.10)
    static let borderSage = adaptive("5C6B5A", "8A9E80", alpha: 0.20)
    static let paperBorder = Color(UIColor { tc in
        tc.userInterfaceStyle == .dark
            ? UIColor(white: 1, alpha: 0.06)
            : UIColor(white: 0, alpha: 0.08)
    })
    static let paperTexture = Color(UIColor { tc in
        tc.userInterfaceStyle == .dark
            ? UIColor(white: 1, alpha: 0.025)
            : UIColor(white: 0, alpha: 0.030)
    })

    // MARK: - Surface Hierarchy (Phase 1 redesign)

    static let surfaceElevated = adaptive("EDE8DC", "262318")   // cards one level above canvas
    static let surfaceFloat    = adaptive("F0EBE0", "2E2A20")   // modal sheets, dropdowns

    // MARK: - Enhanced Borders (Phase 1 redesign)

    static let borderSubtle    = adaptive("2C2C2C", "3A3530", alpha: 0.60)
    static let borderStrong    = adaptive("B8973A", "C8A84A", alpha: 0.25)  // gold-tinted important borders

    // MARK: - Data Colors (Phase 1 redesign — muted financial semantics)

    static let dataPositive      = adaptive("3D9B6A", "3D9B6A")   // muted forest green
    static let dataNegative      = adaptive("C4533A", "C4533A")   // heritage brick red
    static let dataPositiveMuted = adaptive("3D9B6A", "3D9B6A", alpha: 0.15)
    static let dataNegativeMuted = adaptive("C4533A", "C4533A", alpha: 0.15)
    static let goldPrimary       = adaptive("B8973A", "C8A84A")   // security gold alias
    static let goldMuted         = adaptive("B8973A", "C8A84A", alpha: 0.30)

    // MARK: - Typography

    /// Maps SwiftUI `Font.TextStyle` to UIKit `UIFont.TextStyle` for Dynamic Type scaling.
    private static func uiTextStyle(from style: Font.TextStyle) -> UIFont.TextStyle {
        switch style {
        case .largeTitle:  return .largeTitle
        case .title:       return .title1
        case .title2:      return .title2
        case .title3:      return .title3
        case .headline:    return .headline
        case .subheadline: return .subheadline
        case .body:        return .body
        case .callout:     return .callout
        case .footnote:    return .footnote
        case .caption:     return .caption1
        case .caption2:    return .caption2
        @unknown default:  return .body
        }
    }

    static func engravedSerif(size: CGFloat, weight: Font.Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        weight == .bold
            ? Font.custom("Georgia-Bold", size: size, relativeTo: style)
            : Font.custom("Georgia", size: size, relativeTo: style)
    }

    static func serialNumberFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .monospaced)
    }

    // Official stamp labels — apply .tracking(1.5) on Text at call site
    static func officialStampFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .default)
    }

    static func hindiFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        Font.custom("Georgia", size: size, relativeTo: style).italic()
    }

    static let labelStyle = Font.caption.weight(.bold).uppercaseSmallCaps()

    // MARK: - Data Typography (Phase 1 redesign)

    /// Large price display — Georgia Bold 28pt for live prices
    static func dataLarge(size: CGFloat = 28, relativeTo style: Font.TextStyle = .title) -> Font {
        Font.custom("Georgia-Bold", size: size, relativeTo: style)
    }

    /// Extra-large display — Georgia Bold 38pt for portfolio totals
    static func dataXL(size: CGFloat = 38, relativeTo style: Font.TextStyle = .largeTitle) -> Font {
        Font.custom("Georgia-Bold", size: size, relativeTo: style)
    }

    /// Monospaced tabular font — vertically aligned decimals for P&L numbers
    static func monoTabular(size: CGFloat = 14, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .monospaced)
    }

    /// Micro label — 10pt SF Pro medium for axis labels, timestamps
    static func microLabel(size: CGFloat = 10, relativeTo style: Font.TextStyle = .caption2) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .default)
    }

    /// Section header label — 11pt SF Pro semibold ALL CAPS with tracking +1.2
    static func sectionCapsLabel(size: CGFloat = 11, relativeTo style: Font.TextStyle = .caption) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .semibold, design: .default)
    }

    // Fix 1.1: SF Pro Rounded for secondary typography (descriptions, timestamps, card labels).
    // Georgia (.engravedSerif) reserved STRICTLY for hero metrics (portfolio value, ticker stamps, headers).
    static func roundedSecondary(size: CGFloat = 14, weight: Font.Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: weight, design: .rounded)
    }

    static func roundedCaption(size: CGFloat = 11, relativeTo style: Font.TextStyle = .caption) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .regular, design: .rounded)
    }

    // MARK: - Spacing

    enum Spacing {
        static let xSmall: CGFloat = 2
        static let small: CGFloat = 4
        static let tight: CGFloat = 6
        static let medium: CGFloat = 8
        static let standard: CGFloat = 12
        static let card: CGFloat = 16
        static let screen: CGFloat = 20
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
        static let cardInset: CGFloat = 20   // standard card internal padding
        static let sectionGap: CGFloat = 28  // gap between major sections
    }

    enum CornerRadius {
        static let small: CGFloat = 4
        static let tight: CGFloat = 6
        static let medium: CGFloat = 8
        static let large: CGFloat = 12
        static let card: CGFloat = 16
        static let pill: CGFloat = 100   // for signal badges, chips
        static let sheet: CGFloat = 24   // bottom sheets
    }

    static let cardPadding: CGFloat = Spacing.screen
    static let screenPadding: CGFloat = Spacing.screen
    static let sectionSpacing: CGFloat = Spacing.xLarge

    // MARK: - Gradients

    static let securityThreadGradient = LinearGradient(
        colors: [securityGold.opacity(0.35), securityGold.opacity(0.08)],
        startPoint: .top,
        endPoint: .bottom
    )

    static let securityGoldGradient = LinearGradient(
        colors: [securityGold, securityGold.opacity(0.78)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
}

// MARK: - Paper Texture (dark-mode aware)

struct PaperTexture: View {
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            Canvas { context, size in
                let grainColor: Color = colorScheme == .dark
                    ? .white.opacity(0.025)
                    : .black.opacity(0.030)
                for _ in 0..<500 {
                    let rect = CGRect(
                        x: CGFloat.random(in: 0...size.width),
                        y: CGFloat.random(in: 0...size.height),
                        width: 1, height: 1
                    )
                    context.fill(Path(rect), with: .color(grainColor))
                }
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)

            Rectangle()
                .fill(Theme.inkSecondary.opacity(colorScheme == .dark ? 0.025 : 0.030))
                .ignoresSafeArea()
                .allowsHitTesting(false)
        }
    }
}

// MARK: - Banknote Watermark

struct BanknoteWatermark: View {
    let text: String
    let size: CGFloat
    let opacity: Double
    let alignment: Alignment

    var body: some View {
        ZStack {
            Color.clear
                .overlay(
                    Text(text)
                        .font(Theme.engravedSerif(size: size, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary.opacity(opacity))
                        .rotationEffect(.degrees(-20))
                        .offset(x: size * 0.1, y: size * 0.1),
                    alignment: alignment
                )
        }
        .allowsHitTesting(false)
    }
}

// MARK: - Guilloché Divider (toned down)

struct GuillocheDivider: View {
    var body: some View {
        GeometryReader { geo in
            ZStack {
                Path { path in
                    let w = geo.size.width
                    path.move(to: .zero)
                    for x in stride(from: 0, through: w, by: 4) {
                        path.addLine(to: CGPoint(x: x, y: sin(x / 4.0) * 2))
                    }
                }
                .stroke(Theme.inkSecondary.opacity(0.22), lineWidth: 0.5)

                Path { path in
                    let w = geo.size.width
                    path.move(to: CGPoint(x: 0, y: 4))
                    for x in stride(from: 0, through: w, by: 4) {
                        path.addLine(to: CGPoint(x: x, y: cos(x / 4.0) * 2 + 4))
                    }
                }
                .stroke(Theme.inkSecondary.opacity(0.08), lineWidth: 0.5)
            }
            .frame(height: Theme.Spacing.medium)
            .padding(.vertical, Theme.Spacing.tight)
        }
    }
}

// MARK: - Count-Up Number

struct CountUpNumber: View {
    let target: Double
    let prefix: String
    let font: Font
    let color: Color

    @State private var current: Double = 0

    var body: some View {
        Text(prefix + IndianFormatter.price(current))
            .font(font)
            .monospacedDigit()
            .foregroundStyle(color)
            .onAppear {
                withAnimation(.easeOut(duration: 1.2)) { current = target }
            }
            .onChange(of: target) { _, newVal in
                withAnimation(.easeOut(duration: 0.6)) { current = newVal }
            }
    }
}

// MARK: - Stagger Appear

struct StaggerAppear: ViewModifier {
    private static let staggerOffset: CGFloat = 10
    private static let staggerDuration: Double = 0.5

    let delay: Double
    @State private var isVisible = false

    func body(content: Content) -> some View {
        content
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : Self.staggerOffset)
            .onAppear {
                withAnimation(.easeOut(duration: Self.staggerDuration).delay(delay)) {
                    isVisible = true
                }
            }
    }
}

extension View {
    func staggerAppear(delay: Double) -> some View {
        modifier(StaggerAppear(delay: delay))
    }

    // Double-border banknote card (toned down 10%)
    func banknoteCard() -> some View {
        let shadowRadius: CGFloat = 3
        let shadowY: CGFloat = 2
        return self
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            .overlay(
                ZStack {
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .stroke(Color.white.opacity(0.5), lineWidth: 0.5)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                        .stroke(Theme.inkPrimary.opacity(0.12), lineWidth: 1)
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                        .stroke(Theme.inkSecondary.opacity(0.16), lineWidth: 0.5)
                        .padding(3)
                }
            )
            .shadow(color: Theme.inkPrimary.opacity(0.06), radius: shadowRadius, x: 0, y: shadowY)
    }

    // Glass-over-paper inner card layer — data floats on frosted glass
    func glassCard() -> some View {
        self
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Color.white.opacity(0.15), lineWidth: 0.5)
            )
            .shadow(color: .black.opacity(0.08), radius: 8, x: 0, y: 2)
    }
}
