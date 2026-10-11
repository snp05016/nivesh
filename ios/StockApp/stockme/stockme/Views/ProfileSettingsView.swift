import SwiftUI

// MARK: - ProfileSettingsView
//
// User profile — display name, email, phone, avatar placeholder.
// The backend `User` model (backend/models/db_models.py) currently only
// stores username/display_name; email and phone have no backend column,
// so they are persisted locally (AppStorage) on this device only.
// Display name + username come from AuthManager.currentUser (server-backed)
// and are read-only: there is no backend profile-update route yet.

struct ProfileSettingsView: View {
    @EnvironmentObject var authManager: AuthManager

    @AppStorage("nivesh_profileEmail") private var email = ""
    @AppStorage("nivesh_profilePhone") private var phone = ""
    @State private var showSavedToast = false

    private var displayName: String { authManager.currentUser?.displayName ?? "" }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    avatarSection
                    detailsSection
                    saveButton
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
        .overlay(alignment: .bottom) { savedToast }
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
            Text("Avatar Placeholder — upload not wired in this demo")
                .font(Theme.serialNumberFont(size: 10))
                .foregroundStyle(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.large)
    }

    // MARK: - Details

    private var detailsSection: some View {
        VStack(spacing: Theme.Spacing.none) {
            ProfileReadOnlyRow(icon: "person.text.rectangle", title: "Display Name", value: displayName)
            GuillocheDivider()
            ProfileFieldRow(icon: "at", title: "Email", text: $email, keyboard: .emailAddress)
            GuillocheDivider()
            ProfileFieldRow(icon: "phone", title: "Phone", text: $phone, keyboard: .phonePad)
            GuillocheDivider()
            if let user = authManager.currentUser {
                ProfileReadOnlyRow(icon: "number", title: "Username", value: user.username)
            }
        }
        .banknoteCard()
    }

    // MARK: - Save

    private var saveButton: some View {
        Button {
            HapticManager.selection()
            saveProfile()
        } label: {
            Text("SAVE CHANGES")
                .font(Theme.officialStampFont(size: 11))
                .foregroundStyle(Theme.canvas)
                .frame(maxWidth: .infinity)
                .padding(.vertical, Theme.Spacing.standard)
                .background(Theme.securityGoldGradient)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        }
        .buttonStyle(EKPressStyle())
    }

    private func saveProfile() {
        // Email/phone are AppStorage-backed (already written on edit); nothing
        // is sent to the server, so the confirmation says so.
        withAnimation { showSavedToast = true }
        A11y.announce("Saved on this device")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
            withAnimation { showSavedToast = false }
        }
    }

    @ViewBuilder
    private var savedToast: some View {
        if showSavedToast {
            Text("SAVED ON THIS DEVICE")
                .font(Theme.officialStampFont(size: 10))
                .foregroundStyle(Theme.canvas)
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.standard)
                .background(Theme.bullGreen)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.pill))
                .padding(.bottom, Theme.Spacing.large)
                .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }
}

// MARK: - Reusable Field Rows (private to this file)

private struct ProfileFieldRow: View {
    let icon: String
    let title: String
    @Binding var text: String
    var keyboard: UIKeyboardType = .default

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
                TextField(title, text: $text)
                    .font(Theme.engravedSerif(size: 15))
                    .foregroundStyle(Theme.inkPrimary)
                    .keyboardType(keyboard)
                    .autocorrectionDisabled()
            }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
    }
}

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
