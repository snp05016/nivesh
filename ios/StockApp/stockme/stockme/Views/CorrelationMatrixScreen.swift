import SwiftUI
import Combine

struct CorrelationItem: Codable, Identifiable {
    var id: String { "\(tickerA)-\(tickerB)" }
    let tickerA: String
    let tickerB: String
    let correlation: Double
    
    init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        tickerA = try container.decode(String.self)
        tickerB = try container.decode(String.self)
        correlation = try container.decode(Double.self)
    }
}

struct CorrelationSector: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let weightPct: Double
    let holdings: [String]
    
    enum CodingKeys: String, CodingKey {
        case sector
        case weightPct = "weight_pct"
        case holdings
    }
}

struct DiversificationSuggestion: Codable, Identifiable {
    var id: String { sector }
    let sector: String
    let reason: String
    let improvementScore: Int
    
    enum CodingKeys: String, CodingKey {
        case sector
        case reason
        case improvementScore = "improvement_score"
    }
}

struct CorrelationResponse: Codable {
    let correlationMatrix: [CorrelationItem]
    let diversificationScore: Int
    let sectorConcentration: [CorrelationSector]
    let suggestions: [DiversificationSuggestion]
    let error: String?
    let message: String?
    let holdingsCount: Int?
    let holdingsTickers: [String]?
    
    enum CodingKeys: String, CodingKey {
        case correlationMatrix = "correlation_matrix"
        case diversificationScore = "diversification_score"
        case sectorConcentration = "sector_concentration"
        case suggestions
        case error
        case message
        case holdingsCount = "holdings_count"
        case holdingsTickers = "holdings_tickers"
    }
}

struct CorrelationMatrixScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var data: CorrelationResponse?
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showHelp = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.xLarge) {
                HelpInlineButton(showHelp: $showHelp)
                    .padding(.horizontal, Theme.screenPadding)
                
                if isLoading {
                    ProgressView("Calculating Matrix...")
                        .padding()
                } else if let error = errorMessage {
                    BanknoteErrorCanvas(
                        title: "Analysis Failed",
                        detail: error,
                        retryAction: loadDataAsync
                    )
                } else if let data = data {
                    
                    // 1. Hero Ring Gauge
                    DiversificationHero(score: data.diversificationScore)
                    
                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                    
                    // 2. Heatmap
                    CorrelationHeatmap(matrix: data.correlationMatrix)
                    
                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                    
                    // 3. Sector Concentration
                    SectorConcentrationView(concentration: data.sectorConcentration)
                    
                    if !data.suggestions.isEmpty {
                        GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                        // 4. Suggestions
                        SuggestionsView(suggestions: data.suggestions)
                    }
                }
            }
            .padding(.vertical, Theme.screenPadding)
        }
        .background(Theme.canvasDeep.edgesIgnoringSafeArea(.all))
        .navigationTitle("Risk Matrix")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            Task {
                await loadDataAsync()
            }
        }
        .helpSheet(isPresented: $showHelp, title: FeatureHelp.correlation.title, subtitle: FeatureHelp.correlation.subtitle, sections: FeatureHelp.correlation.sections)
    }
    
    private func loadDataAsync() async {
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        do {
            guard let token = authManager.currentUser?.token else {
                await MainActor.run {
                    self.errorMessage = "Sign in required to view portfolio correlation."
                    self.isLoading = false
                }
                return
            }
            
            let url = URL(string: "\(NetworkManager.shared.baseURL)/portfolio/correlation?portfolio_id=holdings")!
            var req = URLRequest(url: url, timeoutInterval: 90)
            req.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            
            let (respData, res) = try await URLSession.shared.data(for: req)
            
            guard let http = res as? HTTPURLResponse else {
                throw NSError(domain: "", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid server response."])
            }
            
            if http.statusCode == 401 {
                throw NSError(domain: "", code: 401, userInfo: [NSLocalizedDescriptionKey: "Session expired. Please sign in again."])
            }
            
            guard http.statusCode == 200 else {
                // Try to extract server error detail from response body
                var serverDetail = ""
                if let body = String(data: respData, encoding: .utf8) {
                    // Try JSON error detail
                    if let json = try? JSONSerialization.jsonObject(with: respData) as? [String: Any],
                       let detail = json["detail"] as? String {
                        serverDetail = detail
                    } else if let json = try? JSONSerialization.jsonObject(with: respData) as? [String: Any],
                              let errorMsg = json["error"] as? String {
                        serverDetail = errorMsg
                    } else {
                        // Use first 200 chars of raw body
                        serverDetail = String(body.prefix(200))
                    }
                }
                let detail = serverDetail.isEmpty ? "No details from server." : serverDetail
                throw NSError(domain: "", code: http.statusCode, 
                    userInfo: [NSLocalizedDescriptionKey: "Server error \(http.statusCode): \(detail)"])
            }
            
            let decoded = try JSONDecoder().decode(CorrelationResponse.self, from: respData)
            await MainActor.run {
                self.data = decoded
                self.isLoading = false
            }
        } catch {
            let nsErr = error as NSError
            let msg: String
            if nsErr.domain == NSURLErrorDomain {
                switch nsErr.code {
                case NSURLErrorTimedOut:
                    msg = "Server is taking too long. Large portfolios may need more time — please try again."
                case NSURLErrorCannotConnectToHost, NSURLErrorNetworkConnectionLost:
                    msg = "Cannot reach server. Check your internet connection."
                case NSURLErrorNotConnectedToInternet:
                    msg = "No internet connection."
                default:
                    msg = error.localizedDescription
                }
            } else {
                msg = nsErr.localizedDescription
            }
            await MainActor.run {
                self.errorMessage = msg
                self.isLoading = false
            }
        }
    }
}

