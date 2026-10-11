import SwiftUI
import Combine

/// Copy for a failed report / block / unblock call: the server's 400 message
/// (e.g. "You cannot report your own post") or a generic retry line.
func forumModerationErrorMessage(_ error: Error) -> String {
    if case let NetworkError.fetchFailed(_, status, body) = error {
        if status == 400,
           let data = body.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let detail = json["detail"] as? String {
            return detail
        }
        if status == 401 { return "Sign in to report or block." }
    }
    return "Couldn't send. Try again."
}

enum ForumModerationNotice {
    static let reported = "Thanks. Our team will review this post."
    static let blocked = "You won't see posts from this user."
}

/// Drives ForumHubView — fetches the board list.
@MainActor
class ForumViewModel: ObservableObject {
    @Published var boards: [ForumBoard] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    init() {
        fetchBoards()
    }

    func fetchBoards() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let boards = try await NetworkManager.shared.getForumBoards()
                self.boards = boards
                self.isLoading = false
            } catch {
                self.errorMessage = "Couldn't load boards. Pull to retry."
                self.isLoading = false
            }
        }
    }
}

/// Drives a single board's thread list.
@MainActor
class BoardThreadListViewModel: ObservableObject {
    @Published var threads: [ForumThreadSummary] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    /// One-shot confirmation / error after a report or block.
    @Published var moderationNotice: String? = nil

    let board: ForumBoard

    init(board: ForumBoard) {
        self.board = board
        fetchThreads()
    }

    func fetchThreads() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let threads = try await NetworkManager.shared.getForumThreads(boardId: board.id)
                self.threads = threads
                self.isLoading = false
            } catch {
                self.errorMessage = "Couldn't load threads. Pull to retry."
                self.isLoading = false
            }
        }
    }

    /// Reports a thread's opening post; the thread disappears for this viewer.
    func report(thread: ForumThreadSummary, reason: ForumReportReason, details: String?) {
        guard let postId = thread.opPostId else { return }
        Task {
            do {
                try await NetworkManager.shared.reportForumPost(postId: postId, reason: reason, details: details)
                threads.removeAll { $0.id == thread.id }
                moderationNotice = ForumModerationNotice.reported
                fetchThreads()
            } catch {
                moderationNotice = forumModerationErrorMessage(error)
            }
        }
    }

    /// Blocks a thread's author; all their threads disappear for this viewer.
    func blockAuthor(of thread: ForumThreadSummary) {
        guard let postId = thread.opPostId else { return }
        Task {
            do {
                try await NetworkManager.shared.blockForumAuthor(postId: postId)
                threads.removeAll { $0.id == thread.id }
                moderationNotice = ForumModerationNotice.blocked
                fetchThreads()
            } catch {
                moderationNotice = forumModerationErrorMessage(error)
            }
        }
    }
}

/// Drives ThreadDetailView — fetches thread + posts + poll, and handles
/// reply composition and voting (posts + poll options).
@MainActor
class ThreadDetailViewModel: ObservableObject {
    @Published var thread: ForumThreadDetail? = nil
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var isSubmittingReply: Bool = false
    /// One-shot confirmation / error after a report or block.
    @Published var moderationNotice: String? = nil
    /// Set when a report / block hides the whole thread (its opening post or
    /// author) — the view pops back to the list.
    @Published var threadHidden: Bool = false

    let threadId: Int

    init(threadId: Int) {
        self.threadId = threadId
        fetchThread()
    }

