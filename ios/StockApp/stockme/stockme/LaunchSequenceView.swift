import SwiftUI

struct LaunchSequenceView: View {
    let onComplete: () -> Void

    @State private var notesOut = false
    @State private var logoScaled = false
    @State private var logoVisible = false

    private let noteCount = 5

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()

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
                    .font(Theme.engravedSerif(size: 80, weight: .bold, relativeTo: .largeTitle))
                    .foregroundStyle(
                        LinearGradient(
                        colors: [Theme.securityGoldLight, Theme.securityGold],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )
                    .shadow(color: Theme.securityGoldLight.opacity(0.5), radius: 16, x: 0, y: 0)

                Text("निवेश")
                    .font(Theme.hindiFont(size: 20, relativeTo: .title3))
                    .foregroundStyle(Theme.securityGold.opacity(0.85))
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
    private var colors: [Color] {
        [
            Theme.NoteTint.ten,
            Theme.NoteTint.fifty,
            Theme.NoteTint.hundred,
            Theme.NoteTint.twoHundred,
            Theme.NoteTint.fiveHundred,
        ]
    }

    var body: some View {
        RoundedRectangle(cornerRadius: 10)
            .fill(colors[index])
            .frame(width: 140, height: 70)
            .overlay(
                VStack(spacing: 2) {
                    Text("₹\(denominations[index])")
                        .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                        .foregroundStyle(.white)
                    Text("RESERVE BANK")
                        .font(Theme.monoTabular(size: 7, relativeTo: .caption2))
                        .foregroundStyle(.white.opacity(0.7))
                }
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
            )
            .shadow(color: colors[index].opacity(0.5), radius: 10, x: 0, y: 3)
    }
}


