import XCTest
@testable import stockme

final class NLScreenerTests: XCTestCase {

    func testDecodeSuccessfulNLScreenerFixture() throws {
        let json = """
        {
          "parsed_filters": {
            "sector": "Banks",
            "pe_max": "20"
          },
          "results": [
            {
              "ticker": "HDFCBANK.NS",
              "company": "HDFC Bank",
              "score": 100.0,
              "reason": "PE 18.2 < 20",
              "sector": "Financial Services"
            }
          ]
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(NLScreenerResponse.self, from: json)
        XCTAssertEqual(response.parsedFilters?["sector"], "Banks")
        XCTAssertEqual(response.parsedFilters?["pe_max"], "20")
        XCTAssertEqual(response.results.count, 1)
        XCTAssertEqual(response.results[0].ticker, "HDFCBANK.NS")
    }

    func testDecodeEmptyResultsFixture() throws {
        let json = """
        {
          "parsed_filters": {
            "pe_max": "-100"
          },
          "results": []
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(NLScreenerResponse.self, from: json)
        XCTAssertEqual(response.parsedFilters?["pe_max"], "-100")
        XCTAssertTrue(response.results.isEmpty)
    }

    func testDecodeWithNullSector() throws {
        let json = """
        {
          "parsed_filters": {
            "sector": "IT"
          },
          "results": [
            {
              "ticker": "TCS.NS",
              "company": "Tata Consultancy Services",
              "score": 100.0,
              "reason": "Match",
              "sector": null
            }
          ]
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(NLScreenerResponse.self, from: json)
        XCTAssertEqual(response.results.count, 1)
        XCTAssertNil(response.results[0].sector)
    }

    func testDecodeStructuredBackendError() throws {
        let json = """
        {
          "detail": "Failed to parse natural language query"
        }
        """.data(using: .utf8)!
        
        let response = try JSONDecoder().decode(APIErrorResponse.self, from: json)
        XCTAssertEqual(response.detail, "Failed to parse natural language query")
    }

    func testFailGracefullyOnInvalidJSON() throws {
        let json = """
        {
          "parsed_filters": {
            "sector": "Banks",
            "pe_max": 20
          },
          "results": []
        }
        """.data(using: .utf8)!
        
        // This simulates the old behavior where backend sent an Int for pe_max.
        // It SHOULD throw DecodingError.typeMismatch
        XCTAssertThrowsError(try JSONDecoder().decode(NLScreenerResponse.self, from: json)) { error in
            if let decodingError = error as? DecodingError {
                switch decodingError {
                case .typeMismatch(_, _):
                    break // Expected
                default:
                    XCTFail("Expected typeMismatch error, got \(decodingError)")
                }
            } else {
                XCTFail("Expected DecodingError, got \(error)")
            }
        }
    }
}