    func fetchThread(afterModeration: Bool = false) {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let detail = try await NetworkManager.shared.getForumThreadDetail(threadId: threadId)
                self.thread = detail
                self.isLoading = false
            } catch {
                if afterModeration, case let NetworkError.fetchFailed(_, status, _) = error, status == 404 {
                    self.thread = nil
                    self.threadHidden = true
                } else {
                    self.errorMessage = "Couldn't load thread. Pull to retry."
                }
                self.isLoading = false
            }
        }
    }

    func report(postId: Int, reason: ForumReportReason, details: String?) {
        Task {
            do {
                try await NetworkManager.shared.reportForumPost(postId: postId, reason: reason, details: details)
                moderationNotice = ForumModerationNotice.reported
                fetchThread(afterModeration: true)
            } catch {
                moderationNotice = forumModerationErrorMessage(error)
            }
        }
    }

    func blockAuthor(postId: Int) {
        Task {
            do {
                try await NetworkManager.shared.blockForumAuthor(postId: postId)
                moderationNotice = ForumModerationNotice.blocked
                fetchThread(afterModeration: true)
            } catch {
                moderationNotice = forumModerationErrorMessage(error)
            }
        }
    }

    func submitReply(body: String, parentPostId: Int? = nil) {
        guard !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        isSubmittingReply = true
        Task {
            do {
                _ = try await NetworkManager.shared.createForumPost(threadId: threadId, body: body, parentPostId: parentPostId)
                self.isSubmittingReply = false
                fetchThread()
            } catch {
                self.isSubmittingReply = false
                self.errorMessage = "Couldn't post your reply. Try again."
            }
        }
    }

    func vote(postId: Int, direction: String) {
        Task {
            do {
                let result = try await NetworkManager.shared.voteForumPost(postId: postId, direction: direction)
                applyVoteResult(result)
            } catch {
                // Silently ignore — the UI will simply not update; user can retry.
            }
        }
    }

    func votePoll(pollId: Int, optionId: Int) {
        Task {
            do {
                let updatedPoll = try await NetworkManager.shared.voteForumPoll(pollId: pollId, optionId: optionId)
                applyPollResult(updatedPoll)
            } catch {
                // Silently ignore — the UI will simply not update; user can retry.
            }
        }
    }

    private func applyVoteResult(_ result: ForumVoteResult) {
        guard var current = thread else { return }
        let updatedPosts = current.posts.map { post -> ForumPost in
            guard post.id == result.postId else { return post }
            return ForumPost(
                id: post.id,
                threadId: post.threadId,
                parentPostId: post.parentPostId,
                body: post.body,
                isOp: post.isOp,
                authorDisplayName: post.authorDisplayName,
                upvotes: result.upvotes,
                downvotes: result.downvotes,
                createdAt: post.createdAt,
                isMine: post.isMine
            )
        }
        current = ForumThreadDetail(
            id: current.id, boardId: current.boardId, boardName: current.boardName,
            title: current.title, authorDisplayName: current.authorDisplayName,
            isPinned: current.isPinned, createdAt: current.createdAt,
            posts: updatedPosts, poll: current.poll
        )
        self.thread = current
    }

    private func applyPollResult(_ poll: ForumPoll) {
        guard let current = thread else { return }
        self.thread = ForumThreadDetail(
            id: current.id, boardId: current.boardId, boardName: current.boardName,
            title: current.title, authorDisplayName: current.authorDisplayName,
            isPinned: current.isPinned, createdAt: current.createdAt,
            posts: current.posts, poll: poll
        )
    }
}

/// One editable poll option. Identity is stable across inserts/removals so the
/// row bindings in CreateThreadView never index into a shrunken array.
struct PollOptionDraft: Identifiable, Equatable {
    let id = UUID()
    var text = ""
}

/// Drives CreateThreadView — board picker, title/body, optional poll, and submission.
@MainActor
class CreateThreadViewModel: ObservableObject {
    @Published var boards: [ForumBoard] = []
    @Published var selectedBoardId: Int? = nil
    @Published var title: String = ""
    @Published var body: String = ""
    @Published var includesPoll: Bool = false
    @Published var pollQuestion: String = ""
    @Published var pollOptions: [PollOptionDraft] = [PollOptionDraft(), PollOptionDraft()]
    @Published var isSubmitting: Bool = false
    @Published var errorMessage: String? = nil
    @Published var createdThread: ForumThreadDetail? = nil

