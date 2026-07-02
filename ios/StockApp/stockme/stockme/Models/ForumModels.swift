import Foundation

// MARK: - Community Forum Domain Models
//
// Backed by /api/forum/... (see NetworkManager Community Forum section).
// Field names mirror backend/routers/forum.py response models exactly —
// the backend is authoritative for shape; do not invent fields it doesn't return.

/// A discussion board — general market board or a per-stock board.
/// Mirrors backend/routers/forum.py:ForumBoardResponse.
struct ForumBoard: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let slug: String
    let name: String
    let description: String?
    let boardType: String
    let ticker: String?
    let threadCount: Int

    enum CodingKeys: String, CodingKey {
        case id, slug, name, description
        case boardType = "board_type"
        case ticker
        case threadCount = "thread_count"
    }

    var isStockBoard: Bool { boardType == "stock" }
}

/// Thread summary row shown in a board's thread list.
/// Mirrors backend/routers/forum.py:ForumThreadSummaryResponse.
struct ForumThreadSummary: Codable, Identifiable, Equatable {
    let id: Int
    let boardId: Int
    let title: String
    let authorDisplayName: String
    let isPinned: Bool
    let replyCount: Int
    let upvotes: Int
    let downvotes: Int
    let hasPoll: Bool
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case boardId = "board_id"
        case title
        case authorDisplayName = "author_display_name"
        case isPinned = "is_pinned"
        case replyCount = "reply_count"
        case upvotes, downvotes
        case hasPoll = "has_poll"
        case createdAt = "created_at"
    }
}

/// A single post (opening post or reply) inside a thread.
/// Mirrors backend/routers/forum.py:ForumPostResponse.
struct ForumPost: Codable, Identifiable, Equatable {
    let id: Int
    let threadId: Int
    let parentPostId: Int?
    let body: String
    let isOp: Bool
    let authorDisplayName: String
    let upvotes: Int
    let downvotes: Int
    let createdAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case threadId = "thread_id"
        case parentPostId = "parent_post_id"
        case body
        case isOp = "is_op"
        case authorDisplayName = "author_display_name"
        case upvotes, downvotes
        case createdAt = "created_at"
    }
}

/// A poll option with its running vote count.
/// Mirrors backend/routers/forum.py:ForumPollOptionResponse.
struct ForumPollOption: Codable, Identifiable, Equatable {
    let id: Int
    let optionText: String
    let voteCount: Int

    enum CodingKeys: String, CodingKey {
        case id
        case optionText = "option_text"
        case voteCount = "vote_count"
    }
}

/// A poll attached to a thread.
/// Mirrors backend/routers/forum.py:ForumPollResponse.
struct ForumPoll: Codable, Identifiable, Equatable {
    let id: Int
    let threadId: Int
    let question: String
    let totalVotes: Int
    let options: [ForumPollOption]

    enum CodingKeys: String, CodingKey {
        case id
        case threadId = "thread_id"
        case question
        case totalVotes = "total_votes"
        case options
    }

    func percentage(for option: ForumPollOption) -> Double {
        guard totalVotes > 0 else { return 0 }
        return Double(option.voteCount) / Double(totalVotes) * 100
    }
}

/// Full thread payload — meta, all posts, and poll if any.
/// Mirrors backend/routers/forum.py:ForumThreadDetailResponse.
struct ForumThreadDetail: Codable, Identifiable, Equatable {
    let id: Int
    let boardId: Int
    let boardName: String?
    let title: String
    let authorDisplayName: String
    let isPinned: Bool
    let createdAt: String?
    let posts: [ForumPost]
    let poll: ForumPoll?

    enum CodingKeys: String, CodingKey {
        case id
        case boardId = "board_id"
        case boardName = "board_name"
        case title
        case authorDisplayName = "author_display_name"
        case isPinned = "is_pinned"
        case createdAt = "created_at"
        case posts, poll
    }

    var openingPost: ForumPost? { posts.first(where: { $0.isOp }) ?? posts.first }
    var replies: [ForumPost] { posts.filter { !$0.isOp } }
}

/// Response to POST /api/forum/posts/{id}/vote.
/// Mirrors backend/routers/forum.py:VotePostResponse.
struct ForumVoteResult: Codable, Equatable {
    let postId: Int
    let upvotes: Int
    let downvotes: Int
    /// +1 upvoted, -1 downvoted, 0 vote removed.
    let userVote: Int

    enum CodingKeys: String, CodingKey {
        case postId = "post_id"
        case upvotes, downvotes
        case userVote = "user_vote"
    }
}
