import SwiftUI

// MARK: - Your Data (I06 privacy center)
//
// A rights surface (DPDP s.11, Rule 14), like account deletion: no feature flag can hide it.
// Pushed from Settings, so it has no NavigationStack of its own.

struct PrivacyCenterView: View {
    @EnvironmentObject var authManager: AuthManager
    @ObservedObject private var flags = RemoteFlags.shared
    @StateObject private var vm = PrivacyCenterViewModel()
    @State private var showDeleteAccount = false

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.card) {
                PrivacyStoredDataCard()
                PrivacyExportCard(vm: vm)
                if flags.isOn(RemoteFlags.analyticsKey) {
                    PrivacyAnalyticsCard(vm: vm, retentionDays: flags.analyticsRetentionDays)
                }
                PrivacyLinksCard(showDeleteAccount: $showDeleteAccount)
            }
            .padding(.horizontal, Theme.screenPadding)
            .padding(.vertical, Theme.Spacing.large)
        }
        .background(Theme.canvasDeep.ignoresSafeArea())
        .navigationTitle("Your Data")
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: flags.flags) { _, latest in
            vm.syncAnalytics(consented: latest[RemoteFlags.analyticsConsentedKey] ?? false)
        }
        .sheet(isPresented: $showDeleteAccount) {
            DeleteAccountSheet().environmentObject(authManager)
        }
    }
}

// MARK: - WHAT WE STORE

private struct PrivacyStoredDataCard: View {
    // Keep in step with STORED_DATA_ROWS in backend/services/privacy_export.py (a test compares them).
    private let rows: [String] = [
        "Your account: username, display name, settings and subscription",
        "Holdings, transactions, watchlists, alerts and journal notes you add, and the values and tax reports we calculate from them",
        "Loan, deposit, bank-account and finance-tracker records, if you use those features",
        "Posts, votes, reports and blocks in the community forum",
        "Your device ID and push token, your consent choices and security records, with the IP address on them",
        "Your notifications, analyses and AI research requests",
        "Usage events, only if you turn on usage analytics",
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("WHAT WE STORE")
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
            ForEach(rows, id: \.self) { row in
                Text(row)
                    .font(Theme.engravedSerif(size: 13))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            Text("AI features send stock names and percentage moves to our AI providers only if you allow AI processing.")
                .font(Theme.engravedSerif(size: 12))
                .foregroundStyle(Theme.inkSecondary)
        }
        .padding(Theme.cardPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }
}

// MARK: - DOWNLOAD A COPY

private struct PrivacyExportCard: View {
    @ObservedObject var vm: PrivacyCenterViewModel

    private var isPreparing: Bool { vm.exportState == .preparing }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("DOWNLOAD A COPY")
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
            Text("Get a file with the data linked to your account.")
                .font(Theme.engravedSerif(size: 13))
                .foregroundStyle(Theme.inkPrimary)
            Button {
                HapticManager.selection()
                Task { await vm.exportData() }
            } label: {
                Text("Prepare my data file")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.inkPrimary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.canvas)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            }
            .disabled(isPreparing)
            .accessibilityLabel("Prepare my data file")
            PrivacyExportStatus(state: vm.exportState)
        }
        .padding(Theme.cardPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }
}

private struct PrivacyExportStatus: View {
    let state: PrivacyCenterViewModel.ExportState

    var body: some View {
        switch state {
        case .idle:
            EmptyView()
        case .preparing:
            HStack(spacing: Theme.Spacing.medium) {
                ProgressView().tint(Theme.securityGold)
                Text("Preparing your file…")
                    .font(Theme.engravedSerif(size: 13))
                    .foregroundStyle(Theme.inkSecondary)
            }
        case .ready(let url):
            ShareLink(item: url) {
                Label("Save or share file", systemImage: "square.and.arrow.up")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.securityGold)
            }
        case .failed(let message):
            Text(message)
                .font(Theme.engravedSerif(size: 13))
                .foregroundStyle(Theme.bearRed)
        }
    }
}

// MARK: - USAGE ANALYTICS

private struct PrivacyAnalyticsCard: View {
    @ObservedObject var vm: PrivacyCenterViewModel
    let retentionDays: Int?

    private var toggleBinding: Binding<Bool> {
        Binding(get: { vm.analyticsOn }, set: { on in Task { _ = await vm.setAnalytics(on) } })
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("USAGE ANALYTICS")
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.inkSecondary)
            Toggle("Share usage analytics", isOn: toggleBinding)
                .font(Theme.engravedSerif(size: 14))
                .foregroundStyle(Theme.inkPrimary)
                .tint(Theme.securityGold)
                .disabled(vm.analyticsBusy)
                .accessibilityLabel("Share usage analytics")
            Text(PrivacyCenterViewModel.analyticsCaption(retentionDays: retentionDays))
                .font(Theme.engravedSerif(size: 12))
                .foregroundStyle(Theme.inkSecondary)
            if let error = vm.analyticsError {
                Text(error)
                    .font(Theme.engravedSerif(size: 12))
                    .foregroundStyle(Theme.bearRed)
            }
        }
        .padding(Theme.cardPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }
}

// MARK: - Links

private struct PrivacyLinksCard: View {
    @Binding var showDeleteAccount: Bool

    var body: some View {
        VStack(spacing: 0) {
            PrivacyLinkRow(title: "AI processing and other consents", destination: AccountSecurityView())
            PrivacyLinkRow(title: "Privacy Policy", destination: DisclosureDetailView(key: .privacyPolicy))
            Button {
                HapticManager.selection()
                showDeleteAccount = true
            } label: {
                Text("Delete account")
                    .font(Theme.engravedSerif(size: 14))
                    .foregroundStyle(Theme.bearRed)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.cardPadding)
            }
            .accessibilityLabel("Delete account")
        }
        .frame(maxWidth: .infinity)
        .banknoteCard()
    }
}

private struct PrivacyLinkRow<Destination: View>: View {
    let title: String
    let destination: Destination

    var body: some View {
        NavigationLink(destination: destination) {
            HStack {
                Text(title)
                    .font(Theme.engravedSerif(size: 14))
                    .foregroundStyle(Theme.inkPrimary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(Theme.cardPadding)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        Rectangle().fill(Theme.inkPrimary.opacity(0.06)).frame(height: 0.5)
    }
}
