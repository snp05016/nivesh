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

    // MARK: - Color Helpers

    private static func uiColor(_ hex: String, alpha: CGFloat = 1) -> UIColor {
        let h = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: h).scanHexInt64(&int)
        let r = CGFloat((int >> 16) & 0xFF) / 255
        let g = CGFloat((int >> 8) & 0xFF) / 255
        let b = CGFloat(int & 0xFF) / 255
        return UIColor(red: r, green: g, blue: b, alpha: alpha)
    }

    // Kept for backward-compat — now always returns the dark value since palette is fixed dark
    static func adaptive(_ light: String, _ dark: String, alpha: CGFloat = 1) -> Color {
        Color(uiColor(dark, alpha: alpha))
    }

    // MARK: - The Canvas (delegates to ThemeManager for per-denomination + light/dark)

    static var canvas: Color      { ThemeManager.shared.canvas(for: currentColorScheme) }
    static var canvasDeep: Color  { ThemeManager.shared.canvasDeep(for: currentColorScheme) }
    static var canvasShadow: Color { ThemeManager.shared.canvasShadow(for: currentColorScheme) }

    // MARK: - The Inks (delegates to ThemeManager for per-denomination + light/dark)

    static var inkPrimary: Color   { ThemeManager.shared.inkPrimary(for: currentColorScheme) }
    static var inkSecondary: Color { ThemeManager.shared.inkSecondary(for: currentColorScheme) }
    static var inkTertiary: Color  { ThemeManager.shared.inkTertiary(for: currentColorScheme) }

    // MARK: - The Accents

    static var securityGold: Color      { ThemeManager.shared.accent(for: currentColorScheme) }
    static var securityGoldLight: Color { securityGold.opacity(0.13) }

    // MARK: - Color Scheme Detection
    private static var currentColorScheme: ColorScheme {
        UITraitCollection.current.userInterfaceStyle == .dark ? .dark : .light
    }

    // MARK: - Market Signals

    static let bullGreen      = Color(uiColor("00D4AA"))                         // neon teal (same as securityGold)
    static var bullGreenLight: Color { Color(uiColor("00D4AA")).opacity(0.13) }
    static let bearRed        = Color(uiColor("E85555"))                         // vivid red
    static var bearRedLight:   Color { Color(uiColor("E85555")).opacity(0.13) }
    static let holdAmber      = Color(uiColor("B08020"))                         // amber hold

    // Legacy aliases — Signal.color in Models.swift uses these
    static let signalEmerald = bullGreen
    static let signalRuby    = bearRed

    // MARK: - Extended Palette

    static let avatarBlue    = Color(uiColor("4B7BEC"))  // avatar / badge accent
    static let cardBlueDeep  = Color(uiColor("1A2744"))  // deep navy card surface

    // MARK: - Chart & Data Colors

    static let chartPromoter   = Color(uiColor("6A7AAA"))
    static let avatarBackground = cardBlueDeep

    // MARK: - Denomination Tints (dual-mode: dark & light)

    enum NoteTint {
        // Dark-mode tints (subtle on dark backgrounds — RBI note base colours)
        private static let tenDark:        Color = Color(uiColor("8B5A42"))  // ₹10 Chocolate Brown
        private static let twentyDark:     Color = Color(uiColor("B8C840"))  // ₹20 Greenish Yellow
        private static let fiftyDark:      Color = Color(uiColor("3A72CC"))  // ₹50 Fluorescent Blue
        private static let hundredDark:    Color = Color(uiColor("9080C0"))  // ₹100 Lavender
        private static let twoHundredDark: Color = Color(uiColor("C8A800"))  // ₹200 Bright Yellow
        private static let fiveHundredDark:Color = Color(uiColor("7A8E8E"))  // ₹500 Stone Grey
        private static let twoThousandDark:Color = Color(uiColor("C050A0"))  // ₹2000 Magenta

        // Light-mode tints (darker/more saturated for light backgrounds)
        private static let tenLight:        Color = Color(uiColor("6B3A22"))  // ₹10 Darker chocolate
        private static let twentyLight:     Color = Color(uiColor("6B8020"))  // ₹20 Olive green
        private static let fiftyLight:      Color = Color(uiColor("1A4AA0"))  // ₹50 Deep blue
        private static let hundredLight:    Color = Color(uiColor("6A50A0"))  // ₹100 Deep lavender
        private static let twoHundredLight: Color = Color(uiColor("A88800"))  // ₹200 Dark gold
        private static let fiveHundredLight:Color = Color(uiColor("5A6E6E"))  // ₹500 Dark stone
        private static let twoThousandLight:Color = Color(uiColor("A03080"))  // ₹2000 Deep magenta

        /// Scheme-aware accessors — pale on dark, saturated on light.
        private static var isDark: Bool { UITraitCollection.current.userInterfaceStyle == .dark }

        static var ten: Color        { isDark ? tenDark : tenLight }
        static var twenty: Color     { isDark ? twentyDark : twentyLight }
        static var fifty: Color      { isDark ? fiftyDark : fiftyLight }
        static var hundred: Color    { isDark ? hundredDark : hundredLight }
        static var twoHundred: Color { isDark ? twoHundredDark : twoHundredLight }
        static var fiveHundred: Color{ isDark ? fiveHundredDark : fiveHundredLight }
        static var twoThousand: Color{ isDark ? twoThousandDark : twoThousandLight }
    }

    // MARK: - Borders (scheme-aware)

    private static var isDark: Bool { UITraitCollection.current.userInterfaceStyle == .dark }

    static var borderFine: Color  { isDark ? Color.white.opacity(0.04) : Color.black.opacity(0.08) }
    static var borderSage: Color  { isDark ? Color.white.opacity(0.08) : Color.black.opacity(0.12) }
    static let paperBorder: Color = Color.white.opacity(0.06)  // RBI watermark border — dark-only by design
    static let paperTexture: Color = Color.white.opacity(0.025)

    // MARK: - Surface Hierarchy (scheme-aware)

    /// Cards one level above canvas — delegates to ThemeManager.canvasDeep.
    static var surfaceElevated: Color { ThemeManager.shared.canvasDeep(for: currentColorScheme) }
    /// Modal sheets, dropdowns — slightly lighter than surfaceElevated.
    static var surfaceFloat: Color { surfaceElevated.opacity(0.85) }

    // MARK: - Enhanced Borders

    static let borderSubtle = Color.white.opacity(0.06)
    static var borderStrong: Color { securityGold.opacity(0.25) }   // accent-tinted important borders

    // MARK: - Data Colors

    static let dataPositive      = Color(uiColor("00D4AA"))
    static let dataNegative      = Color(uiColor("E85555"))
    static let dataPositiveMuted = Color(uiColor("00D4AA")).opacity(0.15)
    static let dataNegativeMuted = Color(uiColor("E85555")).opacity(0.15)
    static var goldPrimary: Color { securityGold }                      // alias
    static var goldMuted: Color  { securityGold.opacity(0.30) }

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

    /// Body / heading text — now uses system font so all call sites keep working.
    static func engravedSerif(size: CGFloat, weight: Font.Weight = .regular, relativeTo style: Font.TextStyle = .body) -> Font {
        Font.system(size: size, weight: weight == .bold ? .bold : .regular, design: .default)
    }

    /// Monospaced font for prices, percentages, numerical data.
    static func serialNumberFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .monospaced)
    }

    /// Official stamp labels — apply .tracking(1.5) at call site.
    static func officialStampFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .default)
    }

    /// Secondary text — italic system font (replaces Georgia italic).
    static func hindiFont(size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        Font.system(size: size, weight: .regular)
    }

    static let labelStyle = Font.caption.weight(.bold).uppercaseSmallCaps()

    // MARK: - Data Typography

    /// Large price display — monospaced bold for live prices.
    static func dataLarge(size: CGFloat = 28, relativeTo style: Font.TextStyle = .title) -> Font {
        Font.system(size: size, weight: .bold, design: .monospaced)
    }

    /// Extra-large display — monospaced bold for portfolio totals.
    static func dataXL(size: CGFloat = 38, relativeTo style: Font.TextStyle = .largeTitle) -> Font {
        Font.system(size: size, weight: .bold, design: .monospaced)
    }

    /// Monospaced tabular font — vertically aligned decimals for P&L numbers.
    static func monoTabular(size: CGFloat = 14, relativeTo style: Font.TextStyle = .body) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .monospaced)
    }

    /// Micro label — for axis labels, timestamps.
    static func microLabel(size: CGFloat = 10, relativeTo style: Font.TextStyle = .caption2) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .medium, design: .default)
    }

    /// Section header label — ALL CAPS with tracking +1.2 at call site.
    static func sectionCapsLabel(size: CGFloat = 11, relativeTo style: Font.TextStyle = .caption) -> Font {
        let scaled = UIFontMetrics(forTextStyle: uiTextStyle(from: style)).scaledValue(for: size)
        return Font.system(size: scaled, weight: .semibold, design: .default)
    }

    /// SF Pro Rounded for secondary typography.
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
        static let none: CGFloat = 0
        static let xSmall: CGFloat = 2
        static let small: CGFloat = 4
        static let tight: CGFloat = 6
        static let medium: CGFloat = 8
        static let standard: CGFloat = 12
        static let card: CGFloat = 16
        static let screen: CGFloat = 20
        static let large: CGFloat = 24
        static let xLarge: CGFloat = 32
        static let cardInset: CGFloat = 20
        static let sectionGap: CGFloat = 28
    }

    // MARK: - Corner Radii

    enum CornerRadius {
        static let small: CGFloat  = 4
        static let tight: CGFloat  = 6
        static let medium: CGFloat = 10   // was 8
        static let large: CGFloat  = 12
        static let card: CGFloat   = 14   // was 16
        static let badge: CGFloat  = 8
        static let pill: CGFloat   = 100
        static let sheet: CGFloat  = 24
    }

    static let cardPadding: CGFloat    = Spacing.screen
    static let screenPadding: CGFloat  = Spacing.screen
    static let sectionSpacing: CGFloat = Spacing.xLarge

    // MARK: - Gradients

    static var securityThreadGradient: LinearGradient {
        LinearGradient(
            colors: [securityGold.opacity(0.35), securityGold.opacity(0.08)],
            startPoint: .top,
            endPoint: .bottom
        )
    }

    static var securityGoldGradient: LinearGradient {
        LinearGradient(
            colors: [securityGold, securityGold.opacity(0.78)],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    /// Chart glow fill — teal fade for bull moves
    static var chartBullGradient: LinearGradient {
        LinearGradient(
            colors: [Color(uiColor("00D4AA")).opacity(0.25), Color(uiColor("00D4AA")).opacity(0.05), Color.clear],
            startPoint: .top, endPoint: .bottom
        )
    }

    /// Chart glow fill — red fade for bear moves
    static var chartBearGradient: LinearGradient {
        LinearGradient(
            colors: [Color(uiColor("E85555")).opacity(0.20), Color(uiColor("E85555")).opacity(0.05), Color.clear],
            startPoint: .top, endPoint: .bottom
        )
    }
}

// MARK: - Paper Texture (now a plain dark canvas)

struct PaperTexture: View {
    var body: some View {
        Theme.canvas.ignoresSafeArea()
    }
}

// MARK: - Banknote Watermark (no-op in terminal aesthetic)

struct BanknoteWatermark: View {
    let text: String
    let size: CGFloat
    let opacity: Double
    let alignment: Alignment

    var body: some View {
        EmptyView()
    }
}

// MARK: - Guilloché Divider (replaced with clean spacer)

struct GuillocheDivider: View {
    var body: some View {
        Spacer().frame(height: Theme.Spacing.card)
    }
}

// MARK: - Section Divider

struct SectionDivider: View {
    var body: some View {
        Rectangle()
            .fill(Color.white.opacity(0.06))
            .frame(height: 0.5)
            .padding(.horizontal, Theme.screenPadding)
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

    /// Dark terminal card — single hairline border on deep navy surface.
    func banknoteCard() -> some View {
        self
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Color.white.opacity(0.08), lineWidth: 0.5)
            )
    }

    /// Alias for banknoteCard — explicit dark card style.
    func darkCard() -> some View {
        self
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: 14))
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .stroke(Color.white.opacity(0.08), lineWidth: 0.5)
            )
    }

    /// Frosted glass inner card layer.
    func glassCard() -> some View {
        self
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Color.white.opacity(0.08), lineWidth: 0.5)
            )
    }
}
