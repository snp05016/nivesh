import XCTest
@testable import stockme

final class FundamentalsDecodingTests: XCTestCase {
    
    func testFinancialMetricsDecoding() throws {
        let json = """
        {
            "period": "FY23",
            "revenue": "1,45,200 Crores",
            "net_income": "25,300 Crores",
            "eps": 124.50,
            "operating_margin": 21.4,
            "free_cash_flow": "18,900 Crores"
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let metrics = try decoder.decode(FinancialMetrics.self, from: json)
        
        XCTAssertEqual(metrics.period, "FY23")
        XCTAssertEqual(metrics.revenue, "1,45,200 Crores")
        XCTAssertEqual(metrics.netIncome, "25,300 Crores")
        XCTAssertEqual(metrics.eps, 124.50)
        XCTAssertEqual(metrics.operatingMargin, 21.4)
        XCTAssertEqual(metrics.freeCashFlow, "18,900 Crores")
    }
    
    func testShareholdingDecoding() throws {
        let json = """
        {
            "quarter": "Q4 FY23",
            "promoter_pct": 55.4,
            "fii_pct": 20.1,
            "dii_pct": 15.3,
            "public_pct": 9.2,
            "pledged_pct": 0.0
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let shareholding = try decoder.decode(Shareholding.self, from: json)
        
        XCTAssertEqual(shareholding.quarter, "Q4 FY23")
        XCTAssertEqual(shareholding.promoterPct, 55.4)
        XCTAssertEqual(shareholding.fiiPct, 20.1)
    }
    
    func testCorporateActionDecoding() throws {
        let json = """
        {
            "ex_date": "2023-05-15",
            "record_date": "2023-05-16",
            "purpose": "Final Dividend",
            "dividend_amount": 15.50
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let action = try decoder.decode(CorporateActionDTO.self, from: json)
        
        XCTAssertEqual(action.exDate, "2023-05-15")
        XCTAssertEqual(action.purpose, "Final Dividend")
        XCTAssertEqual(action.dividendAmount, 15.50)
    }
    
    func testValuationDecoding() throws {
        let json = """
        {
            "date": "2023-10-01",
            "current_pe": 25.4,
            "forward_pe": 22.1,
            "pb_ratio": 4.5,
            "ev_ebitda": 18.2,
            "market_cap": "5,40,000 Crores"
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let valuation = try decoder.decode(ValuationMetrics.self, from: json)
        
        XCTAssertEqual(valuation.currentPe, 25.4)
        XCTAssertEqual(valuation.marketCap, "5,40,000 Crores")
    }
    
    func testRiskSignalDecoding() throws {
        let json = """
        {
            "date": "2023-10-01",
            "signal_type": "High Debt",
            "severity": "Medium",
            "description": "Company has increased its short-term borrowings."
        }
        """.data(using: .utf8)!
        
        let decoder = JSONDecoder()
        let risk = try decoder.decode(RiskSignalDTO.self, from: json)
        
        XCTAssertEqual(risk.signalType, "High Debt")
        XCTAssertEqual(risk.severity, "Medium")
    }
}
