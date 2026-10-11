import XCTest
@testable import stockme

@MainActor
final class InputValidationTests: XCTestCase {
    func testMissingOrNonPositiveTargetIsRejected() {
        XCTAssertNotNil(InputValidation.alertTargetError(target: nil, direction: "above", current: 100))
        XCTAssertNotNil(InputValidation.alertTargetError(target: 0, direction: "above", current: nil))
        XCTAssertNotNil(InputValidation.alertTargetError(target: -5, direction: "below", current: nil))
    }

    func testTargetOnWrongSideOfCurrentPriceIsRejected() {
        XCTAssertNotNil(InputValidation.alertTargetError(target: 90, direction: "above", current: 100))
        XCTAssertNotNil(InputValidation.alertTargetError(target: 100, direction: "above", current: 100))
        XCTAssertNotNil(InputValidation.alertTargetError(target: 110, direction: "below", current: 100))
    }

    func testTargetOnCorrectSidePasses() {
        XCTAssertNil(InputValidation.alertTargetError(target: 110, direction: "above", current: 100))
        XCTAssertNil(InputValidation.alertTargetError(target: 90, direction: "below", current: 100))
    }

    func testUnknownCurrentPriceSkipsDirectionCheck() {
        XCTAssertNil(InputValidation.alertTargetError(target: 90, direction: "above", current: nil))
    }
}
