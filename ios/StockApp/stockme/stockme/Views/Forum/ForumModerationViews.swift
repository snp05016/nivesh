import SwiftUI

// MARK: - Forum trust & safety (App Store 1.2 UGC controls)
//
// Report / block actions, community guidelines (accepted once before the
// first post or reply), blocked-users list and the moderator contact.
// Backed by NetworkManager+Forum.swift -> /api/forum/posts/{id}/report,
// /block-author, /blocks.

enum ForumModeration {
    /// @AppStorage key — true once the user has agreed to the guidelines.
    static let guidelinesKey = "nivesh_forumGuidelinesAcceptedV1"
    static let detailsLimit = 500
}

// MARK: - Report / Block menu items

/// "Report" + "Block user" items, shared by context menus and the ellipsis menu.
struct ForumContentActions: View {
    let onReport: () -> Void
    let onBlock: () -> Void

    var body: some View {
        Button {
            onReport()
        } label: {
            Label("Report", systemImage: "flag")
        }
        Button(role: .destructive) {
            onBlock()
        } label: {
            Label("Block user", systemImage: "hand.raised")
        }
    }
}

/// Visible ellipsis button with the same items (context menus are not discoverable).
struct ForumContentActionsMenu: View {
    let onReport: () -> Void
    let onBlock: () -> Void

    var body: some View {
        Menu {
            ForumContentActions(onReport: onReport, onBlock: onBlock)
        } label: {
            Image(systemName: "ellipsis")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(Theme.inkTertiary)
                .frame(width: 32, height: 24)
                .contentShape(Rectangle())
        }
        .accessibilityLabel("Post actions")
    }
}

// MARK: - Report Sheet

struct ForumReportSheet: View {
    let onSubmit: (ForumReportReason, String?) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var reason: ForumReportReason? = nil
    @State private var details: String = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    Text("Why are you reporting this post? It will be hidden for you right away and sent to our moderators.")
                        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                        .foregroundColor(Theme.inkSecondary)

                    ForEach(ForumReportReason.allCases) { option in
                        ForumReportReasonRow(option: option, isSelected: reason == option) {
                            HapticManager.selection()
                            reason = option
                        }
                    }

                    TextField("Add details (optional)", text: $details, axis: .vertical)
                        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                        .lineLimit(3...6)
                        .padding(Theme.Spacing.card)
                        .banknoteCard()
                        .onChange(of: details) { _, newValue in
                            if newValue.count > ForumModeration.detailsLimit {
                                details = String(newValue.prefix(ForumModeration.detailsLimit))
                            }
                        }
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Report Post")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundColor(Theme.inkSecondary)
                }
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Submit") {
                        guard let reason else { return }
                        HapticManager.selection()
                        let trimmed = details.trimmingCharacters(in: .whitespacesAndNewlines)
                        onSubmit(reason, trimmed.isEmpty ? nil : trimmed)
                        dismiss()
                    }
                    .font(Theme.labelStyle)
                    .disabled(reason == nil)
                    .foregroundColor(reason == nil ? Theme.inkTertiary : Theme.securityGold)
                }
            }
        }
    }
}

private struct ForumReportReasonRow: View {
    let option: ForumReportReason
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack {
                Text(option.label)
                    .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Image(systemName: isSelected ? "largecircle.fill.circle" : "circle")
                    .foregroundColor(isSelected ? Theme.securityGold : Theme.inkTertiary)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .buttonStyle(EKPressStyle())
        .accessibilityAddTraits(isSelected ? .isSelected : [])
    }
}

// MARK: - Community Guidelines

struct ForumGuidelinesSheet: View {
    /// Called when the user taps "I agree" (the sheet dismisses itself).
    let onAgree: () -> Void
    @Environment(\.dismiss) private var dismiss

    private let rules: [String] = [
        "Zero tolerance for abuse, harassment, hate speech or threats.",
        "No spam, advertising, referral links or pump-and-dump promotion.",
        "No personalised buy/sell tips or guaranteed-return claims. Share analysis, not instructions.",
        "Do not post anyone's personal information.",
        "Disclose your position when you discuss a stock you hold.",
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    Text("Before you post, please agree to keep the Nivesh community safe and useful.")
                        .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                        .foregroundColor(Theme.inkSecondary)

                    ForEach(rules, id: \.self) { rule in
                        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                            Image(systemName: "checkmark.seal")
                                .foregroundColor(Theme.securityGold)
                            Text(rule)
                                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                                .foregroundColor(Theme.inkPrimary)
                        }
                    }

                    GuillocheDivider()

                    Text("See something that breaks these rules? Long-press it or tap ••• to Report the post or Block the user. Reported posts are hidden for you immediately and reviewed by our moderators; content that breaks the rules is removed and repeat offenders lose access.")
                        .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                        .foregroundColor(Theme.inkSecondary)

                    ForumContactModeratorsLink()

                    Button {
                        HapticManager.success()
                        onAgree()
                        dismiss()
                    } label: {
                        Text("I agree")
                            .font(Theme.labelStyle)
                            .foregroundColor(Theme.canvas)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, Theme.Spacing.standard)
                            .background(Theme.securityGold)
                            .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
                    }
                    .buttonStyle(EKPressStyle())
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Community Guidelines")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Close") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundColor(Theme.inkSecondary)
                }
            }
        }
    }
}

/// REG-13: the published moderation contact is the Grievance Officer notice
/// (REG-12), served from the backend env, so there is one real address.
struct ForumContactModeratorsLink: View {
    var body: some View {
        NavigationLink {
            DisclosureDetailView(key: .grievanceOfficer)
        } label: {
            Label("Contact & Grievance Officer", systemImage: "envelope")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.securityGold)
        }
    }
}

// MARK: - Blocked Users

struct BlockedUsersView: View {
    @StateObject private var vm = BlockedUsersViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: Theme.Spacing.card) {
                    if let error = vm.errorMessage {
                        ForumErrorState(message: error) { vm.fetchBlocks() }
                    } else if vm.isLoading && vm.blocks.isEmpty {
                        ProgressView()
                            .tint(Theme.securityGold)
                            .frame(maxWidth: .infinity, minHeight: 160)
                    } else if vm.blocks.isEmpty {
                        Text("You haven't blocked anyone.")
                            .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                            .foregroundColor(Theme.inkTertiary)
                            .frame(maxWidth: .infinity, minHeight: 160)
                    } else {
                        ForEach(vm.blocks) { block in
                            BlockedUserRow(block: block) { vm.unblock(block) }
                        }
                    }
                }
                .padding(Theme.screenPadding)
            }
            .background(Theme.canvas.ignoresSafeArea())
            .navigationTitle("Blocked Users")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .foregroundColor(Theme.securityGold)
                }
            }
            .refreshable { vm.fetchBlocks() }
            .onAppear { vm.fetchBlocks() }
        }
    }
}

private struct BlockedUserRow: View {
    let block: ForumBlock
    let onUnblock: () -> Void

    var body: some View {
        HStack {
            Text(block.displayName)
                .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
            Spacer()
            Button {
                HapticManager.selection()
                onUnblock()
            } label: {
                Text("Unblock")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}
