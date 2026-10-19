import XCTest
@testable import stockme

/// C9: Home, Alerts and Inbox use the one state system (StateCard + LoadPhase).
@MainActor
final class HomeSectionStateTests: XCTestCase {

    func testDashboardSectionsAreTheFourMarketCards() {
        XCTAssertEqual(HomeViewModel.dashboardSections, [.marketPulse, .momentum, .macroAlt, .institutional])
    }

    func testRetryTargetForEverySection() {
        let expected: [HomeSectionID: HomeViewModel.RetryTarget] = [
            .top: .none, .portfolio: .none, .indices: .indices, .watchlist: .none,
            .sectors: .sectors, .morning: .morning, .news: .none, .youtube: .none,
            .earnings: .earnings, .marketPulse: .dashboard, .momentum: .dashboard,
            .macroAlt: .dashboard, .institutional: .dashboard,
        ]
        XCTAssertEqual(Set(expected.keys), Set(HomeSectionID.allCases), "every section is mapped")
        for id in HomeSectionID.allCases {
            XCTAssertEqual(HomeViewModel.retryTarget(for: id), expected[id], id.rawValue)
        }
        for id in HomeViewModel.dashboardSections {
            XCTAssertEqual(HomeViewModel.retryTarget(for: id), .dashboard, id.rawValue)
        }
    }

    // MARK: - Source scans

    /// ios/StockApp/stockme/stockme (the app folder), from stockmeTests/<this file>.
    private var appRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()   // stockmeTests
            .deletingLastPathComponent()   // ios/StockApp/stockme
            .appendingPathComponent("stockme")
    }

    private func source(_ relativePath: String) throws -> String {
        try String(contentsOf: appRoot.appendingPathComponent(relativePath), encoding: .utf8)
    }

    /// HomeScreen is split across Views/HomeScreen.swift, Views/Home/ and its view model.
    private func homeSources() throws -> String {
        let homeDir = appRoot.appendingPathComponent("Views/Home")
        let files = try FileManager.default.contentsOfDirectory(at: homeDir, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "swift" }
        XCTAssertFalse(files.isEmpty)
        var all = try source("Views/HomeScreen.swift") + source("ViewModels/HomeViewModel.swift")
        for file in files { all += try String(contentsOf: file, encoding: .utf8) }
        return all
    }

    func testHomeUsesStateCardNotTheOldLoadingCard() throws {
        let home = try homeSources()
        XCTAssertFalse(home.contains("DashboardLoadingCard("), "DashboardLoadingCard is replaced by StateCard")
        XCTAssertFalse(home.contains("struct DashboardLoadingCard"))
        XCTAssertFalse(home.contains(") unavailable\""), "the old 'X unavailable' copy is gone")
        XCTAssertFalse(home.contains("NetworkError.decodingError(viewModel.sectionErrors"),
                       "stored messages are passed verbatim, never wrapped in NetworkError")
        XCTAssertTrue(home.contains("hasLoaded: viewModel.sectionUpdatedAt[id] != nil"))
        XCTAssertGreaterThanOrEqual(home.components(separatedBy: "HomeSectionStateCard(viewModel:").count - 1, 7,
                                    "all 7 absent-data branches use the state card")
    }

    func testAlertsCopyAndLoadedOnceState() throws {
        let alerts = try source("Views/AlertsScreen.swift")
        XCTAssertFalse(alerts.contains("Set a target price from any stock"))
        XCTAssertTrue(alerts.contains("hasLoadedOnce"))
        XCTAssertTrue(alerts.contains("No price alerts yet."))
    }

    func testInboxNoLongerPromisesNotifications() throws {
        let inbox = try source("Views/Core/NotificationInboxView.swift")
        XCTAssertFalse(inbox.contains("We'll notify you when something important happens"))
        XCTAssertTrue(inbox.contains("hasLoaded: hasLoaded"))
        XCTAssertFalse(inbox.contains("try? await NetworkManager.shared.markNotificationRead"))
    }
}
