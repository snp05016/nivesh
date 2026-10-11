import SwiftUI
import XCTest
@testable import stockme

/// UX-25: the hand-drawn hero charts expose a spoken summary and a non-drag way to step dates.
@MainActor
final class ImmersiveChartAccessibilityTests: XCTestCase {

    func testSummaryStatesRangeChangeHighAndLow() {
        let d0 = Date(timeIntervalSince1970: 0), d1 = Date(timeIntervalSince1970: 86_400)
        let text = ImmersiveChartAccessibility.summary(
            values: [100, 150, 80, 110], dates: [d0, d1],
            format: { String(format: "%.0f", $0) }, dateText: { $0 == d0 ? "D0" : "D1" })
        XCTAssertEqual(text, "From 100 on D0 to 110 on D1, up 10.00%, high 150, low 80")
    }

    func testSummaryWithoutFiniteValues() {
        XCTAssertEqual(ImmersiveChartAccessibility.summary(values: [.nan], dates: [],
                                                           format: { "\($0)" }, dateText: { _ in "" }), "No data")
    }

    func testAdjustableStepStartsAtLatestAndClamps() {
        XCTAssertEqual(ImmersiveChartAccessibility.step(from: nil, count: 5, direction: .decrement), 3)
        XCTAssertEqual(ImmersiveChartAccessibility.step(from: nil, count: 5, direction: .increment), 4)
        XCTAssertEqual(ImmersiveChartAccessibility.step(from: 0, count: 5, direction: .decrement), 0)
        XCTAssertEqual(ImmersiveChartAccessibility.step(from: 4, count: 5, direction: .increment), 4)
        XCTAssertNil(ImmersiveChartAccessibility.step(from: nil, count: 0, direction: .increment))
    }
}
