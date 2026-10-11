import SwiftUI

// MARK: - ProfileSettingsView
//
// User profile — display name and username from AuthManager.currentUser
// (server-backed). Read-only: there is no backend profile-update route yet,
// so nothing here pretends to save (UX-18 / GH #692).

struct ProfileSettingsView: View {
    @EnvironmentObject var authManager: AuthManager

    private var displayName: String { authManager.currentUser?.displayName ?? "" }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    avatarSection
                    detailsSection
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
    }

    // MARK: - Avatar

    private var avatarSection: some View {
        VStack(spacing: Theme.Spacing.standard) {
            ZStack {
                Circle().fill(Theme.securityGold).frame(width: 84, height: 84)
                    .shadow(color: Theme.securityGold.opacity(0.3), radius: 10, y: 4)
                Text(String(displayName.prefix(1)).uppercased())
                    .font(Theme.serialNumberFont(size: 32).weight(.semibold))
                    .foregroundStyle(Theme.canvas)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.large)
    }

    // MARK: - Details

    private var detailsSection: some View {
        VStack(spacing: Theme.Spacing.none) {
            ProfileReadOnlyRow(icon: "person.text.rectangle", title: "Display Name", value: displayName)
            if let user = authManager.currentUser {
                GuillocheDivider()
                ProfileReadOnlyRow(icon: "number", title: "Username", value: user.username)
            }
        }
        .banknoteCard()
    }
}

// MARK: - Read-only Row (private to this file)

private struct ProfileReadOnlyRow: View {
    let icon: String
    let title: String
    let value: String

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: icon)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.inkSecondary.opacity(0.7))
                .frame(width: 24)
            Text(title.uppercased())
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            Text(value)
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(Theme.inkTertiary)
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}
