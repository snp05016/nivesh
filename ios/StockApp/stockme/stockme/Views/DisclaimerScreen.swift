import SwiftUI

struct DisclaimerScreen: View {
    let onAccept: () -> Void

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()

            VStack(spacing: 0) {
                Spacer()

                VStack(spacing: 24) {
                    // Official Warning Stamp
                    BanknoteSignalBadge(text: "OFFICIAL NOTICE", color: Theme.securityGold, rotation: -4)
                        .scaleEffect(1.2)

                    VStack(spacing: 4) {
                        Text("महत्वपूर्ण सूचना")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundColor(Theme.inkSecondary)
                        Text("REGISTRY DISCLAIMER")
                            .font(Theme.engravedSerif(size: 22, weight: .bold))
                            .foregroundColor(Theme.inkPrimary)
                    }
                    .staggerAppear(delay: 0.1)

                    VStack(spacing: 16) {
                        DisclaimerBulletin(
                            icon: "info.circle.fill",
                            text: "This application is for educational purposes only and does not constitute financial advice.",
                            delay: 0.2
                        )
                        DisclaimerBulletin(
                            icon: "person.fill.questionmark",
                            text: "Please consult a SEBI-registered advisor before executing any market transactions.",
                            delay: 0.3
                        )
                        DisclaimerBulletin(
                            icon: "chart.xyaxis.line",
                            text: "AI predictions are speculative and not indicative of future performance.",
                            delay: 0.4
                        )
                    }
                    .padding(.horizontal, 8)
                }
                .padding(32)
                .banknoteCard()
                .padding(.horizontal, 20)
                .staggerAppear(delay: 0.1)

                Spacer()

                VStack(spacing: 16) {
                    Button(action: onAccept) {
                        Text("I ACKNOWLEDGE & CONTINUE")
                            .font(Theme.labelStyle)
                            .foregroundColor(Theme.canvas)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 20)
                            .background(Theme.inkPrimary)
                            .banknoteCard()
                    }

                    Text("By entering the registry you agree to the official terms of use.")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(Theme.inkSecondary.opacity(0.6))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 24)
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 40)
                .staggerAppear(delay: 0.5)
            }
        }
    }
}

private struct DisclaimerBulletin: View {
    let icon: String
    let text: String
    let delay: Double

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(Theme.inkSecondary.opacity(0.4))
                .frame(width: 20)
                .padding(.top, 2)
            Text(text.uppercased())
                .font(.system(size: 10, weight: .bold))
                .foregroundColor(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(2)
        }
        .staggerAppear(delay: delay)
    }
}
