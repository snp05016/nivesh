import XCTest
@testable import stockme

/// IOSUI-09: opening AnalysisScreen without the action hub must never start a paid job
/// unless the user has a saved report AND opted into auto-regenerating stale ones.
@MainActor
final class AnalysisAutoStartTests: XCTestCase {

    func testNoCachedReportStaysIdle() {
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: false, hasCached: false, autoRegenerateStale: false, cachedIsStale: false), .idle)
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: false, hasCached: false, autoRegenerateStale: true, cachedIsStale: true), .idle)
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: true, hasCached: false, autoRegenerateStale: false, cachedIsStale: false), .idle)
    }

    func testCachedReportPromptsByDefault() {
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: false, hasCached: true, autoRegenerateStale: false, cachedIsStale: true), .promptCached)
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: false, hasCached: true, autoRegenerateStale: true, cachedIsStale: false), .promptCached)
    }

    func testStaleCacheWithOptInFetches() {
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: false, hasCached: true, autoRegenerateStale: true, cachedIsStale: true), .fetch)
    }

    func testForceCachedShowsCache() {
        XCTAssertEqual(AnalysisViewModel.autoStart(forceCached: true, hasCached: true, autoRegenerateStale: true, cachedIsStale: true), .showCached)
    }
}
