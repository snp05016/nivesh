import XCTest
@testable import stockme

final class PortfolioPDFExportTests: XCTestCase {

    private func response(status: Int, contentType: String) -> URLResponse {
        HTTPURLResponse(
            url: URL(string: "https://example.com/portfolio/export/pdf/1")!,
            statusCode: status,
            httpVersion: "HTTP/1.1",
            headerFields: ["Content-Type": contentType]
        )!
    }

    func testAcceptsPDFResponse() {
        XCTAssertNoThrow(try NetworkManager.requirePDFResponse(response(status: 200, contentType: "application/pdf")))
    }

    func testNon2xxThrows() {
        XCTAssertThrowsError(try NetworkManager.requirePDFResponse(response(status: 503, contentType: "application/json"))) { error in
            guard case NetworkError.serverError(let code, _) = error else { return XCTFail("unexpected error \(error)") }
            XCTAssertEqual(code, 503)
        }
    }

    func testTextBodyThrows() {
        XCTAssertThrowsError(try NetworkManager.requirePDFResponse(response(status: 200, contentType: "text/plain; charset=utf-8")))
    }
}
