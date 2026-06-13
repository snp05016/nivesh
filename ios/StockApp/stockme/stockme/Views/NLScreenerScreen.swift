import SwiftUI
import Combine

// MARK: - Models
struct NLScreenerRequest: Codable {
    let query: String
}

struct NLScreenerResponse: Codable {
    let parsedFilters: [String: String]?
    let results: [NLScreenerResult]
    
    enum CodingKeys: String, CodingKey {
        case parsedFilters = "parsed_filters"
        case results
    }
}

struct NLScreenerResult: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let company: String
    let score: Double
    let reason: String
    let sector: String?
}

// MARK: - ViewModel
@MainActor
class NLScreenerViewModel: ObservableObject {
    @Published var query: String = ""
    @Published var parsedFilters: [String: String] = [:]
    @Published var results: [NLScreenerResult] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String?
    
    @Published var history: [String] = []
    
    init() {
        loadHistory()
    }
    
    func loadHistory() {
        if let saved = UserDefaults.standard.stringArray(forKey: "NLScreenerHistory") {
            history = saved
        }
    }
    
    func saveToHistory(_ newQuery: String) {
        if !history.contains(newQuery) {
            history.insert(newQuery, at: 0)
            if history.count > 5 {
                history = Array(history.prefix(5))
            }
            UserDefaults.standard.set(history, forKey: "NLScreenerHistory")
        }
    }
    
    func performSearch(searchQuery: String? = nil) {
        let textToSearch = searchQuery ?? query
        guard !textToSearch.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        
        query = textToSearch
        saveToHistory(textToSearch)
        
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/screener/natural-language") else { return }
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                
                let reqBody = NLScreenerRequest(query: textToSearch)
                request.httpBody = try JSONEncoder().encode(reqBody)
                
                let (data, response) = try await URLSession.shared.data(for: request)
                
                guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                    throw URLError(.badServerResponse)
                }
                
                let apiResponse = try JSONDecoder().decode(NLScreenerResponse.self, from: data)
                
                var filterDict: [String: String] = [:]
                for (key, val) in apiResponse.parsedFilters ?? [:] {
                    filterDict[key] = val
                }
                
                self.parsedFilters = filterDict
                self.results = apiResponse.results
                self.isLoading = false
            } catch {
                self.errorMessage = "Failed to load results: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
}

// MARK: - View
struct NLScreenerScreen: View {
    @StateObject private var viewModel = NLScreenerViewModel()
    
    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()
                
                VStack(spacing: Theme.Spacing.standard) {
                    searchBar
                    
                    if viewModel.isLoading {
                        Spacer()
                        ProgressView("Analyzing query...")
                        Spacer()
                    } else if let error = viewModel.errorMessage {
                        Spacer()
                        Text(error)
                            .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                            .foregroundColor(Theme.bearRed)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, Theme.screenPadding)
                        Spacer()
                    } else {
                        ScrollView {
                            VStack(spacing: Theme.Spacing.card) {
                                if !viewModel.parsedFilters.isEmpty {
                                    filtersSection
                                    GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                                }
                                
                                if !viewModel.results.isEmpty {
                                    resultsSection
                                } else if !viewModel.query.isEmpty && !viewModel.isLoading {
                                    Text("No stocks matched your criteria.")
                                        .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                                        .foregroundColor(Theme.inkSecondary)
                                        .padding(.top, Theme.sectionSpacing)
                                } else {
                                    historySection
                                }
                            }
                            .padding(.bottom, Theme.screenPadding)
                        }
                    }
                }
            }
            .navigationTitle("NL Screener")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
    
    private var searchBar: some View {
        HStack(spacing: Theme.Spacing.standard) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(Theme.inkSecondary)
            
            TextField("Ask in plain English...", text: $viewModel.query)
                .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
                .onSubmit {
                    viewModel.performSearch()
                }
            
            if !viewModel.query.isEmpty {
                Button(action: {
                    viewModel.query = ""
                    HapticManager.selection()
                }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
            }
            
            Button(action: {
                HapticManager.selection()
            }) {
                Image(systemName: "mic.fill")
                    .foregroundColor(Theme.securityGold)
            }
            .buttonStyle(EKPressStyle())
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.large)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                .stroke(Theme.borderFine, lineWidth: 1)
        )
        .padding(.horizontal, Theme.screenPadding)
        .padding(.top, Theme.Spacing.standard)
    }
    
    private var filtersSection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            Text("Understood Filters:")
                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                .foregroundColor(Theme.inkSecondary)
                .padding(.horizontal, Theme.screenPadding)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: Theme.Spacing.standard) {
                    ForEach(Array(viewModel.parsedFilters.keys.sorted()), id: \.self) { key in
                        HStack(spacing: Theme.Spacing.small) {
                            Text(key)
                                .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                                .foregroundColor(Theme.inkSecondary)
                            Text(viewModel.parsedFilters[key] ?? "")
                                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                .foregroundColor(Theme.inkPrimary)
                        }
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.canvasShadow)
                        .cornerRadius(Theme.CornerRadius.medium)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                .stroke(Theme.borderFine, lineWidth: 1)
                        )
                    }
                }
                .padding(.horizontal, Theme.screenPadding)
            }
        }
        .padding(.top, Theme.Spacing.small)
    }
    
    private var resultsSection: some View {
        LazyVStack(spacing: Theme.Spacing.card) {
            ForEach(viewModel.results) { result in
                NavigationLink(destination: StockProfileView(ticker: result.ticker)) {
                    ResultCard(result: result)
                }
                .buttonStyle(EKPressStyle())
                .simultaneousGesture(TapGesture().onEnded {
                    HapticManager.selection()
                })
            }
        }
        .padding(.horizontal, Theme.screenPadding)
    }
    
    private var historySection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            if !viewModel.history.isEmpty {
                Text("Recent Searches")
                    .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                    .foregroundColor(Theme.inkSecondary)
                    .padding(.horizontal, Theme.screenPadding)
                    .padding(.top, Theme.Spacing.large)
                
                ForEach(viewModel.history, id: \.self) { h in
                    Button(action: {
                        HapticManager.selection()
                        viewModel.performSearch(searchQuery: h)
                    }) {
                        HStack {
                            Image(systemName: "clock")
                                .foregroundColor(Theme.inkTertiary)
                            Text(h)
                                .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                                .foregroundColor(Theme.inkPrimary)
                                .lineLimit(1)
                            Spacer()
                            Image(systemName: "arrow.up.left")
                                .foregroundColor(Theme.inkTertiary)
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
        }
    }
}

struct ResultCard: View {
    let result: NLScreenerResult
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(result.ticker)
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    Text(result.company)
                        .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(1)
                }
                Spacer()
                
                Text("\(Int(result.score))%")
                    .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                    .foregroundColor(Theme.canvas)
                    .padding(.horizontal, Theme.Spacing.standard)
                    .padding(.vertical, Theme.Spacing.tight)
                    .background(result.score >= 80 ? Theme.bullGreen : Theme.holdAmber)
                    .cornerRadius(Theme.CornerRadius.small)
            }
            
            if let sector = result.sector {
                Text(sector.uppercased())
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                    .foregroundColor(Theme.inkTertiary)
            }
            
            Text(result.reason)
                .font(Theme.engravedSerif(size: 12, relativeTo: .caption))
                .foregroundColor(Theme.inkPrimary)
                .lineLimit(2)
                .padding(.top, Theme.Spacing.xSmall)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .banknoteCard()
    }
}
