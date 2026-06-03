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
                        .font(Theme.engravedSerif(size: 48, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                }
                .staggerAppear(delay: 0.1)
                .padding(.bottom, 32)

                // App name
                VStack(spacing: 8) {
                    Text("निवेश / NIVESH")
                        .font(Theme.engravedSerif(size: 44, weight: .bold))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Text("OFFICIAL FINANCIAL TENDER")
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.inkSecondary)
                }
                .staggerAppear(delay: 0.2)

                // Tagline
                Text("Invest with Official Clarity")
                    .font(Theme.engravedSerif(size: 16))
                    .italic()
                    .foregroundColor(Theme.inkSecondary)
                    .padding(.top, 16)
                    .staggerAppear(delay: 0.3)

                Spacer()

                // Features (Presented as Registry Bulletins)
                VStack(spacing: 20) {
                    FeatureRegistryRow(icon: "shield.righthalf.filled", text: "AI-verified analysis for the Indian market", delay: 0.5)
                    FeatureRegistryRow(icon: "indianrupeesign", text: "Secure real-time P&L tracking", delay: 0.6)
                    FeatureRegistryRow(icon: "doc.text.fill", text: "Official archives and record keeping", delay: 0.7)
                }
                .padding(.horizontal, 40)
                .padding(.bottom, 48)

                // CTA (The Official Access Button)
                Button(action: onContinue) {
                    Text("ENTER REGISTRY")
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.canvas)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 20)
                        .background(Theme.inkPrimary)
                        .banknoteCard()
                }
                .padding(.horizontal, 24)
                .padding(.bottom, 48)
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
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(Theme.securityGold)
                .frame(width: 32)
            Text(text.uppercased())
                .font(.system(size: 11, weight: .bold))
                .foregroundColor(Theme.inkSecondary)
            Spacer()
        }
        .staggerAppear(delay: delay)
    }
}
