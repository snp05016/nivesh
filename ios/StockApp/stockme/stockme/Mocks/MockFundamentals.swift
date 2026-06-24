import Foundation

public struct MockFundamentals {
    
    public static let mockFinancials: [FinancialMetrics] = [
        FinancialMetrics(period: "FY23", revenue: "1,45,200 Crores", netIncome: "25,300 Crores", eps: 124.50, operatingMargin: 21.4, freeCashFlow: "18,900 Crores"),
        FinancialMetrics(period: "FY22", revenue: "1,25,100 Crores", netIncome: "21,100 Crores", eps: 105.20, operatingMargin: 20.1, freeCashFlow: "15,200 Crores"),
        FinancialMetrics(period: "FY21", revenue: "1,10,000 Crores", netIncome: "18,500 Crores", eps: 85.40, operatingMargin: 19.5, freeCashFlow: "12,000 Crores")
    ]
    
    public static let mockShareholding: [Shareholding] = [
        Shareholding(quarter: "Q4 FY23", promoterPct: 55.4, fiiPct: 20.1, diiPct: 15.3, publicPct: 9.2, pledgedPct: 0.0),
        Shareholding(quarter: "Q3 FY23", promoterPct: 55.4, fiiPct: 19.8, diiPct: 15.5, publicPct: 9.3, pledgedPct: 0.0)
    ]
    
    public static let mockCorporateActions: [CorporateActionDTO] = [
        CorporateActionDTO(exDate: "2023-05-15", recordDate: "2023-05-16", purpose: "Final Dividend", dividendAmount: 15.50),
        CorporateActionDTO(exDate: "2022-11-10", recordDate: "2022-11-11", purpose: "Interim Dividend", dividendAmount: 10.00),
        CorporateActionDTO(exDate: "2021-07-20", recordDate: "2021-07-21", purpose: "Bonus Issue 1:1", dividendAmount: nil)
    ]
    
    public static let mockValuation = ValuationMetrics(
        date: "2023-10-01",
        currentPe: 25.4,
        forwardPe: 22.1,
        pbRatio: 4.5,
        evEbitda: 18.2,
        marketCap: "5,40,000 Crores"
    )
    
    public static let mockRiskSignals: [RiskSignalDTO] = [
        RiskSignalDTO(date: "2023-10-01", signalType: "High Debt", severity: "Medium", description: "Company has increased its short-term borrowings by 15%."),
        RiskSignalDTO(date: "2023-09-15", signalType: "Promoter Pledge", severity: "Low", description: "Promoter pledging remains at 0%.")
    ]
    
    public static let mockFundamentalsResponse = FundamentalsResponse(
        ticker: "RELIANCE",
        financials: mockFinancials,
        shareholding: mockShareholding,
        corporateActions: mockCorporateActions,
        valuation: mockValuation,
        riskSignals: mockRiskSignals
    )
}
