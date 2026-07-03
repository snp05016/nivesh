import SwiftUI

// MARK: - AccountSecurityView
//
// Change password, active sessions list, 2FA toggle placeholder.
// MOCK — simulated for demo purposes. There is no backend endpoint for
// password change, session listing, or 2FA in this repo (auth.router only
// exposes /login and /register — backend/routers/auth.py), so this screen
// simulates the flows entirely client-side: change-password shows a fake
// success state, "active sessions" is a hand-seeded local list keyed off
// this device, and the 2FA toggle is a persisted placeholder with no real
// TOTP/SMS enrollment behind it.

struct AccountSecurityView: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var confirmPassword = ""
    @State private var isChangingPassword = false
    @State private var changePasswordMessage: String?
    @State private var changePasswordSucceeded = false

    @AppStorage("nivesh_twoFactorEnabled") private var twoFactorEnabled = false
    @State private var show2FAExplainer = false

    private var thisDeviceSession: MockSession {
        MockSession(
            id: "current",
            deviceName: UIDevice.current.name,
            location: "This Device",
            lastActive: "Active now",
            isCurrent: true
        )
    }

    private var otherSessions: [MockSession] {
        // MOCK DATA — simulated for demo purposes, not a real session store.
        [
            MockSession(id: "1", deviceName: "iPhone 15 Pro", location: "Mumbai, IN", lastActive: "2 hours ago", isCurrent: false),
            MockSession(id: "2", deviceName: "Chrome on MacBook Pro", location: "Bengaluru, IN", lastActive: "Yesterday", isCurrent: false),
        ]
    }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    kycDeviceSecurityLink
                    changePasswordSection
                    twoFactorSection
                    sessionsSection
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

    // MARK: - Change Password

    private var changePasswordSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("CHANGE PASSWORD", hindi: "पासवर्ड बदलें")
            VStack(spacing: Theme.Spacing.none) {
                SecureFieldRow(icon: "lock", title: "Current Password", text: $currentPassword)
                GuillocheDivider()
                SecureFieldRow(icon: "lock.rotation", title: "New Password", text: $newPassword)
                GuillocheDivider()
                SecureFieldRow(icon: "lock.rotation", title: "Confirm New Password", text: $confirmPassword)
            }
            .banknoteCard()

            if let message = changePasswordMessage {
                Text(message)
                    .font(Theme.serialNumberFont(size: 11))
                    .foregroundStyle(changePasswordSucceeded ? Theme.bullGreen : Theme.bearRed)
            }

            Button {
                HapticManager.selection()
                submitPasswordChange()
            } label: {
                Text(isChangingPassword ? "UPDATING…" : "UPDATE PASSWORD")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.canvas)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.securityGoldGradient)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
            }
            .buttonStyle(EKPressStyle())
            .disabled(isChangingPassword || !canSubmitPasswordChange)
            .opacity(canSubmitPasswordChange ? 1.0 : 0.5)
        }
    }

    private var canSubmitPasswordChange: Bool {
        !currentPassword.isEmpty && newPassword.count >= 8 && newPassword == confirmPassword
    }

    private func submitPasswordChange() {
        // MOCK - simulated for demo purposes: no backend endpoint exists to
        // actually rotate the password hash, so this just simulates a
        // network round-trip and reports success/failure locally.
        isChangingPassword = true
        changePasswordMessage = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) {
            isChangingPassword = false
            changePasswordSucceeded = true
            changePasswordMessage = "Password updated (demo — not sent to server)."
            currentPassword = ""; newPassword = ""; confirmPassword = ""
        }
    }

    // MARK: - Two-Factor Auth

    private var twoFactorSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("TWO-FACTOR AUTHENTICATION", hindi: "दो-चरणीय सत्यापन")
            VStack(spacing: Theme.Spacing.none) {
                HStack(spacing: Theme.Spacing.standard) {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .fill(Theme.securityGold.opacity(0.08)).frame(width: 32, height: 32)
                        Image(systemName: "checkmark.shield.fill")
                            .font(.subheadline.weight(.medium)).foregroundStyle(Theme.securityGold.opacity(0.7))
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text("ENABLE 2FA")
                            .font(Theme.officialStampFont(size: 9)).foregroundStyle(Theme.inkPrimary)
                        Text("Placeholder — no TOTP/SMS enrollment wired in this demo")
                            .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
                    }
                    Spacer()
                    Toggle("", isOn: $twoFactorEnabled)
                        .labelsHidden()
                        .tint(Theme.securityGold)
                        .onChange(of: twoFactorEnabled) { _, newValue in
                            HapticManager.selection()
                            if newValue { show2FAExplainer = true }
                        }
                }
                .padding(.vertical, Theme.Spacing.standard)
                .padding(.horizontal, Theme.Spacing.card)
            }
            .banknoteCard()
        }
        .banknoteDialog(
            "2FA — Demo Placeholder",
            isPresented: $show2FAExplainer,
            message: "Two-factor authentication is a placeholder in this demo app — no real TOTP/SMS setup happens.",
            buttons: [.init("Got it")]
        )
    }

    // MARK: - Active Sessions

    private var sessionsSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            sectionHeader("ACTIVE SESSIONS", hindi: "सक्रिय सत्र")
            VStack(spacing: Theme.Spacing.none) {
                SessionRow(session: thisDeviceSession)
                ForEach(otherSessions) { session in
                    GuillocheDivider()
                    SessionRow(session: session)
                }
            }
            .banknoteCard()

            Text("Session data is illustrative for this demo — the backend has no session/device registry to revoke against.")
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
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

// MARK: - Mock Session Model

private struct MockSession: Identifiable {
    let id: String
    let deviceName: String
    let location: String
    let lastActive: String
    let isCurrent: Bool
}

// MARK: - Reusable Rows (private to this file)

private struct SecureFieldRow: View {
    let icon: String
    let title: String
    @Binding var text: String

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: icon)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.securityGold.opacity(0.7))
                .frame(width: 24)
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(title.uppercased())
                    .font(Theme.officialStampFont(size: 8))
                    .foregroundStyle(Theme.inkTertiary)
                SecureField(title, text: $text)
                    .font(Theme.engravedSerif(size: 15))
                    .foregroundStyle(Theme.inkPrimary)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

private struct SessionRow: View {
    let session: MockSession

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                    .fill((session.isCurrent ? Theme.bullGreen : Theme.inkSecondary).opacity(0.08))
                    .frame(width: 32, height: 32)
                Image(systemName: session.isCurrent ? "checkmark.circle.fill" : "iphone")
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle((session.isCurrent ? Theme.bullGreen : Theme.inkSecondary).opacity(0.7))
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(session.deviceName)
                    .font(Theme.engravedSerif(size: 13)).foregroundStyle(Theme.inkPrimary)
                Text("\(session.location) · \(session.lastActive)")
                    .font(Theme.serialNumberFont(size: 10)).foregroundStyle(Theme.inkTertiary)
            }
            Spacer()
            if session.isCurrent {
                Text("THIS DEVICE")
                    .font(Theme.officialStampFont(size: 7))
                    .foregroundStyle(Theme.bullGreen)
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}
