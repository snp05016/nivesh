import SwiftUI

// MARK: - Forum Hub

struct ForumHubView: View {
    @StateObject private var vm = ForumViewModel()
    @State private var showCreateThread = false
    @State private var showGuidelines = false
    @State private var showBlockedUsers = false
    @AppStorage(ForumModeration.guidelinesKey) private var acceptedGuidelines = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.sectionSpacing) {
                ForumHubHeader()

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                ForumBoardListSection(vm: vm)
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle("Community Forum")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    Button {
                        showGuidelines = true
                    } label: {
                        Label("Community guidelines", systemImage: "checkmark.seal")
                    }
                    Button {
                        showBlockedUsers = true
                    } label: {
                        Label("Blocked users", systemImage: "hand.raised")
                    }
                    ForumContactModeratorsLink()
                } label: {
                    Image(systemName: "shield.lefthalf.filled")
                        .foregroundStyle(Theme.securityGold)
                }
                .accessibilityLabel("Community safety")
            }
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    HapticManager.selection()
                    showCreateThread = true
                } label: {
                    Image(systemName: "square.and.pencil")
                        .foregroundStyle(Theme.securityGold)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .sheet(isPresented: $showCreateThread) {
            CreateThreadView(onCreated: { _ in vm.fetchBoards() })
        }
        .sheet(isPresented: $showGuidelines) {
            ForumGuidelinesSheet { acceptedGuidelines = true }
        }
        .sheet(isPresented: $showBlockedUsers) {
            BlockedUsersView()
        }
        .refreshable { vm.fetchBoards() }
    }
}

// MARK: - Header

private struct ForumHubHeader: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text("Discussion Boards")
                .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                .foregroundColor(Theme.inkPrimary)

            Text("Talk markets, per-stock threads, and community polls.")
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkSecondary)
        }
        .padding(.horizontal, Theme.screenPadding)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Board List Section

private struct ForumBoardListSection: View {
    @ObservedObject var vm: ForumViewModel

