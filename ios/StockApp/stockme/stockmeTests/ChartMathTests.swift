import XCTest
@testable import stockme

/// IOSUI-26: indicator periods, flat/NaN geometry, range slicing and range-based colour.
@MainActor
final class ChartMathTests: XCTestCase {

    private func days(_ n: Int, from start: String = "2024-01-01") -> [String] {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone.current
        let s = WireDate.day(start)!
        return (0..<n).map { WireDate.dayKey(cal.date(byAdding: .day, value: $0, to: s)!) }
    }

    private func pricePoints(_ n: Int) throws -> [PricePoint] {
        let rows = days(n).enumerated().map { i, d in #"{"date":"\#(d)","close":\#(100 + i)}"# }
        return try JSONDecoder().decode([PricePoint].self, from: Data("[\(rows.joined(separator: ","))]".utf8))
    }

    private func snapshots(pnl: [Double]? = nil, count: Int = 0) throws -> [PortfolioValuationSnapshot] {
        let pnls = pnl ?? Array(repeating: 0, count: count)
        let rows = zip(days(pnls.count), pnls).map { d, p in
            #"{"date":"\#(d)","total_value":1000,"total_invested":900,"total_pnl":\#(p),"pnl_percent":0}"#
        }
        return try JSONDecoder().decode([PortfolioValuationSnapshot].self, from: Data("[\(rows.joined(separator: ","))]".utf8))
    }

    // MARK: SMA

    func testSMA200IsEmptyWithoutTwoHundredPoints() throws {
        XCTAssertTrue(PriceHistoryChart.sma(try pricePoints(150), period: 200).isEmpty)
    }

    func testSMA200UsesTheTruePeriod() throws {
        let sma = PriceHistoryChart.sma(try pricePoints(250), period: 200)
        XCTAssertEqual(sma.count, 51)
        XCTAssertEqual(sma.first?.value ?? 0, 199.5, accuracy: 1e-9) // mean of 100...299
    }

    // MARK: Geometry

    func testFlatSeriesIsVerticallyCentred() {
        let rect = CGRect(x: 0, y: 0, width: 300, height: 200)
        let pts = ImmersiveChartGeometry.points(values: [5, 5, 5], in: rect)
        XCTAssertEqual(pts.count, 3)
        XCTAssertTrue(pts.allSatisfy { $0.y == rect.midY })
    }

    func testNonFiniteValuesNeverReachCoreGraphics() {
        let rect = CGRect(x: 0, y: 0, width: 300, height: 200)
        let pts = ImmersiveChartGeometry.points(values: [1, .nan, 3, .infinity], in: rect)
        XCTAssertEqual(pts.count, 4)
        XCTAssertTrue(pts.allSatisfy { $0.x.isFinite && $0.y.isFinite })
        XCTAssertLessThan(pts[2].y, pts[0].y) // higher value still plots higher
    }

    // MARK: Range slicing + colour

    func testYearRangeIsOneYearNotTheWholeFetch() throws {
        let all = try snapshots(count: 730)
        XCTAssertEqual(all.ranged(.year).count, 366)
        XCTAssertEqual(all.ranged(.all).count, 730)
        XCTAssertEqual(all.ranged(.day).count, 2)
    }

    func testRangeKeepsAtLeastTwoPoints() throws {
        XCTAssertEqual(try snapshots(count: 2).ranged(.day).count, 2)
        XCTAssertTrue([PortfolioValuationSnapshot]().ranged(.year).isEmpty)
    }

    func testColourFollowsPnlChangeOverTheShownRange() throws {
        XCTAssertFalse(try snapshots(pnl: [100, 90, 80]).pnlChangeIsPositive)
        // Lifetime P&L still negative, but it improved over the range.
        XCTAssertTrue(try snapshots(pnl: [-50, -20]).pnlChangeIsPositive)
    }
}
