import XCTest
@testable import stockme

/// C9: LoadPhase.resolve precedence. Empty only after a successful response;
/// a failure with nothing loaded is never empty; stored messages are verbatim.
final class LoadPhaseTests: XCTestCase {

    func testPrecedenceTable() {
        let cases: [(isLoading: Bool, hasLoaded: Bool, isEmpty: Bool, error: String?, isOnline: Bool, expected: LoadPhase, note: String)] = [
            (true, false, true, nil, true, .loading, "loading, not yet loaded, no data gives loading, never empty"),
            (false, false, true, nil, true, .loading, "idle before the first load"),
            (false, false, false, "Couldn't load market data.", true, .failed("Couldn't load market data."), "failure shown verbatim"),
            (true, false, false, "x", true, .loading, "retry in progress"),
            (false, true, true, nil, true, .empty, "successful empty answer"),
            (false, true, false, "x", true, .loaded, "refresh failure keeps loaded data"),
            (false, true, false, nil, false, .loaded, "offline keeps loaded data"),
            (false, false, false, "x", false, .offline, "offline beats error"),
            (false, false, false, nil, false, .offline, "offline, nothing loaded"),
            (true, true, false, nil, true, .loaded, "refresh in progress keeps loaded data"),
        ]
        for c in cases {
            let phase = LoadPhase.resolve(isLoading: c.isLoading, hasLoaded: c.hasLoaded,
                                          isEmpty: c.isEmpty, error: c.error, isOnline: c.isOnline)
            XCTAssertEqual(phase, c.expected, c.note)
        }
    }

    func testFailureWithNothingLoadedIsNeverEmpty() {
        for isLoading in [true, false] {
            for isOnline in [true, false] {
                let phase = LoadPhase.resolve(isLoading: isLoading, hasLoaded: false, isEmpty: true,
                                              error: "Couldn't load.", isOnline: isOnline)
                XCTAssertNotEqual(phase, .empty)
            }
        }
    }
}
