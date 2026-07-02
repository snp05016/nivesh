import SwiftUI

// MARK: - Thread Detail

struct ThreadDetailView: View {
    @StateObject private var vm: ThreadDetailViewModel
    @State private var replyText: String = ""
    @FocusState private var isComposerFocused: Bool

    init(threadId: Int) {
        _vm = StateObject(wrappedValue: ThreadDetailViewModel(threadId: threadId))
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: Theme.sectionSpacing) {
                    if let thread = vm.thread {
                        ThreadHeaderSection(thread: thread)
                            .padding(.horizontal, Theme.screenPadding)

                        if let openingPost = thread.openingPost {
                            ThreadPostCard(post: openingPost, vm: vm)
                                .padding(.horizontal, Theme.screenPadding)
                        }

                        if let poll = thread.poll {
                            ThreadPollCard(poll: poll, vm: vm)
                                .padding(.horizontal, Theme.screenPadding)
                        }

                        GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                        ThreadRepliesSection(replies: thread.replies, vm: vm)
                            .padding(.horizontal, Theme.screenPadding)
                    } else if vm.isLoading {
                        ProgressView()
                            .tint(Theme.securityGold)
                            .frame(maxWidth: .infinity, minHeight: 240)
                    } else if let error = vm.errorMessage {
                        ForumErrorState(message: error) { vm.fetchThread() }
                            .padding(.horizontal, Theme.screenPadding)
                    }
                }
                .padding(.vertical, Theme.screenPadding)
            }

            ReplyComposer(text: $replyText, isFocused: $isComposerFocused, isSubmitting: vm.isSubmittingReply) {
                let bodyToSend = replyText
                replyText = ""
                isComposerFocused = false
                vm.submitReply(body: bodyToSend)
            }
        }
        .background(Theme.canvas.ignoresSafeArea())
        .navigationTitle(vm.thread?.title ?? "Thread")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { vm.fetchThread() }
    }
}

// MARK: - Header

private struct ThreadHeaderSection: View {
    let thread: ForumThreadDetail

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack(spacing: Theme.Spacing.small) {
                if thread.isPinned {
                    Image(systemName: "pin.fill")
                        .font(.system(size: 11))
                        .foregroundColor(Theme.securityGold)
                }
                Text(thread.title)
                    .font(Theme.engravedSerif(size: 22, weight: .bold, relativeTo: .title2))
                    .foregroundColor(Theme.inkPrimary)
            }
            HStack(spacing: Theme.Spacing.xSmall) {
                Text("by \(thread.authorDisplayName)")
                if let boardName = thread.boardName {
                    Text("· \(boardName)")
                }
            }
            .font(Theme.engravedSerif(size: 12, relativeTo: .footnote))
            .foregroundColor(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Post Card (used for both the opening post and each reply)

struct ThreadPostCard: View {
    let post: ForumPost
    @ObservedObject var vm: ThreadDetailViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            HStack {
                Text(post.authorDisplayName)
                    .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
                if post.isOp {
                    Text("OP")
                        .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                        .tracking(1.2)
                        .foregroundColor(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.small)
                        .padding(.vertical, 2)
                        .background(Theme.securityGold.opacity(0.12))
                        .cornerRadius(Theme.CornerRadius.small)
                }
                Spacer()
            }

            Text(post.body)
                .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)

            GuillocheDivider()

            PostVoteRow(post: post, vm: vm)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct PostVoteRow: View {
    let post: ForumPost
    @ObservedObject var vm: ThreadDetailViewModel

    var body: some View {
        HStack(spacing: Theme.Spacing.large) {
            Button {
                HapticManager.selection()
                vm.vote(postId: post.id, direction: "up")
            } label: {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "arrow.up")
                    Text("\(post.upvotes)")
                        .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                }
                .foregroundColor(Theme.bullGreen)
            }
            .buttonStyle(EKPressStyle())

            Button {
                HapticManager.selection()
                vm.vote(postId: post.id, direction: "down")
            } label: {
                HStack(spacing: Theme.Spacing.xSmall) {
                    Image(systemName: "arrow.down")
                    Text("\(post.downvotes)")
                        .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                }
                .foregroundColor(Theme.bearRed)
            }
            .buttonStyle(EKPressStyle())

            Spacer()
        }
    }
}

// MARK: - Poll

private struct ThreadPollCard: View {
    let poll: ForumPoll
    @ObservedObject var vm: ThreadDetailViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text(poll.question)
                .font(Theme.engravedSerif(size: 16, weight: .bold, relativeTo: .headline))
                .foregroundColor(Theme.inkPrimary)

            ForEach(poll.options) { option in
                Button {
                    HapticManager.selection()
                    vm.votePoll(pollId: poll.id, optionId: option.id)
                } label: {
                    PollOptionRow(option: option, percentage: poll.percentage(for: option))
                }
                .buttonStyle(EKPressStyle())
            }

            Text("\(poll.totalVotes) vote\(poll.totalVotes == 1 ? "" : "s")")
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(Theme.Spacing.card)
        .banknoteCard()
    }
}

private struct PollOptionRow: View {
    let option: ForumPollOption
    let percentage: Double

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
            HStack {
                Text(option.optionText)
                    .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                    .foregroundColor(Theme.inkPrimary)
                Spacer()
                Text(String(format: "%.0f%%", percentage))
                    .font(Theme.serialNumberFont(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.securityGold)
            }
            ProgressView(value: percentage, total: 100)
                .tint(Theme.securityGold)
                .frame(height: 6)
        }
        .padding(.vertical, Theme.Spacing.xSmall)
    }
}

// MARK: - Replies

private struct ThreadRepliesSection: View {
    let replies: [ForumPost]
    @ObservedObject var vm: ThreadDetailViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("REPLIES (\(replies.count))")
                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                .tracking(1.5)
                .foregroundColor(Theme.inkSecondary)

            if replies.isEmpty {
                Text("No replies yet. Be the first to respond.")
                    .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                    .foregroundColor(Theme.inkTertiary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.vertical, Theme.Spacing.standard)
            } else {
                ForEach(replies) { reply in
                    ThreadPostCard(post: reply, vm: vm)
                }
            }
        }
    }
}

// MARK: - Reply Composer

private struct ReplyComposer: View {
    @Binding var text: String
    var isFocused: FocusState<Bool>.Binding
    let isSubmitting: Bool
    let onSubmit: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: Theme.Spacing.standard) {
            TextField("Write a reply…", text: $text, axis: .vertical)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(1...4)
                .padding(Theme.Spacing.standard)
                .background(Theme.canvasDeep)
                .cornerRadius(Theme.CornerRadius.medium)
                .focused(isFocused)

            Button {
                HapticManager.selection()
                onSubmit()
            } label: {
                if isSubmitting {
                    ProgressView().tint(Theme.securityGold)
                } else {
                    Image(systemName: "paperplane.fill")
                        .foregroundColor(Theme.securityGold)
                }
            }
            .buttonStyle(EKPressStyle())
            .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSubmitting)
        }
        .padding(Theme.screenPadding)
        .background(Theme.canvas)
    }
}