    init(preselectedBoard: ForumBoard? = nil, loadBoards: Bool = true) {
        if let preselectedBoard {
            self.boards = [preselectedBoard]
            self.selectedBoardId = preselectedBoard.id
        }
        if loadBoards { fetchBoards() }
    }

    /// Trimmed, non-empty option texts — what gets validated and submitted.
    var validPollOptions: [String] {
        pollOptions
            .map { $0.text.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    /// Mirror CreateThreadRequest in backend/routers/forum.py so over-long input is
    /// caught before the server answers with a validation 422. Counted in Unicode
    /// scalars to match Python's len().
    nonisolated static let maxTitleLength = 200
    nonisolated static let maxPollQuestionLength = 300

    var isValid: Bool {
        guard selectedBoardId != nil else { return false }
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmedTitle.count >= 3, trimmedTitle.unicodeScalars.count <= Self.maxTitleLength else { return false }
        guard !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        if includesPoll {
            let trimmedQuestion = pollQuestion.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmedQuestion.isEmpty,
                  trimmedQuestion.unicodeScalars.count <= Self.maxPollQuestionLength,
                  validPollOptions.count >= 2 else {
                return false
            }
        }
        return true
    }

    /// A 422 means either the spam filter ("Post rejected by spam filter") or a
    /// schema validation failure; only the former is a moderation block.
    nonisolated static func submitErrorMessage(for error: Error) -> String {
        guard case let NetworkError.fetchFailed(_, status, body) = error, status == 422 else {
            return "Couldn't post your thread. Try again."
        }
        if body.localizedCaseInsensitiveContains("spam filter") {
            return "Your post was flagged and blocked. Try rephrasing."
        }
        return "Please check your post: title 3-\(maxTitleLength) characters, poll question up to \(maxPollQuestionLength)."
    }

    func fetchBoards() {
        Task {
            do {
                let boards = try await NetworkManager.shared.getForumBoards()
                self.boards = boards
                if self.selectedBoardId == nil { self.selectedBoardId = boards.first?.id }
            } catch {
                // Board picker just stays empty — user can retry by reopening the sheet.
            }
        }
    }

    func addPollOption() {
        guard pollOptions.count < 6 else { return }
        pollOptions.append(PollOptionDraft())
    }

    func removePollOption(id: PollOptionDraft.ID) {
        guard pollOptions.count > 2 else { return }
        pollOptions.removeAll { $0.id == id }
    }

    func submit(completion: @escaping (Bool) -> Void) {
        guard let boardId = selectedBoardId, isValid else { return }
        isSubmitting = true
        errorMessage = nil
        Task {
            do {
                let thread = try await NetworkManager.shared.createForumThread(
                    boardId: boardId,
                    title: title.trimmingCharacters(in: .whitespacesAndNewlines),
                    body: body.trimmingCharacters(in: .whitespacesAndNewlines),
                    pollQuestion: includesPoll ? pollQuestion.trimmingCharacters(in: .whitespacesAndNewlines) : nil,
                    pollOptions: includesPoll ? validPollOptions : nil
                )
                self.createdThread = thread
                self.isSubmitting = false
                completion(true)
            } catch {
                self.errorMessage = Self.submitErrorMessage(for: error)
                self.isSubmitting = false
                completion(false)
            }
        }
    }
}

/// Drives BlockedUsersView — list + unblock.
@MainActor
class BlockedUsersViewModel: ObservableObject {
    @Published var blocks: [ForumBlock] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil

    func fetchBlocks() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                self.blocks = try await NetworkManager.shared.getForumBlocks()
            } catch {
                self.errorMessage = "Couldn't load blocked users. Pull to retry."
            }
            self.isLoading = false
        }
    }

    func unblock(_ block: ForumBlock) {
        Task {
            do {
                try await NetworkManager.shared.unblockForumUser(blockId: block.blockId)
                blocks.removeAll { $0.blockId == block.blockId }
            } catch {
                errorMessage = forumModerationErrorMessage(error)
            }
        }
    }
}
