import SwiftUI

// MARK: - AccountSecurityView
//
// KYC & device-binding entry point. Password change, two-factor
// authentication and session management have no backend endpoints yet
// (backend/routers/auth.py exposes only /login and /register), so this screen
// states that plainly instead of simulating those flows client-side.

struct AccountSecurityView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    kycDeviceSecurityLink
                    Text("Password change, two-factor authentication and session management are not available yet.")
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
