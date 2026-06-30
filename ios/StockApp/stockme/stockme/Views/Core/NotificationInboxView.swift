import SwiftUI

// MARK: - Notification Inbox View

struct NotificationInboxView: View {
    @State private var notifications: [NotificationDTO] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            if isLoading {
                VStack(spacing: Theme.Spacing.large) {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .scaleEffect(1.2)
                    Text("Loading notifications...")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                        .foregroundStyle(Theme.inkSecondary)
                }
            } else if let error = errorMessage {
                VStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "bell.slash")
                        .font(.largeTitle)
                        .foregroundStyle(Theme.inkTertiary)
                    Text(error)
                        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if notifications.isEmpty {
                VStack(spacing: Theme.Spacing.standard) {
                    Image(systemName: "bell")
                        .font(Theme.engravedSerif(size: 40, relativeTo: .largeTitle))
                        .foregroundStyle(Theme.inkTertiary.opacity(0.5))
                    Text("NO NOTIFICATIONS")
                        .font(Theme.officialStampFont(size: 11, relativeTo: .body))
                        .tracking(2)
                        .foregroundStyle(Theme.inkTertiary)
                    Text("You're all caught up. We'll notify you when something important happens.")
                        .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                        .foregroundStyle(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, Theme.Spacing.xLarge)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVStack(spacing: Theme.Spacing.card) {
                        ForEach(notifications) { notif in
                            NotificationCard(notification: notif)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.vertical, Theme.Spacing.card)
                }
            }
        }
        .navigationTitle("NOTIFICATIONS")
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadNotifications() }
    }

    private func loadNotifications() async {
        isLoading = true
        errorMessage = nil
        do {
            notifications = try await NetworkManager.shared.fetchNotifications()
        } catch {
            errorMessage = "Could not load notifications"
        }
        isLoading = false
    }
}

// MARK: - Notification Card (extracted per AGENTS.md §6.6)

struct NotificationCard: View {
    let notification: NotificationDTO
    @State private var isRead: Bool

    init(notification: NotificationDTO) {
        self.notification = notification
        _isRead = State(initialValue: notification.isRead)
    }

    var body: some View {
        Button(action: { HapticManager.selection(); markRead() }) {
            HStack(alignment: .top, spacing: Theme.Spacing.standard) {
                Image(systemName: notification.typeIcon)
                    .font(.title3)
                    .foregroundStyle(typeColor)
                    .frame(width: 32, height: 32)
                    .background(typeColor.opacity(0.1))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(notification.title)
                            .font(Theme.engravedSerif(size: 14, weight: .semibold, relativeTo: .body))
                            .foregroundStyle(Theme.inkPrimary)
                            .lineLimit(2)
                        Spacer(minLength: Theme.Spacing.medium)
                        Text(notification.formattedTime)
                            .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                            .foregroundStyle(Theme.inkTertiary)
                    }
                    Text(notification.body)
                        .font(Theme.engravedSerif(size: 12, weight: .regular, relativeTo: .footnote))
                        .foregroundStyle(Theme.inkSecondary)
                        .lineLimit(3)
                        .lineSpacing(2)
                }
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.canvasDeep)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                    .stroke(Theme.borderFine, lineWidth: 0.5)
            )
            .overlay(alignment: .topTrailing) {
                if !isRead {
                    Circle()
                        .fill(Theme.securityGold)
                        .frame(width: 8, height: 8)
                        .padding(Theme.Spacing.standard)
                }
            }
        }
        .buttonStyle(EKPressStyle())
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
    }

    private var typeColor: Color {
        switch notification.typeColor {
        case "securityGold": return Theme.securityGold
        case "bullGreen": return Theme.bullGreen
        case "inkSecondary": return Theme.inkSecondary
        default: return Theme.inkTertiary
        }
    }

    private func markRead() {
        guard !isRead else { return }
        Task {
            try? await NetworkManager.shared.markNotificationRead(id: notification.id)
            isRead = true
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        NotificationInboxView()
    }
}
