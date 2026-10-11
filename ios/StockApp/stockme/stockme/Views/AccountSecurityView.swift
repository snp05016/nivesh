import SwiftUI

// MARK: - AccountSecurityView
//
// KYC & device-binding entry point, password change and "sign out of all
// devices" (AUTH-13: POST /api/v1/auth/change-password and /api/v1/auth/logout
// revoke every token server-side). Two-factor authentication has no backend
// yet, so the screen says so instead of simulating it.

struct AccountSecurityView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    kycDeviceSecurityLink
                    PasswordChangeCard()
                    SignOutEverywhereCard()
                    Text("Two-factor authentication is not available yet.")
                        .font(Theme.engravedSerif(size: 13))
                        .foregroundStyle(Theme.inkSecondary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Account Security")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - KYC & Device Security (real, already-merged /api/kyc/... endpoints)

    private var kycDeviceSecurityLink: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("KYC & SIM-BINDING", hindi: "केवाईसी और डिवाइस बंधन")
            NavigationLink(destination: AccountSecurityStatusView()) {
                HStack(spacing: Theme.Spacing.standard) {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(Theme.securityGold.opacity(0.08)).frame(width: 32, height: 32)
                        Image(systemName: "checkmark.shield.fill")
                            .font(.subheadline.weight(.medium)).foregroundStyle(Theme.securityGold.opacity(0.7))
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("KYC CONSENTS & DEVICE BINDING")
                            .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                        Text("View consent status, bind this device (SIM-binding), verify loan/FD eligibility")
                            .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.inkTertiary)
                }
                .padding(.vertical, Theme.Spacing.standard)
                .padding(.horizontal, Theme.Spacing.card)
                .contentShape(Rectangle())
            }
            .buttonStyle(EKPressStyle())
            .banknoteCard()
        }
    }

    private func sectionHeader(_ title: String, hindi: String) -> some View {
        HStack(alignment: .bottom, spacing: Theme.Spacing.tight) {
            Text(hindi).font(Theme.hindiFont(size: 9)).foregroundStyle(Theme.inkSecondary)
            Text(title).font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
        }
        .padding(.horizontal, Theme.Spacing.small)
    }
}

// MARK: - Password change (AUTH-13)

/// Changes the password server-side; every existing session, this one included,
/// is revoked, so the user signs in again with the new password.
private struct PasswordChangeCard: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var current = ""
    @State private var new = ""
    @State private var confirm = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var showSignInAgain = false

    private var canSubmit: Bool { !current.isEmpty && new.count >= 8 && new == confirm && !isSaving }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("CHANGE PASSWORD")
                .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
            SecureField("Current password", text: $current).textContentType(.password)
            SecureField("New password (min 8 characters)", text: $new).textContentType(.newPassword)
            SecureField("Confirm new password", text: $confirm).textContentType(.newPassword)
            if !confirm.isEmpty && new != confirm {
                Text("Passwords do not match.").font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
            }
            if let errorMessage {
                Text(errorMessage).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
            }
            Button(isSaving ? "UPDATING..." : "UPDATE PASSWORD") { submit() }
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(canSubmit ? Theme.securityGold : Theme.inkTertiary)
                .disabled(!canSubmit)
                .buttonStyle(EKPressStyle())
        }
        .font(Theme.engravedSerif(size: 14))
        .foregroundStyle(Theme.inkPrimary)
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .alert("Password changed", isPresented: $showSignInAgain) {
            Button("OK") { authManager.logout() }
        } message: {
            Text("Please sign in again with your new password.")
        }
    }

    private func submit() {
        isSaving = true
        errorMessage = nil
        Task {
            defer { isSaving = false }
            do {
                try await NetworkManager.shared.changePassword(current: current, new: new)
                showSignInAgain = true
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

// MARK: - Sign out everywhere (AUTH-13)

private struct SignOutEverywhereCard: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var confirming = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Button("SIGN OUT OF ALL DEVICES") { confirming = true }
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.bearRed)
                .buttonStyle(EKPressStyle())
            Text("Ends every session, including this one.")
                .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            if let errorMessage {
                Text(errorMessage).font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.bearRed)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(Theme.Spacing.card)
        .banknoteCard()
        .confirmationDialog("Sign out of all devices?", isPresented: $confirming, titleVisibility: .visible) {
            Button("Sign Out Everywhere", role: .destructive) { signOutEverywhere() }
        }
    }

    private func signOutEverywhere() {
        errorMessage = nil
        Task {
            do {
                try await NetworkManager.shared.logoutAllSessions()
                authManager.logout()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
