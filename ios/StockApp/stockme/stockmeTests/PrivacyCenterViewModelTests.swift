import XCTest
@testable import stockme

@MainActor
final class PrivacyCenterViewModelTests: XCTestCase {

    private final class FakeAPI: PrivacyAPI {
        var exportResult: Result<URL, Error> = .success(URL(fileURLWithPath: "/tmp/nivesh-my-data-2026-10-11.json"))
        var consentError: Error?
        var consentCalls: [(type: String, granted: Bool)] = []
        var refreshes = 0
        var order: [String] = []

        func downloadMyData() async throws -> URL { try exportResult.get() }

        func setConsent(type: String, granted: Bool) async throws {
            order.append("consent")
            consentCalls.append((type, granted))
            if let consentError { throw consentError }
        }

        func refreshFlags() async {
            order.append("refresh")
            refreshes += 1
        }
    }

    private struct Boom: Error {}

    private func makeVM(_ api: FakeAPI, consented: Bool = false) -> PrivacyCenterViewModel {
        PrivacyCenterViewModel(api: api, analyticsConsented: consented)
    }

    // MARK: Export

    func testExportSuccessGivesReady() async {
        let api = FakeAPI()
        let vm = makeVM(api)
        XCTAssertEqual(vm.exportState, .idle)
        await vm.exportData()
        XCTAssertEqual(vm.exportState, .ready(URL(fileURLWithPath: "/tmp/nivesh-my-data-2026-10-11.json")))
    }

    func testExportMessagesPerFailure() async {
        let cases: [(Error, String)] = [
            (NetworkError.serverError(429, nil), "You've downloaded your data several times today. Try again tomorrow."),
            (URLError(.notConnectedToInternet), "You're offline. Connect and try again."),
            (URLError(.networkConnectionLost), "You're offline. Connect and try again."),
            (NetworkError.serverError(404, nil), "Data download isn't available right now."),
            (NetworkError.serverError(500, nil), "Couldn't prepare your file. Try again."),
            (Boom(), "Couldn't prepare your file. Try again."),
        ]
        for (error, message) in cases {
            let api = FakeAPI()
            api.exportResult = .failure(error)
            let vm = makeVM(api)
            await vm.exportData()
            XCTAssertEqual(vm.exportState, .failed(message), "\(error)")
        }
    }

    // MARK: Analytics toggle

    func testSuccessfulToggleCallsConsentThenRefresh() async {
        let api = FakeAPI()
        let vm = makeVM(api)
        let ok = await vm.setAnalytics(true)
        XCTAssertTrue(ok)
        XCTAssertTrue(vm.analyticsOn)
        XCTAssertEqual(api.consentCalls.first?.type, "product_analytics")
        XCTAssertEqual(api.consentCalls.first?.granted, true)
        XCTAssertEqual(api.order, ["consent", "refresh"])
        XCTAssertNil(vm.analyticsError)
        XCTAssertFalse(vm.analyticsBusy)
    }

    func testFailedToggleRevertsAndSetsError() async {
        let api = FakeAPI()
        api.consentError = Boom()
        let vm = makeVM(api, consented: true)
        let ok = await vm.setAnalytics(false)
        XCTAssertFalse(ok)
        XCTAssertTrue(vm.analyticsOn)  // reverted
        XCTAssertEqual(vm.analyticsError, "Couldn't update this setting. Try again.")
        XCTAssertEqual(api.refreshes, 0)
        XCTAssertFalse(vm.analyticsBusy)
    }

    func testSyncFollowsTheServerWhenIdle() {
        let vm = makeVM(FakeAPI(), consented: false)
        vm.syncAnalytics(consented: true)
        XCTAssertTrue(vm.analyticsOn)
    }

    // MARK: Caption

    func testCaptionWithRetentionDays() {
        let text = PrivacyCenterViewModel.analyticsCaption(retentionDays: 180)
        XCTAssertTrue(text.contains("Kept for 180 days."))
        XCTAssertTrue(text.hasPrefix("Tells us which screens and features are used. We never record your holdings, stock names or amounts."))
        XCTAssertTrue(text.hasSuffix("You can turn this off at any time; turning it off deletes what was recorded."))
    }

    func testCaptionWithoutRetentionDays() {
        let text = PrivacyCenterViewModel.analyticsCaption(retentionDays: nil)
        XCTAssertTrue(text.contains("Kept for the period set out in our Privacy Policy."))
        XCTAssertFalse(text.contains("days."))
    }

    // MARK: Ask store

    func testAskStoreIsPerUser() {
        let defaults = UserDefaults(suiteName: UUID().uuidString)!
        XCTAssertTrue(AnalyticsAskStore.shouldAsk(userKey: "1", defaults: defaults))
        AnalyticsAskStore.markAnswered(userKey: "1", defaults: defaults)
        XCTAssertFalse(AnalyticsAskStore.shouldAsk(userKey: "1", defaults: defaults))
        XCTAssertTrue(AnalyticsAskStore.shouldAsk(userKey: "2", defaults: defaults))
    }
}
