import XCTest
@testable import stockme

final class JournalStatsDecodingTests: XCTestCase {

    func testDecodesKeywordObjectsAndEmptyPatterns() throws {
        // Shape of GET /trade-journal/{user_id}/stats (patterns is always [] since C16).
        let json = """
        {
            "user_id": 7,
            "total_entries": 3,
            "most_journalled_ticker": "TCS",
            "win_loss_ratio": {"wins": 1, "losses": 0, "ratio": null},
            "top_keywords": [{"word": "results", "count": 2}, {"word": "momentum", "count": 1}],
            "action_breakdown": {"BUY": 2, "SELL": 1, "HOLD": 0, "WATCH": 0},
            "patterns": []
        }
        """.data(using: .utf8)!

        let stats = try JSONDecoder().decode(TradeJournalStatsResponse.self, from: json)

        XCTAssertEqual(stats.totalEntries, 3)
        XCTAssertEqual(stats.topKeywords, [KeywordCount(word: "results", count: 2), KeywordCount(word: "momentum", count: 1)])
        XCTAssertEqual(stats.patterns?.count, 0)
        XCTAssertEqual(stats.actionBreakdown?["BUY"], 2)
    }
}
