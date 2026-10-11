import SwiftUI

/// Shown when AnalysisScreen has no report, no running job and no error.
/// Running an analysis costs server-side AI spend, so it starts only on an explicit tap.
struct AnalysisIdleStateView: View {
    let ticker: String
    let exchange: String
    let quickInfo: QuickInfo?
    let isRunning: Bool
    let onRun: () -> Void
    /// Set when a saved report exists (e.g. after dismissing "Cached Report Found").
    var onViewSaved: (() -> Void)? = nil

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.screen) {
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    Text(ticker)
                        .font(Theme.serialNumberFont(size: 24))
                        .foregroundStyle(Theme.inkPrimary)
                    if let price = quickInfo?.price {
                        HStack(spacing: Theme.Spacing.medium) {
                            Text(IndianFormatter.price(price))
                                .font(Theme.serialNumberFont(size: 20))
                                .foregroundStyle(Theme.inkPrimary)
                            ChangeBadge(value: quickInfo?.changePercent ?? 0)
                        }
                    }
                    GuillocheDivider()
                    Text(onViewSaved == nil ? "No saved AI report for this stock yet." : "Run a fresh AI report, or open the saved one.")
                        .font(Theme.engravedSerif(size: 15, weight: .bold))
                        .foregroundStyle(Theme.inkPrimary)
                    Text("Runs a full multi-agent AI analysis on our servers. Takes a few minutes and counts toward your daily analysis limit.")
                        .font(.footnote)
                        .foregroundStyle(Theme.inkSecondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(Theme.Spacing.screen)
                .banknoteCard()

                Button(action: onRun) {
                    HStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: "sparkles")
                        Text("RUN ANALYSIS")
                    }
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.inkPrimary)
                    .padding(.vertical, Theme.Spacing.standard)
                    .frame(maxWidth: .infinity)
                    .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.small).stroke(Theme.inkPrimary, lineWidth: 1))
                }
                .disabled(isRunning)
                .opacity(isRunning ? 0.4 : 1.0)
                .accessibilityLabel("Run analysis")

                if let onViewSaved {
                    Button {
                        HapticManager.selection()
                        onViewSaved()
                    } label: {
                        Text("VIEW SAVED REPORT")
                            .font(Theme.officialStampFont(size: 11))
                            .foregroundStyle(Theme.securityGold)
                            .padding(.vertical, Theme.Spacing.standard)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(EKPressStyle())
                    .accessibilityLabel("View saved report")
                }

                NavigationLink(value: StockProfileDest(ticker: ticker, exchange: exchange)) {
                    Text("View stock profile")
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(Theme.securityGold)
                }
                .buttonStyle(EKPressStyle())
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.top, Theme.screenPadding)
        }
    }
}
