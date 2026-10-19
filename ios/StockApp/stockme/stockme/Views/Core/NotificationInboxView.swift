import SwiftUI

// MARK: - Notification Inbox View

struct NotificationInboxView: View {
    @State private var notifications: [NotificationDTO] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    /// C9: a successful load has arrived, so an empty list really means "nothing yet".
    @State private var hasLoaded = false
    @ObservedObject private var connectivity = ConnectivityMonitor.shared

    private var phase: LoadPhase {
        .resolve(isLoading: isLoading, hasLoaded: hasLoaded, isEmpty: notifications.isEmpty,
                 error: errorMessage, isOnline: connectivity.isOnline)
    }

    var body: some View {
        ZStack {
            Theme.canvas.ignoresSafeArea()

            StateCard(
                title: "notifications",
                phase: phase,
                emptyMessage: "No notifications yet. Price-alert triggers and account messages appear here.",
                onRetry: { Task { await loadNotifications() } }
            ) {
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
            .padding(.horizontal, phase == .loaded ? 0 : Theme.screenPadding)
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
            hasLoaded = true
        } catch {
            errorMessage = "Couldn't load notifications."
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
                        .accessibilityHidden(true)
                }
            }
        }
        .buttonStyle(EKPressStyle())
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
        // The unread dot is visual only; VoiceOver hears the state.
        .accessibilityValue(isRead ? "" : "Unread")
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
        isRead = true   // optimistic; rolled back below if the server refuses
        Task {
            do {
                try await NetworkManager.shared.markNotificationRead(id: notification.id)
            } catch {
                isRead = false
                GlobalErrorDiagnoser.shared.trackNetworkError(error, endpoint: "/api/v1/notifications/{id}/read")
            }
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        NotificationInboxView()
    }
}
