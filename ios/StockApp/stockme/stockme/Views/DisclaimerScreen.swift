import SwiftUI

struct DisclaimerScreen: View {
    let onAccept: () -> Void
    @State private var showTerms = false

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()

            VStack(spacing: Theme.Spacing.none) {
                Spacer()

                VStack(spacing: Theme.Spacing.large) {
                    // Warning Stamp
                    BanknoteSignalBadge(text: "IMPORTANT", color: Theme.securityGold, rotation: -4)
                        .scaleEffect(1.2)

                    VStack(spacing: Theme.Spacing.small) {
                        Text("महत्वपूर्ण सूचना")
                            .font(.caption2.weight(.bold))
                            .foregroundStyle(Theme.inkSecondary)
                        Text("DISCLAIMER")
                            .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    .staggerAppear(delay: 0.1)

                    VStack(spacing: Theme.Spacing.card) {
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
                    .padding(.horizontal, Theme.Spacing.medium)
                }
                .padding(Theme.Spacing.xLarge)
                .banknoteCard()
                .padding(.horizontal, Theme.Spacing.screen)
                .staggerAppear(delay: 0.1)

                Spacer()

                VStack(spacing: Theme.Spacing.card) {
                    Button(action: { HapticManager.selection(); onAccept() }) { Text("I ACKNOWLEDGE & CONTINUE")
                            .font(Theme.labelStyle)
                            .foregroundStyle(Theme.canvas)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.screen)
                            .background(Theme.inkPrimary)
                            .banknoteCard()
                    }

                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("By continuing you agree to the")
                            .foregroundStyle(Theme.inkSecondary.opacity(0.6))
                            .multilineTextAlignment(.center)
                        Button { showTerms = true } label: {
                            Text("Terms of Use")
                                .underline()
                                .foregroundStyle(Theme.securityGold)
                        }
                        .buttonStyle(.plain)
                    }
                    .font(.caption2.weight(.bold))
                    .padding(.horizontal, Theme.Spacing.large)
                }
                .padding(.horizontal, Theme.Spacing.large)
                .padding(.bottom, Theme.Spacing.xLarge)
                .staggerAppear(delay: 0.5)
            }
        }
        .sheet(isPresented: $showTerms) {
            NavigationStack { DisclosureDetailView(key: .termsOfUse) }
                .presentationDragIndicator(.visible)
        }
    }
}

private struct DisclaimerBulletin: View {
    let icon: String
    let text: String
    let delay: Double

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary.opacity(0.4))
                .frame(width: 20)
                .padding(.top, Theme.Spacing.xSmall)
            Text(text.uppercased())
                .font(.caption2.weight(.bold))
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(2)
        }
        .staggerAppear(delay: delay)
    }
}
