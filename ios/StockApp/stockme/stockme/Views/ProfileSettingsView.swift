import SwiftUI

// MARK: - ProfileSettingsView
//
// User profile — display name and username from AuthManager.currentUser
// (server-backed). The display name is saved with PATCH /api/v1/me/profile;
// "Saved" appears only after the server confirms it (GH #692).

struct ProfileSettingsView: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var nameDraft = ""
    @State private var isSaving = false
    @State private var saveError: String? = nil
    @State private var didSave = false

    private var displayName: String { authManager.currentUser?.displayName ?? "" }
    private var trimmedDraft: String { nameDraft.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var canSave: Bool { !isSaving && !trimmedDraft.isEmpty && trimmedDraft != displayName }

    var body: some View {
        ZStack {
            Theme.canvasDeep.ignoresSafeArea()
            ScrollView {
                VStack(spacing: Theme.Spacing.large) {
                    avatarSection
                    detailsSection
                    saveSection
                }
                .padding(.horizontal, Theme.Spacing.screen)
                .padding(.vertical, Theme.Spacing.large)
            }
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.large)
        .onAppear { nameDraft = displayName }
    }

    private func saveProfile() {
        let name = trimmedDraft
        isSaving = true
        saveError = nil
        didSave = false
        Task {
            defer { isSaving = false }
            do {
                try await authManager.updateDisplayName(name)
                nameDraft = authManager.currentUser?.displayName ?? name
                didSave = true
            } catch {
                saveError = "Couldn't save your profile. Please try again."
            }
        }
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
            ProfileNameField(text: $nameDraft)
            if let user = authManager.currentUser {
                GuillocheDivider()
                ProfileReadOnlyRow(icon: "number", title: "Username", value: user.username)
            }
        }
        .banknoteCard()
    }

    // MARK: - Save

    private var saveSection: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Button(action: saveProfile) {
                Text(isSaving ? "SAVING…" : "SAVE PROFILE")
                    .font(Theme.officialStampFont(size: 11))
                    .foregroundStyle(Theme.canvas)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.securityGold.opacity(canSave ? 1 : 0.4))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
            }
            .disabled(!canSave)
            if let saveError {
                Text(saveError)
                    .font(Theme.serialNumberFont(size: 12))
                    .foregroundStyle(Theme.bearRed)
            } else if didSave && trimmedDraft == displayName {
                Text("PROFILE SAVED")
                    .font(Theme.officialStampFont(size: 9))
                    .foregroundStyle(Theme.signalEmerald)
            }
        }
    }
}

// MARK: - Editable name row (private to this file)

private struct ProfileNameField: View {
    @Binding var text: String

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "person.text.rectangle")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.inkSecondary.opacity(0.7))
                .frame(width: 24)
            Text("DISPLAY NAME")
                .font(Theme.officialStampFont(size: 9))
                .foregroundStyle(Theme.inkPrimary)
            Spacer()
            TextField("Your name", text: $text)
                .font(Theme.serialNumberFont(size: 12))
                .foregroundStyle(Theme.inkPrimary)
                .multilineTextAlignment(.trailing)
                .textInputAutocapitalization(.words)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .onChange(of: text) { _, newValue in
                    // Same cap as the backend (users.display_name is 100 chars).
                    if newValue.count > 100 { text = String(newValue.prefix(100)) }
                }
        }
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
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
