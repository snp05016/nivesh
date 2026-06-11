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

// MARK: - RBI Seal Background (replaces breaking numeral)

struct RBISealBackground: View {
    var opacity: Double = 0.04

    var body: some View {
        ZStack {
            Circle()
                .stroke(lineWidth: 1.5)
                .frame(width: 180, height: 180)
            Circle()
                .stroke(lineWidth: 0.8)
                .frame(width: 160, height: 160)

            // Curved top text "RESERVE BANK OF INDIA"
            ForEach(Array("RESERVE BANK OF INDIA".enumerated()), id: \.offset) { i, char in
                let total = 20
                let angle = Double(i - total / 2) * 9.5 - 90
                Text(String(char))
                    .font(Theme.serialNumberFont(size: 9))
                    .rotationEffect(.degrees(angle + 90))
                    .offset(y: -70)
                    .rotationEffect(.degrees(angle))
            }

            // Centre ₹
            Text("₹")
                .font(Font.custom("Georgia-Bold", size: 52))
                .offset(y: 4)

            // Curved bottom text "SATYAMEVA JAYATE"
            ForEach(Array("SATYAMEVA JAYATE".enumerated()), id: \.offset) { i, char in
                let total = 16
                let angle = Double(i - total / 2) * 11.0 + 90
                Text(String(char))
                    .font(Theme.serialNumberFont(size: 8))
                    .rotationEffect(.degrees(angle - 90))
                    .offset(y: 70)
                    .rotationEffect(.degrees(angle))
            }

            // Cardinal dots
            ForEach([0, 90, 180, 270], id: \.self) { angle in
                Circle()
                    .fill()
                    .frame(width: 4, height: 4)
                    .offset(y: -68)
                    .rotationEffect(.degrees(Double(angle)))
            }
        }
        .foregroundStyle(.primary)
        .opacity(opacity)
        .allowsHitTesting(false)
    }
}

// MARK: - Micro-text Guilloche Strip

struct MicroTextStrip: View {
    var body: some View {
        let text = "NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत "
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
        (colorScheme == .dark ? currentTheme.canvasDark : currentTheme.canvasLight)
            .ignoresSafeArea()
            .animation(.easeInOut(duration: 0.6), value: selectedTheme)
    }
}
