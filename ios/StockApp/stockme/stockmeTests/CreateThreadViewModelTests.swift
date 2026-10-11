import XCTest
@testable import stockme

/// WIP-17: a 422 is only a moderation block when the spam filter raised it;
/// schema-validation 422s get a validation message, and isValid mirrors the
/// server's length limits.
@MainActor
final class CreateThreadViewModelTests: XCTestCase {

    func testSpam422MapsToBlocked() {
        let error = NetworkError.fetchFailed(endpoint: "x", status: 422, body: "{\"detail\":\"Post rejected by spam filter\"}")
        XCTAssertTrue(CreateThreadViewModel.submitErrorMessage(for: error).contains("flagged"))
    }

    func testValidation422MapsToGeneric() {
        let error = NetworkError.fetchFailed(endpoint: "x", status: 422, body: "{\"detail\":[{\"type\":\"string_too_long\"}]}")
        let message = CreateThreadViewModel.submitErrorMessage(for: error)
        XCTAssertFalse(message.contains("flagged"))
        XCTAssertTrue(message.contains("200"))
    }

    func testOtherErrorsMapToRetry() {
        let error = NetworkError.fetchFailed(endpoint: "x", status: 500, body: "spam filter")
        XCTAssertEqual(CreateThreadViewModel.submitErrorMessage(for: error), "Couldn't post your thread. Try again.")
    }

    func testTitleOver200Invalid() {
        let vm = CreateThreadViewModel(loadBoards: false)
        vm.selectedBoardId = 1
        vm.body = "x"
        vm.title = String(repeating: "a", count: 201)
        XCTAssertFalse(vm.isValid)
        vm.title = String(repeating: "a", count: 200)
        XCTAssertTrue(vm.isValid)
    }

    func testPollQuestionOver300Invalid() {
        let vm = CreateThreadViewModel(loadBoards: false)
        vm.selectedBoardId = 1
        vm.body = "x"
        vm.title = "Nifty outlook"
        vm.includesPoll = true
        vm.pollOptions[0].text = "Bull"
        vm.pollOptions[1].text = "Bear"
        vm.pollQuestion = String(repeating: "q", count: 301)
        XCTAssertFalse(vm.isValid)
        vm.pollQuestion = String(repeating: "q", count: 300)
        XCTAssertTrue(vm.isValid)
    }
}
