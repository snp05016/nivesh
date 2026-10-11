import XCTest
@testable import stockme

/// IOSUI-04: the arrow carries the sign, so a loss must never print a "+".
final class ChangeBadgeTests: XCTestCase {

    func testLabelTable() {
        let cases: [(input: Double, text: String, up: Bool)] = [
            (-12.3, "▼ 12.30%", false),
            (-0.004, "▲ 0.00%", true),   // rounds to zero: no down arrow, no "-0.00"
            (0, "▲ 0.00%", true),
            (5.236, "▲ 5.24%", true),
        ]
        for c in cases {
            let label = ChangeBadge.label(for: c.input)
            XCTAssertEqual(label.text, c.text, "input \(c.input)")
            XCTAssertEqual(label.up, c.up, "input \(c.input)")
        }
    }

    func testNonFiniteShowsDash() {
        let values: [Double] = [.nan, .infinity, -Double.infinity]
        for v in values {
            XCTAssertEqual(ChangeBadge.label(for: v).text, "—", "input \(v)")
        }
    }

    func testNeverPrintsPlus() {
        let values: [Double] = [-12.3, -0.004, 0, 5.236, 100, -100, .nan]
        for v in values {
            XCTAssertFalse(ChangeBadge.label(for: v).text.contains("+"), "input \(v)")
        }
    }
}
