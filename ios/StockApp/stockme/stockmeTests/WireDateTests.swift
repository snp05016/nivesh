import XCTest
@testable import stockme

/// IOSUI-24: dates are parsed once at decode with a pinned formatter, and an
/// unparseable date is dropped instead of being plotted at "today".
@MainActor
final class WireDateTests: XCTestCase {

    private func gregorianDay(_ y: Int, _ m: Int, _ d: Int) -> Date {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone.current
        return cal.date(from: DateComponents(year: y, month: m, day: d))!
    }

    private func ohlcvJSON(_ date: String) -> String {
        #"{"date":"\#(date)","open":1,"high":2,"low":0.5,"close":1.5,"volume":100}"#
    }

    func testOHLCVPointParsesDateOnceAtDecode() throws {
        let p = try JSONDecoder().decode(OHLCVPoint.self, from: Data(ohlcvJSON("2026-10-08").utf8))
        XCTAssertEqual(p.parsedDate, gregorianDay(2026, 10, 8))
    }

    func testUnparseableDateIsNotMappedToNow() throws {
        let p = try JSONDecoder().decode(OHLCVPoint.self, from: Data(ohlcvJSON("garbage").utf8))
        XCTAssertEqual(p.parsedDate, .distantPast)
        XCTAssertTrue([p].droppingUndated.isEmpty)
    }

    func testStockHistoryResponseDropsUndatedRows() throws {
        let json = #"{"ticker":"TCS","exchange":"NSE","period":"1y","prices":[\#(ohlcvJSON("2026-10-07")),\#(ohlcvJSON("garbage")),\#(ohlcvJSON("2026-10-08"))]}"#
        let resp = try JSONDecoder().decode(StockHistoryResponse.self, from: Data(json.utf8))
        XCTAssertEqual(resp.prices.map(\.date), ["2026-10-07", "2026-10-08"])

        // Bare-array fallback path in NetworkManager goes through the memberwise init.
        let rows = try JSONDecoder().decode([OHLCVPoint].self, from: Data("[\(ohlcvJSON("x")),\(ohlcvJSON("2026-10-08"))]".utf8))
        let built = StockHistoryResponse(ticker: "TCS", exchange: "NSE", period: "1y", prices: rows)
        XCTAssertEqual(built.prices.map(\.date), ["2026-10-08"])
    }

    func testValuationHistoryDropsUndatedSnapshots() throws {
        func snap(_ d: String) -> String {
            #"{"date":"\#(d)","total_value":100,"total_invested":90,"total_pnl":10,"pnl_percent":11.1,"nifty_close":null}"#
        }
        let json = #"{"user_id":1,"days":30,"snapshots":[\#(snap("2026-10-07")),\#(snap("bad")),\#(snap("2026-10-08"))],"summary":{"period_change_value":0,"period_change_pct":0,"peak_value":100,"trough_value":100,"data_points":3}}"#
        let resp = try JSONDecoder().decode(ValuationHistoryResponse.self, from: Data(json.utf8))
        XCTAssertEqual(resp.snapshots.map(\.date), ["2026-10-07", "2026-10-08"])
        XCTAssertEqual(resp.snapshots.last?.parsedDate, gregorianDay(2026, 10, 8))
    }

    func testDayToleratesTrailingTimeAndRejectsGarbage() {
        XCTAssertEqual(WireDate.day("2026-10-08T00:00:00"), gregorianDay(2026, 10, 8))
        XCTAssertNil(WireDate.day("garbage"))
        XCTAssertEqual(WireDate.dayKey(gregorianDay(2026, 10, 8)), "2026-10-08")
    }

    func testPurchaseDateWireFormatIsPinnedToPOSIXGregorian() {
        // A th_TH Buddhist-calendar device would otherwise send "08-ต.ค.-2569".
        XCTAssertEqual(WireDate.ddMMMyyyy.locale.identifier, "en_US_POSIX")
        XCTAssertEqual(WireDate.ddMMMyyyy.calendar.identifier, .gregorian)
        XCTAssertEqual(WireDate.ddMMMyyyy.string(from: gregorianDay(2026, 10, 8)), "08-Oct-2026")
        XCTAssertEqual(WireDate.dayFormatter.calendar.identifier, .gregorian)
    }

    /// IOSCORE-21: backend isoformat() is naive UTC with microseconds.
    func testParseISOAcceptsMicrosecondsAndMissingOffset() throws {
        let expected = Date(timeIntervalSince1970: 1_791_462_896.789)
        let naive = try XCTUnwrap(WireDate.parseISO("2026-10-08T12:34:56.789012"))
        XCTAssertEqual(naive.timeIntervalSince1970, expected.timeIntervalSince1970, accuracy: 0.001)
        let offset = try XCTUnwrap(WireDate.parseISO("2026-10-08T12:34:56.789+00:00"))
        XCTAssertEqual(offset.timeIntervalSince1970, expected.timeIntervalSince1970, accuracy: 0.001)
        let ist = try XCTUnwrap(WireDate.parseISO("2026-10-08T18:04:56+05:30"))
        XCTAssertEqual(ist.timeIntervalSince1970, 1_791_462_896, accuracy: 0.001)
        XCTAssertNil(WireDate.parseISO("garbage"))
    }

    func testNotificationTimeIsFormattedNotRaw() throws {
        let json = #"{"id":1,"type":"system","title":"t","body":"b","is_read":false,"action_url":null,"created_at":"2026-10-08T12:34:56.789012"}"#
        let dto = try JSONDecoder().decode(NotificationDTO.self, from: Data(json.utf8))
        XCTAssertFalse(dto.formattedTime.isEmpty)
        XCTAssertFalse(dto.formattedTime.contains("2026-10-08T"))
    }

    func testISTDayIsPinnedToKolkataAndPOSIX() {
        // 2026-10-08 20:00 UTC is already 9 Oct in India.
        let d = Date(timeIntervalSince1970: 1_791_462_896 + 7.5 * 3600)
        XCTAssertEqual(NetworkManager.istDateString(from: d), "2026-10-09")
        XCTAssertEqual(WireDate.istDayFormatter.locale.identifier, "en_US_POSIX")
        XCTAssertEqual(WireDate.istDayFormatter.calendar.identifier, .gregorian)
    }

    func testLegacyPurchaseDateStillParses() {
        XCTAssertEqual(WireDate.ddMMMyyyy.date(from: "08-Oct-2026"), gregorianDay(2026, 10, 8))
    }

    func testParsedDateAccessIsCheapForLongSeries() throws {
        let rows = (0..<1_250).map { i in
            ohlcvJSON(WireDate.dayKey(gregorianDay(2021, 1, 1).addingTimeInterval(Double(i) * 86_400)))
        }
        let points = try JSONDecoder().decode([OHLCVPoint].self, from: Data("[\(rows.joined(separator: ","))]".utf8))
        XCTAssertEqual(points.count, 1_250)
        measure {
            for _ in 0..<100 { _ = points.map(\.parsedDate) }
        }
    }
}
