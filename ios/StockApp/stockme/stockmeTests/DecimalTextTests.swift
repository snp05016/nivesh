import XCTest
@testable import stockme

/// IOSUI-05: editing a holding must not rewrite share counts through printf %g.
final class DecimalTextTests: XCTestCase {

    func testEditableRoundTripsExactly() {
        for v in [1_234_567, 1_000_000, 0.5, 123.456, 1530.1234] {
            let text = DecimalText.editable(v, maxFractionDigits: 4)
            XCTAssertEqual(DecimalText.parse(text), v, text)
        }
    }

    func testEditableHasNoExponentOrGrouping() {
        XCTAssertEqual(DecimalText.editable(1_234_567, maxFractionDigits: 4), "1234567")
        XCTAssertEqual(DecimalText.editable(1_000_000, maxFractionDigits: 4), "1000000")
        XCTAssertEqual(DecimalText.editable(0.5, maxFractionDigits: 4), "0.5")
        XCTAssertEqual(DecimalText.editable(1530, maxFractionDigits: 4), "1530")
    }

    func testParseHonoursLocaleSeparators() {
        XCTAssertEqual(DecimalText.parse("72,50", locale: Locale(identifier: "de_DE")), 72.5)
        XCTAssertEqual(DecimalText.parse("1,00,000", locale: Locale(identifier: "en_IN")), 100_000)
        XCTAssertEqual(DecimalText.parse(" 42 ", locale: Locale(identifier: "en_IN")), 42)
    }

    func testParseRejectsNonNumbers() {
        XCTAssertNil(DecimalText.parse("abc"))
        XCTAssertNil(DecimalText.parse(""))
    }
}
