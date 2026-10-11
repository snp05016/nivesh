import XCTest
@testable import stockme

/// CMKT-07: QuantLab metrics decoded as zeros (let-with-default) and regime rows failed
/// (convertFromSnakeCase fighting explicit snake_case CodingKeys). QuantLabAPIClient now
/// decodes with a plain JSONDecoder(), so these tests use one too.
final class QuantLabDecodingTests: XCTestCase {

    private let metricsJSON = """
    {
        "gross_return": 0.22, "net_return": 0.2, "cagr": 0.18, "sharpe": 1.2,
        "sortino": 1.5, "max_drawdown": -0.12, "volatility": 0.16, "hit_rate": 0.55,
        "average_win": 0.04, "average_loss": -0.02, "profit_factor": 1.8, "turnover": 0.3,
        "average_holding_period": 30.0, "exposure": 0.9, "cash_percentage": 0.1,
        "sector_concentration": 0.25, "drawdown_duration": 14.0, "benchmark_excess_return": 0.05
    }
    """

    func testBacktestResultDecodesMetrics() throws {
        let json = """
        {
            "params": {
                "horizon": "30D", "strategy_type": "confidence_weighted", "top_k": 10,
                "confidence_threshold": 50.0, "position_sizing": "equal_weight",
                "cost_preset": "realistic_retail"
            },
            "metrics": \(metricsJSON),
            "benchmark_metrics": {},
            "statistical_significance": {},
            "trade_count": 42
        }
        """.data(using: .utf8)!

        let result = try JSONDecoder().decode(BacktestResult.self, from: json)

        XCTAssertEqual(result.metrics.cagr, 0.18)
        XCTAssertEqual(result.metrics.sharpe, 1.2)
        XCTAssertEqual(result.metrics.maxDrawdown, -0.12)
        XCTAssertEqual(result.metrics.benchmarkExcessReturn, 0.05)
        XCTAssertEqual(result.metrics.exposure, 0.9)
        XCTAssertEqual(result.params.horizon, "30D")
        XCTAssertEqual(result.params.confidenceThreshold, 50.0)
        XCTAssertNotNil(result.benchmarkMetrics)
        XCTAssertNotNil(result.statisticalSignificance)
    }

    func testRegimeBreakdownDecodes() throws {
        let json = """
        {
            "overall_metrics": \(metricsJSON),
            "regimes": [
                {"regime_name": "BULL", "sample_size": 10, "net_cagr": 0.1,
                 "sharpe": 1.0, "max_drawdown": -0.1, "hit_rate": 0.5},
                {"regime_name": "BEAR", "sample_size": 6, "net_cagr": -0.05,
                 "sharpe": -0.3, "max_drawdown": -0.2, "hit_rate": 0.4}
            ],
            "conclusion": "Insufficient data"
        }
        """.data(using: .utf8)!

        let result = try JSONDecoder().decode(RegimeBreakdownResponse.self, from: json)

        XCTAssertEqual(result.regimes.count, 2)
        XCTAssertEqual(result.regimes.first?.regimeName, "BULL")
        XCTAssertEqual(result.regimes.last?.sampleSize, 6)
        XCTAssertEqual(result.overallMetrics?.cagr, 0.18)
    }

    func testParamsEncodeThreshold50() throws {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        let data = try encoder.encode(BacktestParams())
        let object = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])

        XCTAssertEqual(object["confidence_threshold"] as? Double, 50.0)
        XCTAssertEqual(object["top_k"] as? Int, 10)
        XCTAssertEqual(object["strategy_type"] as? String, "momentum")
    }
}
