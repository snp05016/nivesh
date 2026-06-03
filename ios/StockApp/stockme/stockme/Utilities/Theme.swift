import SwiftUI
import UIKit

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

    // MARK: - The Paper

    static let canvas       = adaptive("F5F0E8", "1C1A14") // off-white / aged charcoal
    static let canvasDeep   = adaptive("EDE8DC", "242018") // card surfaces
    static let canvasShadow = adaptive("D9D3C4", "141210") // pressed/inset

    // MARK: - The Inks

    static let inkPrimary   = adaptive("2C2C2C", "E8E0D0") // charcoal / aged cream
    static let inkSecondary = adaptive("5C6B5A", "8A9E80") // sage green / lighter sage
    static let inkTertiary  = adaptive("8A8A7A", "5C5C52") // faded / dim

    // MARK: - The Accents

    static let securityGold      = adaptive("B8973A", "C8A84A") // dull gold / brighter gold
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

    // MARK: - Typography

    static func engravedSerif(size: CGFloat, weight: Font.Weight = .regular) -> Font {
        weight == .bold
            ? Font.custom("Georgia-Bold", size: size)
            : Font.custom("Georgia", size: size)
    }

    static func serialNumberFont(size: CGFloat) -> Font {
        Font.system(size: size, weight: .medium, design: .monospaced)
    }

    // Official stamp labels — apply .tracking(1.5) on Text at call site
    static func officialStampFont(size: CGFloat) -> Font {
        Font.system(size: size, weight: .medium)
    }

    static func hindiFont(size: CGFloat) -> Font {
        Font.custom("Georgia", size: size).italic()
    }

    static let labelStyle = Font.system(size: 10, weight: .bold).uppercaseSmallCaps()

    // MARK: - Spacing

    static let cardPadding: CGFloat = 20
    static let screenPadding: CGFloat = 20
    static let sectionSpacing: CGFloat = 32

    // MARK: - Gradients

    static let securityThreadGradient = LinearGradient(
        colors: [securityGold.opacity(0.35), securityGold.opacity(0.08)],
        startPoint: .top,
        endPoint: .bottom
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
                .fill(Color(hex: "5C6B5A").opacity(colorScheme == .dark ? 0.025 : 0.030))
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
                        .foregroundColor(Theme.inkPrimary.opacity(opacity))
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
        ZStack {
            Path { path in
                let w = UIScreen.main.bounds.width
                path.move(to: .zero)
                for x in stride(from: 0, through: w, by: 4) {
                    path.addLine(to: CGPoint(x: x, y: sin(x / 4.0) * 2))
                }
            }
            .stroke(Theme.inkSecondary.opacity(0.22), lineWidth: 0.5)

            Path { path in
                let w = UIScreen.main.bounds.width
                path.move(to: CGPoint(x: 0, y: 4))
                for x in stride(from: 0, through: w, by: 4) {
                    path.addLine(to: CGPoint(x: x, y: cos(x / 4.0) * 2 + 4))
                }
            }
            .stroke(Theme.inkSecondary.opacity(0.08), lineWidth: 0.5)
        }
        .frame(height: 8)
        .padding(.vertical, 6)
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
            .foregroundColor(color)
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
    let delay: Double
    @State private var isVisible = false

    func body(content: Content) -> some View {
        content
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 10)
            .onAppear {
                withAnimation(.easeOut(duration: 0.5).delay(delay)) {
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
        self
            .background(Theme.canvasDeep)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.white.opacity(0.5), lineWidth: 0.5)
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Theme.inkPrimary.opacity(0.12), lineWidth: 1)
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Theme.inkSecondary.opacity(0.16), lineWidth: 0.5)
                        .padding(3)
                }
            )
            .shadow(color: Theme.inkPrimary.opacity(0.06), radius: 3, x: 0, y: 2)
    }
}
