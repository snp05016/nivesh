import XCTest
@testable import stockme

/// UX-17: one rupee symbol, no ₹ on index points, nil renders as "—", one compact style.
@MainActor
final class IndianFormatterTests: XCTestCase {

    /// Runs `body` with the default (relative L/Cr) display, restoring the user's setting after.
    private func withRelativeFormat(_ body: () -> Void) {
        let key = "currencyDisplay"
        let saved = UserDefaults.standard.object(forKey: key)
        UserDefaults.standard.removeObject(forKey: key)
        defer { UserDefaults.standard.set(saved, forKey: key) }
        body()
    }

    func testPriceHasExactlyOneSymbol() {
        let s = IndianFormatter.price(123456)
        XCTAssertEqual(s, "₹1,23,456.00")
        XCTAssertEqual(s.filter { $0 == "₹" }.count, 1)
    }

    func testMissingPriceIsDash() {
        XCTAssertEqual(IndianFormatter.price(nil as Double?), "—")
        XCTAssertEqual(IndianFormatter.price(Optional(12.5)), "₹12.50")
    }

    func testIndexPointsHaveNoRupee() {
        XCTAssertEqual(IndianFormatter.points(22450.5), "22,450.50")
        XCTAssertFalse(IndianFormatter.points(22450.5).contains("₹"))
        XCTAssertEqual(IndianFormatter.signedPoints(-120.5), "-120.50")
        XCTAssertEqual(IndianFormatter.signedPoints(120.5), "+120.50")
    }

    func testSignedPrice() {
        XCTAssertEqual(IndianFormatter.signedPrice(-12), "-₹12.00")
        XCTAssertEqual(IndianFormatter.signedPrice(12), "+₹12.00")
    }

    func testCompactStyleSignBeforeSymbolAndSpacedUnit() {
        withRelativeFormat {
            XCTAssertEqual(IndianFormatter.formatLakhsCrores(-12_000_000), "-₹1.20 Cr")
            XCTAssertEqual(IndianFormatter.formatLakhsCrores(-340_000), "-₹3.40 L")
            XCTAssertEqual(IndianFormatter.priceCompact(250_000), "₹2.50 L")
            XCTAssertEqual(IndianFormatter.formatLakhsCrores(1_90_000 * 1_00_00_000), "₹1,90,000 Cr")
        }
    }

    /// Source scan: no call site may prepend "₹" to a formatter that already emits it.
    func testNoDoubleRupeeAtCallSites() throws {
        let appDir = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("stockme")
        let pattern = try NSRegularExpression(
            pattern: #"(₹|\\u\{20B9\})\\\((IndianFormatter\.(price|priceCompact|formatLakhsCrores|signedPrice)\b|[^)"]*\.(inrFormatted|shortFormatted))"#
        )
        guard let files = FileManager.default.enumerator(at: appDir, includingPropertiesForKeys: nil) else {
            throw XCTSkip("source tree not reachable from the test host")
        }
        var scanned = 0
        var offenders: [String] = []
        for case let url as URL in files where url.pathExtension == "swift" {
            let text = try String(contentsOf: url, encoding: .utf8)
            scanned += 1
            for (i, line) in text.components(separatedBy: "\n").enumerated() {
                let range = NSRange(line.startIndex..., in: line)
                if pattern.firstMatch(in: line, range: range) != nil {
                    offenders.append("\(url.lastPathComponent):\(i + 1)")
                }
            }
        }
        if scanned == 0 { throw XCTSkip("no Swift sources found at \(appDir.path)") }
        XCTAssertTrue(offenders.isEmpty, "double rupee symbol at: \(offenders.joined(separator: ", "))")
    }
}