    var body: some View {
        VStack(spacing: Theme.Spacing.card) {
            if vm.isLoading && vm.boards.isEmpty {
                ProgressView()
                    .tint(Theme.securityGold)
                    .frame(maxWidth: .infinity, minHeight: 160)
            } else if let error = vm.errorMessage {
                ForumErrorState(message: error) { vm.fetchBoards() }
            } else if vm.boards.isEmpty {
                ForumEmptyState()
            } else {
                ForEach(vm.boards) { board in
                    NavigationLink {
                        BoardThreadListView(board: board)
                    } label: {
                        ForumBoardCard(board: board)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct ForumErrorState: View {
    let message: String
    let retry: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text(message)
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundColor(Theme.inkSecondary)
                .multilineTextAlignment(.center)
            Button {
                HapticManager.selection()
                retry()
            } label: {
                Text("Retry")
                    .font(Theme.labelStyle)
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .frame(maxWidth: .infinity, minHeight: 160)
    }
}

private struct ForumEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No boards yet")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Boards are added as new stocks and markets get community interest.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Board Card

private struct ForumBoardCard: View {
    let board: ForumBoard

    var body: some View {
        HStack(spacing: Theme.Spacing.standard) {
            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                .fill(Theme.canvasShadow)
                .frame(width: 40, height: 40)
                .overlay(
                    Image(systemName: board.isStockBoard ? "chart.line.uptrend.xyaxis" : "bubble.left.and.bubble.right.fill")
                        .foregroundColor(Theme.inkPrimary)
                )

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(board.name)
                    .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                    .foregroundColor(Theme.inkPrimary)
                    .lineLimit(1)

                if let description = board.description {
                    Text(description)
                        .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(2)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                Text("\(board.threadCount)")
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .subheadline))
                    .foregroundColor(Theme.securityGold)
                Text("THREADS")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.2)
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

// MARK: - Board Thread List

struct BoardThreadListView: View {
    @StateObject private var vm: BoardThreadListViewModel
    @State private var showCreateThread = false
    @State private var reportTarget: ForumThreadSummary? = nil
    @State private var blockTarget: ForumThreadSummary? = nil

    private let board: ForumBoard

    init(board: ForumBoard) {
        self.board = board
        _vm = StateObject(wrappedValue: BoardThreadListViewModel(board: board))
    }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.card) {
                if vm.isLoading && vm.threads.isEmpty {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .frame(maxWidth: .infinity, minHeight: 160)
                } else if let error = vm.errorMessage {
                    ForumErrorState(message: error) { vm.fetchThreads() }
                } else if vm.threads.isEmpty {
                    ForumThreadEmptyState()
                } else {
                    ForEach(vm.threads) { thread in
                        NavigationLink {
                            ThreadDetailView(threadId: thread.id, onHidden: { vm.fetchThreads() })
                        } label: {
                            ForumThreadRow(thread: thread)
                        }
                        .buttonStyle(EKPressStyle())
                        .contextMenu {
                            if thread.opPostId != nil && thread.isMine != true {
                                ForumContentActions(onReport: { reportTarget = thread }, onBlock: { blockTarget = thread })
                            }
                        }
                    }
                }
            }
            .padding(Theme.screenPadding)
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(board.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    HapticManager.selection()
                    showCreateThread = true
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .foregroundStyle(Theme.securityGold)
                }
                .buttonStyle(EKPressStyle())
            }
        }
        .sheet(isPresented: $showCreateThread) {
            CreateThreadView(preselectedBoard: board, onCreated: { _ in vm.fetchThreads() })
        }
        .sheet(item: $reportTarget) { thread in
            ForumReportSheet { reason, details in
                vm.report(thread: thread, reason: reason, details: details)
            }
        }
        .banknoteDialog(
            "Block this user?",
            isPresented: Binding(get: { blockTarget != nil }, set: { if !$0 { blockTarget = nil } }),
            message: "You won't see their threads or replies. You can unblock them from Community Forum > Blocked users.",
            buttons: blockDialogButtons
        )
        .banknoteDialog(
            vm.moderationNotice ?? "",
            isPresented: Binding(get: { vm.moderationNotice != nil }, set: { if !$0 { vm.moderationNotice = nil } }),
            buttons: [.cancel("OK")]
        )
        .refreshable { vm.fetchThreads() }
    }

    private var blockDialogButtons: [BanknoteDialogButton] {
        // Captured now: the dialog clears blockTarget before running the action.
        let target = blockTarget
        return [
            .init("Block", role: .destructive) {
                if let target { vm.blockAuthor(of: target) }
            },
            .cancel()
        ]
    }
}

private struct ForumThreadEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("No threads yet")
                .font(Theme.engravedSerif(size: 15, weight: .bold, relativeTo: .subheadline))
                .foregroundColor(Theme.inkPrimary)
            Text("Be the first to start a discussion on this board.")
                .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                .foregroundColor(Theme.inkTertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct ForumThreadRow: View {
    let thread: ForumThreadSummary

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(spacing: Theme.Spacing.small) {
                        if thread.isPinned {
                            Image(systemName: "pin.fill")
                                .font(.system(size: 10))
                                .foregroundColor(Theme.securityGold)
                        }
                        Text(thread.title)
                            .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                            .foregroundColor(Theme.inkPrimary)
                            .lineLimit(2)
                    }
                    Text("by \(thread.authorDisplayName)")
                        .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
                        .foregroundColor(Theme.inkTertiary)
                }
                Spacer()
                if thread.hasPoll {
                    Image(systemName: "chart.bar.fill")
                        .foregroundColor(Theme.avatarBlue)
                }
            }

            HStack(spacing: Theme.Spacing.large) {
                ForumStatItem(icon: "arrow.up", value: "\(thread.upvotes)", color: Theme.bullGreen)
                ForumStatItem(icon: "arrow.down", value: "\(thread.downvotes)", color: Theme.bearRed)
                ForumStatItem(icon: "bubble.left", value: "\(thread.replyCount)", color: Theme.inkSecondary)
                Spacer()
            }
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct ForumStatItem: View {
    let icon: String
    let value: String
    let color: Color

    var body: some View {
        HStack(spacing: Theme.Spacing.xSmall) {
            Image(systemName: icon)
                .font(.system(size: 11))
            Text(value)
                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
        }
        .foregroundColor(color)
    }
}