// MARK: - Subviews

struct DiversificationHero: View {
    let score: Int
    
    var color: Color {
        if score > 70 { return Theme.bullGreen }
        if score > 40 { return Theme.holdAmber }
        return Theme.bearRed
    }
    
    var body: some View {
        VStack(spacing: Theme.Spacing.standard) {
            Text("Diversification Score")
                .font(Theme.officialStampFont(size: 14, relativeTo: .caption))
                .foregroundColor(Theme.inkSecondary)
                .textCase(.uppercase)
            
            ZStack {
                Circle()
                    .stroke(Theme.borderFine, lineWidth: 12)
                    .frame(width: 140, height: 140)
                
                Circle()
                    .trim(from: 0, to: CGFloat(score) / 100.0)
                    .stroke(color, style: StrokeStyle(lineWidth: 12, lineCap: .round))
                    .frame(width: 140, height: 140)
                    .rotationEffect(.degrees(-90))
                    .animation(.easeOut(duration: 1.0), value: score)
                
                VStack(spacing: Theme.Spacing.xSmall) {
                    Text("\(score)")
                        .font(Theme.serialNumberFont(size: 48, relativeTo: .largeTitle))
                        .foregroundColor(Theme.inkPrimary)
                    Text("/ 100")
                        .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                        .foregroundColor(Theme.inkTertiary)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct CorrelationHeatmap: View {
    let matrix: [CorrelationItem]
    
    var uniqueTickers: [String] {
        var set = Set<String>()
        for item in matrix {
            set.insert(item.tickerA)
            set.insert(item.tickerB)
        }
        return Array(set).sorted()
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Holdings Correlation")
                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
                .padding(.horizontal, Theme.screenPadding)
            
            if uniqueTickers.isEmpty {
                Text("Not enough data to compute correlation.")
                    .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                    .foregroundColor(Theme.inkSecondary)
                    .padding(.horizontal, Theme.screenPadding)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        // Header row
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Text("")
                                .frame(width: 60, height: 30)
                            ForEach(uniqueTickers, id: \.self) { t in
                                Text(t.prefix(4))
                                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                    .foregroundColor(Theme.inkSecondary)
                                    .frame(width: 40, height: 30)
                            }
                        }
                        
                        ForEach(uniqueTickers, id: \.self) { t1 in
                            HStack(spacing: Theme.Spacing.xSmall) {
                                Text(t1.prefix(4))
                                    .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                                    .foregroundColor(Theme.inkSecondary)
                                    .frame(width: 60, alignment: .trailing)
                                
                                ForEach(uniqueTickers, id: \.self) { t2 in
                                    HeatmapCell(t1: t1, t2: t2, matrix: matrix)
                                }
                            }
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
    }
}

struct HeatmapCell: View {
    let t1: String
    let t2: String
    let matrix: [CorrelationItem]
    
    var correlation: Double {
        if t1 == t2 { return 1.0 }
        let match = matrix.first { ($0.tickerA == t1 && $0.tickerB == t2) || ($0.tickerA == t2 && $0.tickerB == t1) }
        return match?.correlation ?? 0.0
    }
    
    var color: Color {
        if correlation > 0.7 { return Theme.bearRed }
        if correlation > 0.4 { return Theme.holdAmber }
        if correlation < -0.4 { return Theme.bullGreen }
        return Theme.inkTertiary
    }
    
    var body: some View {
        ZStack {
            color.opacity(max(0.1, abs(correlation)))
            Text(String(format: "%.2f", correlation))
                .font(Theme.serialNumberFont(size: 10, relativeTo: .caption2))
                .foregroundColor(Theme.inkPrimary)
        }
        .frame(width: 40, height: 40)
        .cornerRadius(Theme.CornerRadius.small)
    }
}

struct SectorConcentrationView: View {
    let concentration: [CorrelationSector]
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Sector Concentration")
                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
            
            VStack(spacing: Theme.Spacing.standard) {
                ForEach(concentration) { item in
                    HStack {
                        Text(item.sector)
                            .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                            .foregroundColor(Theme.inkPrimary)
                        Spacer()
                        Text("\(Int(item.weightPct))%")
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(item.weightPct > 40 ? Theme.bearRed : Theme.inkSecondary)
                    }
                    
                    if item.weightPct > 40 {
                        HStack {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(Theme.bearRed)
                            Text("\(item.sector) \(Int(item.weightPct))% = HIGH RISK")
                                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                                .foregroundColor(Theme.bearRed)
                            Spacer()
                        }
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}

struct SuggestionsView: View {
    let suggestions: [DiversificationSuggestion]
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.card) {
            Text("Diversification Advice")
                .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                .foregroundColor(Theme.inkPrimary)
            
            ForEach(suggestions) { sug in
                VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                    Text(sug.reason)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                    
                    HStack {
                        Text("Add \(sug.sector)")
                            .font(Theme.officialStampFont(size: 14, relativeTo: .caption))
                            .foregroundColor(Theme.inkPrimary)
                        Spacer()
                        Text("Score → \(sug.improvementScore)")
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .caption))
                            .foregroundColor(Theme.bullGreen)
                    }
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
}
