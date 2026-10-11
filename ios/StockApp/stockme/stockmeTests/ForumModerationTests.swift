import XCTest
@testable import stockme

/// UX-23: forum report / block support — decoding of the new additive fields,
/// report reasons matching the backend Literal, and error-copy mapping.
@MainActor
final class ForumModerationTests: XCTestCase {

    func testPostDecodesIsMineAndToleratesOldPayload() throws {
        let new = #"{"id":1,"thread_id":2,"parent_post_id":null,"body":"b","is_op":true,"author_display_name":"A","upvotes":0,"downvotes":0,"created_at":null,"is_mine":true}"#
        let old = #"{"id":1,"thread_id":2,"parent_post_id":null,"body":"b","is_op":true,"author_display_name":"A","upvotes":0,"downvotes":0,"created_at":null}"#
        XCTAssertEqual(try JSONDecoder().decode(ForumPost.self, from: Data(new.utf8)).isMine, true)
        XCTAssertNil(try JSONDecoder().decode(ForumPost.self, from: Data(old.utf8)).isMine)
    }

    func testThreadSummaryDecodesOpPostId() throws {
        let json = #"{"id":5,"board_id":1,"title":"t","author_display_name":"A","is_pinned":false,"reply_count":0,"upvotes":0,"downvotes":0,"has_poll":false,"created_at":null,"op_post_id":9,"is_mine":false}"#
        let summary = try JSONDecoder().decode(ForumThreadSummary.self, from: Data(json.utf8))
        XCTAssertEqual(summary.opPostId, 9)
        XCTAssertEqual(summary.isMine, false)
    }

    func testReportReasonsMatchBackend() {
        XCTAssertEqual(
            Set(ForumReportReason.allCases.map(\.rawValue)),
            ["spam", "abuse", "misleading", "pump_and_dump", "other"]
        )
    }

    func testErrorMessageUsesServerDetailOn400() {
        let error = NetworkError.fetchFailed(endpoint: "/x", status: 400, body: #"{"detail":"You cannot report your own post"}"#)
        XCTAssertEqual(forumModerationErrorMessage(error), "You cannot report your own post")
    }

    func testErrorMessageFallsBackToGenericCopy() {
        let error = NetworkError.fetchFailed(endpoint: "/x", status: 500, body: "boom")
        XCTAssertEqual(forumModerationErrorMessage(error), "Couldn't send. Try again.")
        XCTAssertEqual(
            forumModerationErrorMessage(NetworkError.fetchFailed(endpoint: "/x", status: 401, body: "")),
            "Sign in to report or block."
        )
    }
}
