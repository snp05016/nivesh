import SwiftUI

struct DisclaimerScreen: View {
    let onAccept: () -> Void
    @State private var shownDocument: DisclosureKey?

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()

            VStack(spacing: Theme.Spacing.none) {
                // Scrolls only when Dynamic Type makes the card taller than the screen.
                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        Text("Before you start")
                            .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                            .foregroundStyle(Theme.inkPrimary)
                            .accessibilityAddTraits(.isHeader)
                            .staggerAppear(delay: 0.1)

                        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                            DisclaimerBulletin(
                                icon: "info.circle.fill",
                                text: "Nivesh is not registered with SEBI as an investment adviser or research analyst. Nothing in the app is a recommendation to buy, sell or hold any security.",
                                delay: 0.2
                            )
                            DisclaimerBulletin(
                                icon: "chart.xyaxis.line",
                                text: "Stock reports describe the past using public market data. Figures can be delayed or incomplete, and past patterns can change.",
                                delay: 0.3
                            )
                            DisclaimerBulletin(
                                icon: "person.fill.questionmark",
                                text: "Investments in the securities market are subject to market risks. Consider speaking to a SEBI-registered investment adviser before you invest.",
                                delay: 0.4
                            )
                        }
                        .padding(.horizontal, Theme.Spacing.medium)
                    }
                    .padding(Theme.Spacing.xLarge)
                    .banknoteCard()
                    .padding(.horizontal, Theme.Spacing.screen)
                    .padding(.vertical, Theme.Spacing.large)
                    .staggerAppear(delay: 0.1)
                }
                .scrollBounceBehavior(.basedOnSize)
                .defaultScrollAnchor(.center)

                VStack(spacing: Theme.Spacing.card) {
                    Button(action: { HapticManager.selection(); onAccept() }) { Text("I understand")
                            .font(Theme.labelStyle)
                            .foregroundStyle(Theme.canvas)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.screen)
                            .background(Theme.inkPrimary)
                            .banknoteCard()
                    }

                    VStack(spacing: Theme.Spacing.xSmall) {
                        Text("By continuing you agree to the Terms of Use and Privacy Policy:")
                            .foregroundStyle(Theme.inkSecondary.opacity(0.6))
                            .multilineTextAlignment(.center)
                        HStack(spacing: Theme.Spacing.xSmall) {
                            ForEach([DisclosureKey.termsOfUse, .privacyPolicy]) { doc in
                                Button { shownDocument = doc } label: {
                                    Text(doc.displayTitle)
                                        .underline()
                                        .foregroundStyle(Theme.securityGold)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                    .font(.caption2.weight(.bold))
                    .padding(.horizontal, Theme.Spacing.large)
                }
                .padding(.horizontal, Theme.Spacing.large)
                .padding(.bottom, Theme.Spacing.xLarge)
                .staggerAppear(delay: 0.5)
            }
        }
        .sheet(item: $shownDocument) { doc in
            NavigationStack { DisclosureDetailView(key: doc) }
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
                .accessibilityHidden(true)
            Text(text)
                .font(.subheadline)
                .foregroundStyle(Theme.inkSecondary)
                .fixedSize(horizontal: false, vertical: true)
                .lineSpacing(2)
        }
        .accessibilityElement(children: .combine)
        .staggerAppear(delay: delay)
    }
}
