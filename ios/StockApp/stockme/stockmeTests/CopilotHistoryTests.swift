import XCTest
@testable import stockme

/// UX-28: the Copilot history sent to the LLM holds only real turns, failures show
/// friendly copy, and the navigation map tracks the real Markets sections.
@MainActor
final class CopilotHistoryTests: XCTestCase {

    func testHistoryExcludesWelcomeErrorsAndFailedQuestion() {
        let messages = [
            ChatMessage(role: "assistant", content: "", isWelcome: true),
            ChatMessage(role: "user", content: "a"),
            ChatMessage(role: "assistant", content: "b"),
            ChatMessage(role: "user", content: "failed question"),
            ChatMessage(role: "assistant", content: "Can't connect.", isError: true),
        ]
        XCTAssertEqual(CopilotScreen.historyPayload(from: messages),
                       [["role": "user", "content": "a"], ["role": "assistant", "content": "b"]])
    }

    func testHistoryCapsAtLast20() {
        let messages = (0..<30).map { ChatMessage(role: $0 % 2 == 0 ? "user" : "assistant", content: "m\($0)") }
        let history = CopilotScreen.historyPayload(from: messages)
        XCTAssertEqual(history.count, 20)
        XCTAssertEqual(history.first?["content"], "m10")
        XCTAssertEqual(history.last?["content"], "m29")
    }

    func testFriendlyErrorNeverLeaksRawDescription() {
        let offline = CopilotScreen.friendlyError(URLError(.notConnectedToInternet))
        XCTAssertEqual(offline, NetworkError.userMessage(status: -1, serverDetail: nil))
        XCTAssertEqual(CopilotScreen.friendlyError(NetworkError.unauthorized),
                       NetworkError.unauthorized.errorDescription)
        let decoding = CopilotScreen.friendlyError(DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "bad")))
        XCTAssertFalse(decoding.contains("bad"))
        XCTAssertFalse(decoding.isEmpty)
    }

    func testNavigationContextMentionsEveryVisibleMarketSection() throws {
        let context = try XCTUnwrap(CopilotScreen.appNavigationContext["app_navigation"] as? String)
        for section in MarketSection.allCases where ReleaseGate.isVisible(section) {
            XCTAssertTrue(context.contains(section.englishTitle), "missing \(section.englishTitle)")
        }
        XCTAssertFalse(context.contains("gear icon"))
        XCTAssertFalse(context.contains("Learn Financial Terms"))
        XCTAssertFalse(context.contains("Server URL"))
    }
}
