import SwiftUI

// MARK: - Color from hex

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 255, 255, 255)
        }
        self.init(.sRGB, red: Double(r)/255, green: Double(g)/255, blue: Double(b)/255, opacity: Double(a)/255)
    }
}

// MARK: - View modifiers

extension View {
    /// Fixes horizontal scroll UX: direction lock (fixed height), trailing inset, fade edge
    func horizontalScrollFixed(height: CGFloat? = nil) -> some View {
        self
            .frame(height: height)
            .overlay(alignment: .trailing) {
                LinearGradient(
                    gradient: Gradient(colors: [Theme.canvas.opacity(0), Theme.canvas]),
                    startPoint: .leading, endPoint: .trailing
                )
                .frame(width: Theme.Spacing.xLarge)
                .allowsHitTesting(false)
            }
            .padding(.horizontal, Theme.Spacing.card)
    }

    func inkCard() -> some View {
        self
            .background(Theme.canvas)
            .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.card).stroke(Theme.inkPrimary.opacity(0.1), lineWidth: 1))
            .cornerRadius(Theme.CornerRadius.card)
    }

    func shimmerPlaceholder(isLoading: Bool) -> some View {
        self.modifier(ShimmerModifier(isLoading: isLoading))
    }
    
    func hideKeyboardOnTap() -> some View {
        self.onTapGesture {
            UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
        }
    }

    func hideKeyboard() {
        UIApplication.shared.sendAction(
            #selector(UIResponder.resignFirstResponder),
            to: nil, from: nil, for: nil
        )
    }
}

// MARK: - Shimmer Modifier

struct ShimmerModifier: ViewModifier {
    let isLoading: Bool
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        if isLoading {
            content
                .overlay(
                    GeometryReader { geo in
                        LinearGradient(
                            colors: [
                                Theme.canvas.opacity(0),
                                Theme.canvas.opacity(0.3),
                                Theme.canvas.opacity(0),
                            ],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: geo.size.width * 2)
                        .offset(x: phase * geo.size.width)
                        .onAppear {
                            guard !MotionPolicy.isReduced() else { return }
                            withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                                phase = 1
                            }
                        }
                    }
                )
                .clipped()
        } else {
            content
        }
    }
}

// MARK: - Number formatting

extension Double {
    var inrFormatted: String { IndianFormatter.price(self) }
    var percentFormatted: String { IndianFormatter.percent(self) }
    var shortFormatted: String { IndianFormatter.priceCompact(self) }
}

// MARK: - Date

extension Date {
    var timeGreeting: String {
        let hour = Calendar.current.component(.hour, from: self)
        switch hour {
        case 5..<12:  return "Good morning"
        case 12..<17: return "Good afternoon"
        default:       return "Good evening"
        }
    }
}


// MARK: - Haptic Feedback Manager
struct HapticManager {
    static func impact(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
        // Only run on physical devices, simulators often lack the pattern library plist
        #if targetEnvironment(simulator)
        return 
        #else
        guard isEnabled() else { return }
        let generator = UIImpactFeedbackGenerator(style: style)
        generator.prepare()
        generator.impactOccurred()
        #endif
    }
    
    static func notification(_ type: UINotificationFeedbackGenerator.FeedbackType) {
        #if targetEnvironment(simulator)
        return
        #else
        guard isEnabled() else { return }
        let generator = UINotificationFeedbackGenerator()
        generator.prepare()
        generator.notificationOccurred(type)
        #endif
    }
}

// MARK: - Input Validation (Fixes 3.5, 3.7, 3.8, 3.15)

extension String {
    /// Fix 3.5: Check if text contains banned Western number scales.
    var containsWesternScale: Bool {
        let pattern = #"\b(million|billion|trillion)\b"#
        return range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }

    /// Fix 3.15: Truncate to max characters for journal entries.
    func truncating(to maxChars: Int) -> String {
        return String(prefix(maxChars))
    }
}

// MARK: - Accessibility Helpers (Fix 3.25)

extension View {
    /// Fix 3.25: Apply Dynamic Type scaling guard for financial data.
    /// Prevents serialNumberFont text from clipping at 300% accessibility sizes.
    func accessibleFinancialText() -> some View {
        self
            .minimumScaleFactor(0.3)
            .lineLimit(1)
            .allowsTightening(true)
    }
}
