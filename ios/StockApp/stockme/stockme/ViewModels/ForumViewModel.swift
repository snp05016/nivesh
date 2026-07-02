import SwiftUI

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
}

/// Drives ThreadDetailView — fetches thread + posts + poll, and handles
/// reply composition and voting (posts + poll options).
@MainActor
class ThreadDetailViewModel: ObservableObject {
    @Published var thread: ForumThreadDetail? = nil
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var isSubmittingReply: Bool = false

    let threadId: Int

    init(threadId: Int) {
        self.threadId = threadId
        fetchThread()
    }

    func fetchThread() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let detail = try await NetworkManager.shared.getForumThreadDetail(threadId: threadId)
                self.thread = detail
                self.isLoading = false
            } catch {
                self.errorMessage = "Couldn't load thread. Pull to retry."
                self.isLoading = false
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
                createdAt: post.createdAt
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

/// Drives CreateThreadView — board picker, title/body, optional poll, and submission.
@MainActor
class CreateThreadViewModel: ObservableObject {
    @Published var boards: [ForumBoard] = []
    @Published var selectedBoardId: Int? = nil
    @Published var title: String = ""
    @Published var body: String = ""
    @Published var includesPoll: Bool = false
    @Published var pollQuestion: String = ""
    @Published var pollOptions: [String] = ["", ""]
    @Published var isSubmitting: Bool = false
    @Published var errorMessage: String? = nil
    @Published var createdThread: ForumThreadDetail? = nil

    init(preselectedBoard: ForumBoard? = nil) {
        if let preselectedBoard {
            self.boards = [preselectedBoard]
            self.selectedBoardId = preselectedBoard.id
        }
        fetchBoards()
    }

    var isValid: Bool {
        guard selectedBoardId != nil else { return false }
        guard title.trimmingCharacters(in: .whitespacesAndNewlines).count >= 3 else { return false }
        guard !body.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
        if includesPoll {
            let validOptions = pollOptions.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            guard !pollQuestion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, validOptions.count >= 2 else {
                return false
            }
        }
        return true
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
        pollOptions.append("")
    }

    func removePollOption(at index: Int) {
        guard pollOptions.count > 2, pollOptions.indices.contains(index) else { return }
        pollOptions.remove(at: index)
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
                    pollOptions: includesPoll ? pollOptions.filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty } : nil
                )
                self.createdThread = thread
                self.isSubmitting = false
                completion(true)
            } catch {
                self.errorMessage = "Couldn't create thread. Please try again."
                self.isSubmitting = false
                completion(false)
            }
        }
    }
}
