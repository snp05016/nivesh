import SwiftUI

// Each rupee denomination has a distinct color DNA
enum Denomination {
    case ten, fifty, hundred, twoHundred, fiveHundred, twoThousand

    var numeral: String {
        switch self {
        case .ten:          return "10"
        case .fifty:        return "50"
        case .hundred:      return "100"
        case .twoHundred:   return "200"
        case .fiveHundred:  return "500"
        case .twoThousand:  return "2000"
        }
    }

    var lightTint: Color {
        switch self {
        case .ten:          return Color(hex: "6B3A28")
        case .fifty:        return Color(hex: "4A5A8A")
        case .hundred:      return Color(hex: "7A6BA0")
        case .twoHundred:   return Color(hex: "C85A20")
        case .fiveHundred:  return Color(hex: "4A6B5A")
        case .twoThousand:  return Color(hex: "B040A0")
        }
    }

    var darkTint: Color {
        switch self {
        case .ten:          return Color(hex: "9B6050")
        case .fifty:        return Color(hex: "6A7AAA")
        case .hundred:      return Color(hex: "9A8BC0")
        case .twoHundred:   return Color(hex: "E87A40")
        case .fiveHundred:  return Color(hex: "6A8B7A")
        case .twoThousand:  return Color(hex: "D060C0")
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
                    .font(.system(size: 9, weight: .medium, design: .monospaced))
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
                    .font(.system(size: 8, weight: .medium, design: .monospaced))
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
        .foregroundColor(.primary)
        .opacity(opacity)
        .allowsHitTesting(false)
    }
}

// MARK: - Micro-text Guilloche Strip

struct MicroTextStrip: View {
    var body: some View {
        let text = "NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत NIVESH ₹ RBI भारत "
        Text(text + text)
            .font(.system(size: 7, weight: .medium, design: .monospaced))
            .foregroundColor(.primary.opacity(0.06))
            .lineLimit(1)
            .frame(maxWidth: .infinity, alignment: .leading)
            .allowsHitTesting(false)
    }
}

// MARK: - Denomination Background

struct DenominationBackground: View {
    let denomination: Denomination
    @Environment(\.colorScheme) var colorScheme

    private var tint: Color {
        colorScheme == .dark ? denomination.darkTint : denomination.lightTint
    }

    var body: some View {
        ZStack {
            PaperTexture()

            // Denomination color wash
            tint
                .opacity(colorScheme == .dark ? 0.055 : 0.038)
                .ignoresSafeArea()
                .allowsHitTesting(false)

            // RBI seal — trailing edge, partially clipped like a real note stamp
            HStack {
                Spacer()
                RBISealBackground(opacity: colorScheme == .dark ? 0.055 : 0.038)
                    .offset(x: 60)
            }
            .ignoresSafeArea()

            // Micro-text strip at bottom
            VStack {
                Spacer()
                MicroTextStrip()
                    .padding(.bottom, 4)
            }
            .ignoresSafeArea()
        }
    }
}
