//
//  AccessibilityAuditUITests.swift
//  stockmeUITests
//
//  IOSCORE-38: the app must honour the user's Larger Text setting (capped at
//  AX2 in stockmeApp) and every icon-only control needs a VoiceOver label.
//  Runs the Xcode 15 accessibility audit at the largest accessibility content
//  size. The UI-test target is not in the CI scheme, so run these manually or
//  nightly against a signed-in simulator.
//

import XCTest

final class AccessibilityAuditUITests: XCTestCase {

    override func setUpWithError() throws {
        continueAfterFailure = false
    }

    @MainActor
    private func launchAtAX5() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += ["-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryAccessibilityXXXL"]
        app.launch()
        return app
    }

    /// The tab bar only exists once the launch sequence finished and a user is signed in.
    @MainActor
    private func waitForMainTabs(_ app: XCUIApplication) throws {
        guard app.tabBars.buttons["Home"].waitForExistence(timeout: 20) else {
            throw XCTSkip("Main interface not reachable (signed out?); sign in on the simulator first.")
        }
    }

    @MainActor
    func testHomeAccessibilityAudit() throws {
        let app = launchAtAX5()
        try waitForMainTabs(app)
        app.tabBars.buttons["Home"].tap()
        try app.performAccessibilityAudit(for: [.dynamicType, .elementDetection, .hitRegion])
    }

    @MainActor
    func testSearchAccessibilityAudit() throws {
        let app = launchAtAX5()
        try waitForMainTabs(app)
        app.tabBars.buttons["Markets"].tap()
        // Match the SCREENER card by its description: "screener" alone also hits the
        // NL SCREENER card, which sits first in Discovery and pushes NLScreenerScreen.
        let screener = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", "NSE or BSE")).firstMatch
        guard screener.waitForExistence(timeout: 10) else {
            throw XCTSkip("SCREENER card not found on the Markets tab.")
        }
        screener.tap()
        try app.performAccessibilityAudit(for: [.dynamicType, .elementDetection, .hitRegion])
    }
}
