import SwiftUI

// MARK: - One-time Home ask for usage analytics (I47)
//
// Neutral, free and informed consent (DPDP s.6): equal "Allow" and "Not now" buttons, nothing
// pre-selected. "Not now" records nothing on the server and the card never returns for that
// user on this device. The toggle in Your Data stays available.

struct AnalyticsConsentCard: View {
    @EnvironmentObject var authManager: AuthManager
    @ObservedObject private var flags = RemoteFlags.shared
    @StateObject private var vm = PrivacyCenterViewModel()
    @State private var answered = false

    private var userKey: String? {
        authManager.currentUser.map { String($0.userId) }
    }

    var body: some View {
        if let key = userKey,
           flags.isOn(RemoteFlags.analyticsKey),
           !flags.isOn(RemoteFlags.analyticsConsentedKey),
           !answered,
           AnalyticsAskStore.shouldAsk(userKey: key) {
            AnalyticsAskContent(
                vm: vm,
                retentionDays: flags.analyticsRetentionDays,
                onAllow: {
                    Task {
                        if await vm.setAnalytics(true) {
                            AnalyticsAskStore.markAnswered(userKey: key)
                            answered = true
                        }
                    }
                },
                onNotNow: {
                    AnalyticsAskStore.markAnswered(userKey: key)
                    answered = true
                }
            )
        } else {
            EmptyView()
        }
    }
}

private struct AnalyticsAskContent: View {
    @ObservedObject var vm: PrivacyCenterViewModel
    let retentionDays: Int?
    let onAllow: () -> Void
    let onNotNow: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("HELP IMPROVE NIVESH")
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
            Text(PrivacyCenterViewModel.analyticsCaption(retentionDays: retentionDays))
                .font(Theme.engravedSerif(size: 13))
                .foregroundStyle(Theme.inkPrimary)
            HStack(spacing: Theme.Spacing.standard) {
                AnalyticsAskButton(title: "Allow", action: onAllow).disabled(vm.analyticsBusy)
                AnalyticsAskButton(title: "Not now", action: onNotNow).disabled(vm.analyticsBusy)
            }
            if let error = vm.analyticsError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12))
                    .foregroundStyle(Theme.bearRed)
            }
        }
        .padding(Theme.cardPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

/// Both answers use this one view, so they cannot drift apart in style or size.
private struct AnalyticsAskButton: View {
    let title: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(Theme.officialStampFont(size: 12))
                .foregroundStyle(Theme.inkPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .background(Theme.canvas)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .accessibilityLabel(title)
    }
}
