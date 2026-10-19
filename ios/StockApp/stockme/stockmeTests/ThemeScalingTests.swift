import XCTest
import UIKit
@testable import stockme

/// UX-07: Theme font helpers must follow Dynamic Type (clamped at AX2), keep a
/// micro-text floor, and still apply the in-app Font Size multiplier.
@MainActor
final class ThemeScalingTests: XCTestCase {

    private let fontSizeKey = "nivesh_fontSize"
    private var savedFontSize: Any?

    override func setUp() {
        super.setUp()
        savedFontSize = UserDefaults.standard.object(forKey: fontSizeKey)
        UserDefaults.standard.removeObject(forKey: fontSizeKey)
    }

    override func tearDown() {
        if let savedFontSize {
            UserDefaults.standard.set(savedFontSize, forKey: fontSizeKey)
        } else {
            UserDefaults.standard.removeObject(forKey: fontSizeKey)
        }
        super.tearDown()
    }

    func testGrowsWithContentSizeCategory() {
        let standard = Theme.scaledSize(14, relativeTo: .body, category: .large)
        let ax1 = Theme.scaledSize(14, relativeTo: .body, category: .accessibilityMedium)
        XCTAssertGreaterThan(ax1, standard)
    }

    func testClampsAtAX2() {
        let ax2 = Theme.scaledSize(14, relativeTo: .body, category: .accessibilityLarge)
        let ax5 = Theme.scaledSize(14, relativeTo: .body, category: .accessibilityExtraExtraExtraLarge)
        XCTAssertEqual(ax5, ax2, accuracy: 0.001)
    }

    func testMicroTextFloor() {
        let size = Theme.scaledSize(8, relativeTo: .caption2, minimum: Theme.microTextFloor, category: .large)
        XCTAssertGreaterThanOrEqual(size, 11)
    }

    /// IOSUI-27: every Theme text helper floors sub-11pt design sizes by default.
    func testDefaultFloorAppliesWithoutExplicitMinimum() {
        XCTAssertEqual(Theme.scaledSize(7, relativeTo: .body, category: .large), 11, accuracy: 0.001)
        XCTAssertEqual(Theme.scaledSize(14, relativeTo: .body, category: .large), 14, accuracy: 0.001)
    }

    func testFontSizeMultiplierApplied() {
        let standard = Theme.scaledSize(14, relativeTo: .body, category: .large)
        UserDefaults.standard.set("Large", forKey: fontSizeKey)
        let large = Theme.scaledSize(14, relativeTo: .body, category: .large)
        XCTAssertEqual(large, standard * 1.15, accuracy: 0.001)
    }
}
