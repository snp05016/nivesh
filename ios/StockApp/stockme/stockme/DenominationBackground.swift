import SwiftUI

// Each rupee denomination has a distinct color DNA
enum Denomination {
    case ten, twenty, fifty, hundred, twoHundred, fiveHundred, twoThousand

    var numeral: String {
        switch self {
        case .ten:          return "10"
        case .twenty:       return "20"
        case .fifty:        return "50"
        case .hundred:      return "100"
        case .twoHundred:   return "200"
        case .fiveHundred:  return "500"
        case .twoThousand:  return "2000"
        }
    }

    var tint: Color {
        switch self {
        case .ten:         return Theme.NoteTint.ten
        case .twenty:      return Theme.NoteTint.twenty
        case .fifty:       return Theme.NoteTint.fifty
        case .hundred:     return Theme.NoteTint.hundred
        case .twoHundred:  return Theme.NoteTint.twoHundred
        case .fiveHundred: return Theme.NoteTint.fiveHundred
        case .twoThousand: return Theme.NoteTint.twoThousand
        }
    }
}

// MARK: - Micro-text Guilloche Strip

struct MicroTextStrip: View {
    var body: some View {
        let text = "NIVESH ₹ भारत NIVESH ₹ भारत NIVESH ₹ भारत NIVESH ₹ भारत NIVESH ₹ भारत "
        Text(text + text)
            .font(Theme.serialNumberFont(size: 7))
            .foregroundStyle(.primary.opacity(0.10))
            .lineLimit(1)
            .frame(maxWidth: .infinity, alignment: .leading)
            .allowsHitTesting(false)
    }
}

// MARK: - Denomination Background

struct DenominationBackground: View {
    let denomination: Denomination
    @AppStorage("selectedTheme") private var selectedTheme: String = AppTheme.darkImmersive.rawValue
    @Environment(\.colorScheme) var colorScheme

    private var currentTheme: AppTheme {
        AppTheme(rawValue: selectedTheme) ?? .darkImmersive
    }

    private var tint: Color {
        denomination.tint
    }

    var body: some View {
        let isDark = colorScheme == .dark
        let baseColor = isDark ? currentTheme.canvasDark : currentTheme.canvasLight

        ZStack {
            baseColor
                .ignoresSafeArea()

            // Subtle diagonal gradient with the note's signature color
            LinearGradient(
                stops: [
                    .init(color: tint.opacity(isDark ? 0.06 : 0.12), location: 0),
                    .init(color: tint.opacity(isDark ? 0.02 : 0.04), location: 0.5),
                    .init(color: .clear, location: 1),
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            .allowsHitTesting(false)
        }
        .animation(.easeInOut(duration: 0.6), value: selectedTheme)
    }
}
