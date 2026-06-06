import SwiftUI

struct LaunchSequenceView: View {
    let onComplete: () -> Void

    @State private var notesOut = false
    @State private var logoScaled = false
    @State private var logoVisible = false

    private let noteCount = 5

    var body: some View {
        ZStack {
            Color(hex: "121212").ignoresSafeArea()

            // ── Banknote stack ──────────────────────────────────────
            ZStack {
                ForEach(0..<noteCount, id: \.self) { i in
                    Banknote(index: i)
                        .offset(x: notesOut ? CGFloat((i - 2) * 80 + (i % 2 == 0 ? 200 : -200)) : 0)
                        .rotationEffect(.degrees(notesOut ? Double((i - 2) * 10) : 0))
                        .opacity(notesOut ? 0 : 1)
                        .animation(.easeInOut(duration: 0.7).delay(Double(i) * 0.10), value: notesOut)
                }
            }

            // ── Logo ────────────────────────────────────────────────
            VStack(spacing: 12) {
                Text("₹")
                    .font(.system(size: 80, weight: .bold, design: .serif))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [Color(hex: "D9A63C"), Color(hex: "B8860B")],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .shadow(color: Color(hex: "D9A63C").opacity(0.5), radius: 16, x: 0, y: 0)

                Text("निवेश")
                    .font(.system(size: 20, design: .serif).italic())
                    .foregroundColor(Color(hex: "B8860B").opacity(0.85))
            }
            .scaleEffect(logoScaled ? 1 : 0.5)
            .opacity(logoVisible ? 1 : 0)
            .animation(.easeInOut(duration: 0.6), value: logoScaled)
            .animation(.easeInOut(duration: 0.4), value: logoVisible)
        }
        .onAppear {
            // 1. Notes slide out (0 → 1.0s)
            withAnimation { notesOut = true }

            // 2. Logo fades in + scales up (1.0 → 2.0s)
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                logoVisible = true
                withAnimation(.easeInOut(duration: 0.8)) {
                    logoScaled = true
                }
            }

            // 3. Exit (5.0s)
            DispatchQueue.main.asyncAfter(deadline: .now() + 5.0) {
                onComplete()
            }
        }
    }
}

// MARK: - Banknote Card

private struct Banknote: View {
    let index: Int
    private let denominations = [10, 50, 100, 200, 500]
    private let colors: [Color] = [
        Color(hex: "8B5E3C"),
        Color(hex: "4A6B5A"),
        Color(hex: "7A6BA0"),
        Color(hex: "D4782A"),
        Color(hex: "B040A0"),
    ]

    var body: some View {
        RoundedRectangle(cornerRadius: 10)
            .fill(colors[index])
            .frame(width: 140, height: 70)
            .overlay(
                VStack(spacing: 2) {
                    Text("₹\(denominations[index])")
                        .font(.system(.title3, design: .serif).weight(.bold))
                        .foregroundColor(.white)
                    Text("RESERVE BANK")
                        .font(.system(size: 7, weight: .medium).monospaced())
                        .foregroundColor(.white.opacity(0.7))
                }
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
            .shadow(color: colors[index].opacity(0.5), radius: 10, x: 0, y: 3)
    }
}


