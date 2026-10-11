import XCTest
@testable import stockme

/// IOSUI-25: poll options are identified by id, so removing a row can never
/// leave a binding pointing past the end of the array.
@MainActor
final class PollOptionDraftTests: XCTestCase {

    func testRemoveLastByIdKeepsOrder() {
        let vm = CreateThreadViewModel(loadBoards: false)
        XCTAssertEqual(vm.pollOptions.count, 2)
        vm.addPollOption(); vm.addPollOption(); vm.addPollOption()
        XCTAssertEqual(vm.pollOptions.count, 5)
        let before = vm.pollOptions.map(\.id)
        vm.removePollOption(id: before[4])
        XCTAssertEqual(vm.pollOptions.map(\.id), Array(before.prefix(4)))
    }

    func testRemoveUnknownIdOrBelowMinimumIsNoOp() {
        let vm = CreateThreadViewModel(loadBoards: false)
        vm.addPollOption()
        vm.removePollOption(id: UUID())
        XCTAssertEqual(vm.pollOptions.count, 3)
        vm.removePollOption(id: vm.pollOptions[0].id)
        vm.removePollOption(id: vm.pollOptions[0].id)
        XCTAssertEqual(vm.pollOptions.count, 2)
    }

    func testOptionCapIsSix() {
        let vm = CreateThreadViewModel(loadBoards: false)
        for _ in 0..<10 { vm.addPollOption() }
        XCTAssertEqual(vm.pollOptions.count, 6)
    }

    func testSubmittedOptionsAreTrimmedAndNonEmpty() {
        let vm = CreateThreadViewModel(loadBoards: false)
        vm.addPollOption()
        vm.pollOptions[0].text = "  Bull  "
        vm.pollOptions[1].text = "   "
        vm.pollOptions[2].text = "Bear"
        XCTAssertEqual(vm.validPollOptions, ["Bull", "Bear"])
    }
}
