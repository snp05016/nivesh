import Foundation
import Combine

enum ChartTimeframe: String, CaseIterable, Identifiable {
    case oneDay = "1d"
    case oneWeek = "1w"
    case oneMonth = "1mo"
    case threeMonths = "3mo"
    case sixMonths = "6mo"
    case oneYear = "1y"
    case fiveYears = "5y"
    
    var id: String { self.rawValue }
}

struct ChartDataPoint: Identifiable, Equatable {
    let id = UUID()
    let date: Date
    let price: Double
}

@MainActor
class ChartViewModel: ObservableObject {
    @Published var selectedTimeframe: ChartTimeframe = .oneMonth
    @Published var dataPoints: [ChartDataPoint] = []
    @Published var isLoading: Bool = false
    @Published var selectedPoint: ChartDataPoint?
    
    @Published var errorMessage: String?
    
    let ticker: String
    let exchange: String
    
    init(ticker: String, exchange: String = "NSE") {
        self.ticker = ticker
        self.exchange = exchange
        loadData()
    }
    
    func loadData() {
        isLoading = true
        errorMessage = nil
        selectedPoint = nil
        
        Task {
            if let response = await NetworkManager.shared.fetchStockHistory(ticker: ticker, exchange: exchange, period: selectedTimeframe.rawValue) {
                self.dataPoints = response.prices.map { ChartDataPoint(date: $0.parsedDate, price: $0.close) }
                self.isLoading = false
            } else {
                self.errorMessage = "Failed to load chart data."
                self.isLoading = false
            }
        }
    }
    
    func setTimeframe(_ timeframe: ChartTimeframe) {
        guard selectedTimeframe != timeframe else { return }
        selectedTimeframe = timeframe
        loadData()
    }
    
    // For drag gestures on the chart to inspect points
    func updateSelectedPoint(at date: Date?) {
        guard let date = date else {
            selectedPoint = nil
            return
        }
        // Find the closest point
        let closest = dataPoints.min { abs($0.date.timeIntervalSince(date)) < abs($1.date.timeIntervalSince(date)) }
        selectedPoint = closest
    }
}
