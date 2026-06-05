import SwiftUI

struct OnboardingScreen: View {
    let onContinue: () -> Void

    var body: some View {
        ZStack {
            // The Banknote Canvas
            PaperTexture()

            // Watermarks
            BanknoteWatermark(text: "RESERVE BANK", size: 120, opacity: 0.02, alignment: .topLeading)
            BanknoteWatermark(text: "CENTRAL REGISTRY", size: 100, opacity: 0.02, alignment: .bottomTrailing)

            VStack(spacing: 0) {
                Spacer()

                // Official Medallion
                ZStack {
                    Circle()
                        .stroke(Theme.inkSecondary.opacity(0.3), lineWidth: 1)
                        .frame(width: 100, height: 100)
                    Text("₹")
                        .font(Theme.engravedSerif(size: 48, weight: .bold, relativeTo: .largeTitle))
                        .foregroundStyle(Theme.inkPrimary)
                }
                .staggerAppear(delay: 0.1)
                .padding(.bottom, Theme.Spacing.xLarge)

                // App name
                VStack(spacing: 8) {
                    Text("निवेश / NIVESH")
                        .font(Theme.engravedSerif(size: 44, weight: .bold, relativeTo: .largeTitle))
                        .foregroundStyle(Theme.inkPrimary)
                    
                    Text("OFFICIAL FINANCIAL TENDER")
                        .font(Theme.labelStyle)
                        .foregroundStyle(Theme.inkSecondary)
                }
                .staggerAppear(delay: 0.2)

                // Tagline
                Text("Invest with Official Clarity")
                    .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                    .italic()
                    .foregroundStyle(Theme.inkSecondary)
                    .padding(.top, Theme.Spacing.card)
                    .staggerAppear(delay: 0.3)

                Spacer()

                // Features (Presented as Registry Bulletins)
                VStack(spacing: Theme.Spacing.screen) {
                    FeatureRegistryRow(icon: "shield.righthalf.filled", text: "AI-verified analysis for the Indian market", delay: 0.5)
                    FeatureRegistryRow(icon: "indianrupeesign", text: "Secure real-time P&L tracking", delay: 0.6)
                    FeatureRegistryRow(icon: "doc.text.fill", text: "Official archives and record keeping", delay: 0.7)
                }
                .padding(.horizontal, Theme.Spacing.xLarge)
                .padding(.bottom, 48)

                // CTA (The Official Access Button)
                Button(action: onContinue) {
                    Text("ENTER REGISTRY")
                        .font(Theme.labelStyle)
                        .foregroundStyle(Theme.canvas)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.screen)
                        .background(Theme.inkPrimary)
                        .banknoteCard()
                }
                .padding(.horizontal, Theme.Spacing.large)
                .padding(.bottom, Theme.Spacing.xLarge * 1.5)
                .staggerAppear(delay: 0.8)
            }
        }
    }
}

private struct FeatureRegistryRow: View {
    let icon: String
    let text: String
    let delay: Double

    var body: some View {
        HStack(spacing: Theme.Spacing.card) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundStyle(Theme.securityGold)
                .frame(width: 32)
            Text(text.uppercased())
                .font(.caption.weight(.bold))
                .foregroundStyle(Theme.inkSecondary)
            Spacer()
        }
        .staggerAppear(delay: delay)
    }
}
