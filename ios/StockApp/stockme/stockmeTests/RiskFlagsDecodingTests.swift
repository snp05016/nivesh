import XCTest
@testable import stockme

final class RiskFlagsDecodingTests: XCTestCase {

    private func decode(_ json: String) throws -> RiskFlagsDTO {
        try JSONDecoder().decode(RiskFlagsDTO.self, from: Data(json.utf8))
    }

    func testDecodesTwoFlagsWithNullSourceAndDate() throws {
        let dto = try decode("""
        {"symbol":"ABC","checks":["concentration"],"unavailable":[],"flags":[
          {"id":"holding_concentration","title":"Large share of your holdings","text":"ABC is 60.0% of your holdings by amount invested.","source":"Your Nivesh holdings","source_url":null,"as_of":null},
          {"id":"sector_concentration","title":"Large share in one sector","text":"IT stocks are 100.0%.","source":"Your Nivesh holdings","source_url":"https://www.nseindia.com","as_of":"2026-10-16"}
        ]}
        """)
        XCTAssertEqual(dto.symbol, "ABC")
        XCTAssertEqual(dto.checks, ["concentration"])
        XCTAssertEqual(dto.flags.count, 2)
        XCTAssertNil(dto.flags[0].sourceUrl)
        XCTAssertNil(dto.flags[0].asOf)
        XCTAssertEqual(dto.flags[1].sourceUrl, "https://www.nseindia.com")
        XCTAssertEqual(dto.flags[1].asOf, "2026-10-16")
        XCTAssertEqual(dto.flags[0].id, "holding_concentration")
    }

    func testMissingChecksDecodesToNil() throws {
        let dto = try decode(#"{"symbol":"ABC","flags":[]}"#)
        XCTAssertNil(dto.checks)
    }

    func testEmptyFlags() throws {
        let dto = try decode(#"{"symbol":"ABC","checks":[],"flags":[],"unavailable":[]}"#)
        XCTAssertTrue(dto.flags.isEmpty)
    }

    func testUnknownKeysAreIgnored() throws {
        let dto = try decode("""
        {"symbol":"ABC","checks":["concentration"],"extra":1,"flags":[
          {"id":"x","title":"t","text":"b","source":"s","source_url":null,"as_of":null,"future":true}]}
        """)
        XCTAssertEqual(dto.flags.count, 1)
    }
}
