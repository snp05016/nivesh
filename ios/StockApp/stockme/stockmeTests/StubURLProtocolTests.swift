import XCTest

/// IOSCORE-28: the shared stub harness answers with the configured response and records requests.
final class StubURLProtocolTests: XCTestCase {
    override func tearDown() {
        StubURLProtocol.reset()
        super.tearDown()
    }

    func testStubReturnsConfiguredStatus() async throws {
        StubURLProtocol.reset()
        StubURLProtocol.handler = { req in
            (HTTPURLResponse(url: req.url!, statusCode: 418, httpVersion: nil, headerFields: nil)!, Data("hi".utf8))
        }
        let session = URLSession(configuration: StubURLProtocol.configuration())

        let (data, response) = try await session.data(from: URL(string: "https://example.test/x")!)

        XCTAssertEqual((response as? HTTPURLResponse)?.statusCode, 418)
        XCTAssertEqual(String(decoding: data, as: UTF8.self), "hi")
        XCTAssertEqual(StubURLProtocol.requests.count, 1)
        XCTAssertEqual(StubURLProtocol.requests.first?.url?.path, "/x")
    }

    func testStubRecordsPostBody() async throws {
        StubURLProtocol.reset()
        StubURLProtocol.handler = { req in
            (HTTPURLResponse(url: req.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!, Data())
        }
        let session = URLSession(configuration: StubURLProtocol.configuration())
        var req = URLRequest(url: URL(string: "https://example.test/post")!)
        req.httpMethod = "POST"
        req.httpBody = Data(#"{"a":1}"#.utf8)

        _ = try await session.data(for: req)

        XCTAssertEqual(StubURLProtocol.requests.first?.httpBody, Data(#"{"a":1}"#.utf8))
    }
}
