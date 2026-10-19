import XCTest
import SwiftUI
@testable import stockme

/// IOSCORE-13: saved-report deletions survive a relaunch, and one report that no
/// longer decodes does not take the rest of the list with it.
@MainActor
final class LocalReportManagerTests: XCTestCase {

    private var fileURL: URL!

    override func setUp() {
        super.setUp()
        fileURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("reports-\(UUID().uuidString).json")
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: fileURL)
        try? FileManager.default.removeItem(at: LocalReportManager(fileURL: fileURL).backupURL)
        super.tearDown()
    }

    private func reportJSON(_ ticker: String, date: String) -> String {
        """
        {"ticker":"\(ticker)","company_name":"\(ticker) Ltd","analysis_date":"\(date)",
         "signal":"HOLD","confidence_pct":60,"current_price_inr":100.0,
         "target_prices":{"short_term_3m":105,"medium_term_12m":110,"long_term_36m":130},
         "upside_downside_pct":{"short_term":5,"medium_term":10,"long_term":30},
         "bull_case":[],"bear_case":[],"key_risks":[],
         "key_factors":{"management_quality":"","geopolitical_context":"","promoter_fii_dii_activity":"",
                        "turnaround_story":"","fundamentals_summary":"","global_macro_impact":"","news_sentiment":""},
         "fundamentals_snapshot":{},"what_to_watch":[],"disclaimer":"Not advice."}
        """
    }

    private func writeFile(_ elements: [String]) throws {
        try Data("[\(elements.joined(separator: ","))]".utf8).write(to: fileURL)
    }

    func testDeleteAllPersists() throws {
        try writeFile([reportJSON("TCS", date: "2026-10-01"), reportJSON("INFY", date: "2026-10-02")])
        let manager = LocalReportManager(fileURL: fileURL)
        XCTAssertEqual(manager.savedReports.count, 2)

        manager.savedReports.removeAll()   // what "Delete All" / "Void" do

        XCTAssertTrue(LocalReportManager(fileURL: fileURL).savedReports.isEmpty)
    }

    func testDeleteAtOffsetsPersists() throws {
        try writeFile([reportJSON("TCS", date: "2026-10-01"), reportJSON("INFY", date: "2026-10-02")])
        let manager = LocalReportManager(fileURL: fileURL)

        manager.savedReports.remove(atOffsets: IndexSet(integer: 0))   // swipe-to-delete

        XCTAssertEqual(LocalReportManager(fileURL: fileURL).savedReports.map(\.ticker), ["TCS"])
    }

    func testCorruptElementIsSkipped() throws {
        try writeFile([reportJSON("TCS", date: "2026-10-01"), #"{"garbage":1}"#])

        let manager = LocalReportManager(fileURL: fileURL)

        XCTAssertEqual(manager.savedReports.map(\.ticker), ["TCS"])
    }

    /// A schema change (here: a required key missing) must not wipe history:
    /// init leaves the file alone, and the original bytes survive in the
    /// backup even after the next save rewrites the file.
    func testUndecodableReportIsBackedUpNotDeleted() throws {
        let original = reportJSON("TCS", date: "2026-10-01").replacingOccurrences(of: #""signal":"HOLD","#, with: "")
        try writeFile([original])
        let bytes = try Data(contentsOf: fileURL)

        let manager = LocalReportManager(fileURL: fileURL)

        XCTAssertTrue(manager.savedReports.isEmpty)
        XCTAssertEqual(try Data(contentsOf: fileURL), bytes, "load must not rewrite the file")
        XCTAssertEqual(try Data(contentsOf: manager.backupURL), bytes)

        manager.saveReport(try JSONDecoder().decode(StockAnalysis.self, from: Data(reportJSON("INFY", date: "2026-10-02").utf8)))

        XCTAssertEqual(try Data(contentsOf: manager.backupURL), bytes, "backup must survive later saves")
    }
}
