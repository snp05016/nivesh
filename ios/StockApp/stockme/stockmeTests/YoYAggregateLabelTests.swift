import XCTest
@testable import stockme

/// FAKE-09: the YoY card is labelled by where the numbers came from, never "NSE AGGREGATE".
@MainActor
final class YoYAggregateLabelTests: XCTestCase {

    private func health(source: String, n: Int = 3) -> YoYMarketHealth {
        YoYMarketHealth(revenueYoYPct: 10, netProfitYoYPct: 5, companiesReported: n, source: source, fetchedAt: "")
    }

    func testMissingOrFallbackIsUnavailable() {
        XCTAssertEqual(EarningsProgressView.aggregateSourceLabel(for: nil), "UNAVAILABLE")
        XCTAssertEqual(EarningsProgressView.aggregateSourceLabel(for: health(source: "fallback")), "UNAVAILABLE")
    }

    func testSampleShowsSampleSize() {
        XCTAssertEqual(EarningsProgressView.aggregateSourceLabel(for: health(source: "yfinance_sample", n: 12)), "LARGE-CAP SAMPLE · n=12")
    }

    func testFirecrawlIsWebSourcesNotMoneycontrol() {
        XCTAssertEqual(EarningsProgressView.aggregateSourceLabel(for: health(source: "firecrawl")), "WEB SOURCES")
    }

    func testNeverClaimsNseAggregate() {
        for source in ["firecrawl", "yfinance_sample", "fallback", "unknown"] {
            XCTAssertNotEqual(EarningsProgressView.aggregateSourceLabel(for: health(source: source)), "NSE AGGREGATE")
        }
    }
}
