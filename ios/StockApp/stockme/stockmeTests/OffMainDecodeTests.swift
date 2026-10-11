import XCTest
@testable import stockme

/// Records which thread its decoder ran on.
private struct ThreadProbe: Decodable {
    nonisolated(unsafe) static var decodedOnMainThread: Bool?
    let value: Int

    private enum CodingKeys: String, CodingKey { case value }

    init(from decoder: Decoder) throws {
        Self.decodedOnMainThread = Thread.isMainThread
        value = try decoder.container(keyedBy: CodingKeys.self).decode(Int.self, forKey: .value)
    }
}

/// PERF-24: heavy responses (the analysis result, quick-info, history) decode off the main thread.
@MainActor
final class OffMainDecodeTests: XCTestCase {

    func testDecodeOffMainRunsOffMainThread() async throws {
        ThreadProbe.decodedOnMainThread = nil

        let probe = try await NetworkManager.decodeOffMain(ThreadProbe.self, from: Data(#"{"value":42}"#.utf8))

        XCTAssertEqual(probe.value, 42)
        XCTAssertEqual(ThreadProbe.decodedOnMainThread, false)
    }

    func testDecodeOffMainRethrowsDecodingError() async {
        do {
            _ = try await NetworkManager.decodeOffMain(ThreadProbe.self, from: Data(#"{"value":"x"}"#.utf8))
            XCTFail("expected a DecodingError")
        } catch {
            XCTAssertTrue(error is DecodingError)
        }
    }

    func testJsonObjectOffMainParsesObject() async throws {
        let obj = try await NetworkManager.jsonObjectOffMain(Data(#"{"status":"RUNNING"}"#.utf8)) as? [String: Any]
        XCTAssertEqual(obj?["status"] as? String, "RUNNING")
    }
}
