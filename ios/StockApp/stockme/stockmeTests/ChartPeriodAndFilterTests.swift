import XCTest
@testable import stockme

/// IOSUI-21 / IOSUI-18: controls change what is shown.
@MainActor
final class ChartPeriodAndFilterTests: XCTestCase {

    func testPeriodSlicesHistory() {
        let five = Array(0..<500)
        XCTAssertEqual(InteractivePriceChartView.slice(five, period: "1mo", zoom: 1).count, 21)
        XCTAssertEqual(InteractivePriceChartView.slice(five, period: "1y", zoom: 1).count, 252)
        XCTAssertEqual(InteractivePriceChartView.slice(five, period: "1y", zoom: 2).count, 126)
        XCTAssertEqual(InteractivePriceChartView.slice(Array(0..<300), period: "2y", zoom: 1).count, 300)
        XCTAssertEqual(InteractivePriceChartView.slice(five, period: "1mo", zoom: 10).count, 10, "never fewer than 10 points")
        XCTAssertEqual(InteractivePriceChartView.slice(five, period: "1mo", zoom: 1).last, 499, "keeps the most recent points")
        XCTAssertTrue(InteractivePriceChartView.slice([Int](), period: "1y", zoom: 1).isEmpty)
    }

    private func earnings(_ ticker: String, cap: String) throws -> EarningsResult {
        let json = #"{"ticker":"\#(ticker)","company_name":"\#(ticker)","quarter":"Q2FY27","result_date":"2026-10-08","market_cap":"\#(cap)","revenue":100,"revenue_prev":90,"net_profit":10,"net_profit_prev":9,"ltp":1000,"change_percent":1.2,"is_consolidated":true}"#
        return try JSONDecoder().decode(EarningsResult.self, from: Data(json.utf8))
    }

    func testEarningsCapFilter() throws {
        let feed = [try earnings("A", cap: "large_cap"), try earnings("B", cap: "mid_cap"), try earnings("C", cap: "mid_cap")]
        XCTAssertEqual(EarningsDashboardViewModel.filter(feed, marketCap: "mid_cap").map(\.ticker), ["B", "C"])
        XCTAssertEqual(EarningsDashboardViewModel.filter(feed, marketCap: "all").count, 3)
        XCTAssertTrue(EarningsDashboardViewModel.filter(feed, marketCap: "small_cap").isEmpty)
    }

    private func holding(_ ticker: String, buy: Double, now: Double) -> PortfolioHolding {
        PortfolioHolding(
            stock: Stock(ticker: ticker, companyName: ticker, exchange: "NSE", currentPrice: now, changePercent: 0, signal: nil),
            shares: 1, buyPrice: buy, purchaseDate: nil, notes: nil, targetPrice: nil
        )
    }

    /// IOSUI-18: with few holdings, gainers and losers never list the same stock.
    func testBriefPerformersDoNotOverlap() {
        let holdings = [holding("UP1", buy: 100, now: 120), holding("UP2", buy: 100, now: 105), holding("DN1", buy: 100, now: 90)]
        let split = PortfolioBriefSheet.performers(holdings)
        XCTAssertEqual(split.top.map(\.id), ["UP1", "UP2"])
        XCTAssertEqual(split.attention.map(\.id), ["DN1"])
        XCTAssertTrue(PortfolioBriefSheet.performers([holding("FLAT", buy: 100, now: 100)]).top.isEmpty)
    }
}
