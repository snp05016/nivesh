import SwiftUI

// MARK: - Delete Account (FINSEC-03, App Store 5.1.1(v))

/// In-app account deletion. Re-authenticates with the password, schedules the
/// backend erasure (compliance_service.erase_user after a 7-day grace period)
/// and signs out. Reopening it while a request is pending offers cancellation.
struct DeleteAccountSheet: View {
    private enum Phase { case loading, form, scheduled }

    @EnvironmentObject var authManager: AuthManager
    @Environment(\.dismiss) private var dismiss

    @State private var phase: Phase = .loading
    @State private var password = ""
    @State private var isBusy = false
    @State private var errorText: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    switch phase {
                    case .loading:
                        ProgressView().tint(Theme.securityGold).frame(maxWidth: .infinity)
                    case .form:
                        DeleteAccountForm(password: $password, isBusy: isBusy, errorText: errorText) {
                            Task { await deleteAccount() }
                        }
                    case .scheduled:
                        DeletionScheduledCard(isBusy: isBusy, errorText: errorText) {
                            Task { await cancelDeletion() }
                        }
                    }
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Delete Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") { dismiss() }.foregroundStyle(Theme.securityGold)
                }
            }
            .task { await loadStatus() }
        }
    }

    private func loadStatus() async {
        let status = try? await NetworkManager.shared.fetchDeletionStatus()
        phase = status?.status == "pending" ? .scheduled : .form
    }

    private func deleteAccount() async {
        isBusy = true
        defer { isBusy = false }
        do {
            _ = try await NetworkManager.shared.requestAccountDeletion(password: password)
            HapticManager.success()
            password = ""
            dismiss()
            authManager.logout()
        } catch NetworkError.serverError(403, _) {
            errorText = "Incorrect password."
        } catch {
            errorText = error.localizedDescription
        }
    }

    private func cancelDeletion() async {
        isBusy = true
        defer { isBusy = false }
        do {
            try await NetworkManager.shared.cancelAccountDeletion()
            HapticManager.success()
            errorText = nil
            phase = .form
        } catch {
            errorText = error.localizedDescription
        }
    }
}

private struct DeleteAccountForm: View {
    @Binding var password: String
    let isBusy: Bool
    let errorText: String?
    let onDelete: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Deleting your account permanently erases your holdings, transactions, watchlists, alerts, linked bank accounts, loan and deposit records and device registrations 7 days after you confirm.")
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
            Text("Consent and audit records are kept as legal evidence with your IP address removed, and forum posts remain under \"Deleted user\". You will be signed out now; sign back in within 7 days and open this screen to cancel.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundStyle(Theme.inkSecondary)
            SecureField("Password", text: $password)
                .textContentType(.password)
                .accessibilityLabel("Password")
                .foregroundStyle(Theme.inkPrimary)
                .padding(Theme.Spacing.card)
                .banknoteCard()
            if let errorText {
                Text(errorText).font(Theme.engravedSerif(size: 12, relativeTo: .caption)).foregroundStyle(Theme.bearRed)
            }
            Button(role: .destructive, action: onDelete) {
                Text(isBusy ? "DELETING…" : "DELETE MY ACCOUNT")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.canvas)
                    .frame(maxWidth: .infinity)
                    .padding(Theme.Spacing.card)
                    .background(Theme.bearRed, in: RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }
            .buttonStyle(EKPressStyle())
            .disabled(password.isEmpty || isBusy)
            .opacity(password.isEmpty || isBusy ? 0.5 : 1)
        }
    }
}

private struct DeletionScheduledCard: View {
    let isBusy: Bool
    let errorText: String?
    let onCancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Your account is scheduled for permanent deletion 7 days after you requested it.")
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
            if let errorText {
                Text(errorText).font(Theme.engravedSerif(size: 12, relativeTo: .caption)).foregroundStyle(Theme.bearRed)
            }
            Button(action: onCancel) {
                Text(isBusy ? "CANCELLING…" : "KEEP MY ACCOUNT")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.canvas)
                    .frame(maxWidth: .infinity)
                    .padding(Theme.Spacing.card)
                    .background(Theme.securityGold, in: RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
            }
            .buttonStyle(EKPressStyle())
            .disabled(isBusy)
        }
    }
}
