import SwiftUI
import Charts

struct StressTestResponse: Codable {
    let results: [StressTestResult]
}

struct StressTestResult: Codable, Identifiable {
    var id: String { name }
    let name: String
    let impactPct: Double
    let impactInr: Double
    let holdings: [StressTestHolding]
    
    enum CodingKeys: String, CodingKey {
        case name
        case impactPct = "impact_pct"
        case impactInr = "impact_inr"
        case holdings
    }
}

struct StressTestHolding: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let impactPct: Double
    let impactInr: Double
    
    enum CodingKeys: String, CodingKey {
        case ticker
        case impactPct = "impact_pct"
        case impactInr = "impact_inr"
    }
}

class StressTestViewModel: ObservableObject {
    @Published var selectedScenarios: Set<String> = []
    @Published var results: [StressTestResult] = []
    @Published var isLoading = false
    @Published var errorMessage: String? = nil
    
    let scenarios = [
        ("NIFTY_CRASH", "Nifty Crash", "chart.line.down.right"),
        ("OIL_SHOCK", "Oil Shock", "drop.fill"),
        ("RATE_HIKE", "Rate Hike", "arrow.up.right.circle"),
        ("FII_EXODUS", "FII Exodus", "airplane.departure"),
        ("GLOBAL_RECESSION", "Recession", "globe.americas"),
        ("POLICY_SHOCK", "Policy Shock", "building.columns"),
        ("CURRENCY_CRASH", "Currency Crash", "indianrupeesign.circle"),
        ("CUSTOM", "Custom", "slider.horizontal.3")
    ]
    
    func toggleScenario(_ id: String) {
        if selectedScenarios.contains(id) {
            selectedScenarios.remove(id)
        } else {
            if selectedScenarios.count < 3 {
                selectedScenarios.insert(id)
            }
        }
        HapticManager.selection()
    }
    
    func runTest() {
        guard !selectedScenarios.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        
        Task {
            do {
                guard let userId = AuthManager.shared.getUserId() else {
                    throw NSError(domain: "", code: -1, userInfo: [NSLocalizedDescriptionKey: "Not logged in"])
                }
                
                guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/portfolio/stress-test") else {
                    throw NSError(domain: "", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"])
                }
                
                var request = URLRequest(url: url)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                if let token = AuthManager.shared.getToken() {
                    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                } else {
                    request.setValue(String(userId), forHTTPHeaderField: "user_id")
                }
                
                let body: [String: Any] = [
                    "scenarios": Array(selectedScenarios),
                    "portfolio_id": "holdings"
                ]
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
                
                let (data, response) = try await URLSession.shared.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
                    throw NSError(domain: "", code: -1, userInfo: [NSLocalizedDescriptionKey: "Server error"])
                }
                
                let decoded = try JSONDecoder().decode(StressTestResponse.self, from: data)
                
                DispatchQueue.main.async {
                    self.results = decoded.results
                    self.isLoading = false
                    HapticManager.success()
                }
            } catch {
                DispatchQueue.main.async {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                    HapticManager.error()
                }
            }
        }
    }
}

struct StressTestScreen: View {
    @StateObject private var vm = StressTestViewModel()
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.xLarge) {
                // HERO
                VStack(spacing: Theme.Spacing.standard) {
                    Text("Stress Test")
                        .font(Theme.engravedSerif(size: 32, weight: .bold, relativeTo: .largeTitle))
                        .foregroundColor(Theme.inkPrimary)
                    
                    Text("Simulate market shocks to evaluate your portfolio's resilience.")
                        .font(Theme.roundedSecondary(size: 14, weight: .regular, relativeTo: .body))
                        .foregroundColor(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, Theme.Spacing.screen)
                
                // SCENARIO CHIPS
                VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                    Text("SCENARIOS (Select up to 3)")
                        .font(Theme.sectionCapsLabel())
                        .foregroundColor(Theme.inkTertiary)
                        .padding(.horizontal, Theme.Spacing.screen)
                    
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Theme.Spacing.standard) {
                            ForEach(vm.scenarios, id: \.0) { id, name, icon in
                                let isSelected = vm.selectedScenarios.contains(id)
                                Button {
                                    vm.toggleScenario(id)
                                } label: {
                                    HStack(spacing: Theme.Spacing.small) {
                                        Image(systemName: icon)
                                            .font(.system(size: 14))
                                        Text(name)
                                            .font(Theme.roundedSecondary(size: 14, weight: .medium, relativeTo: .subheadline))
                                    }
                                    .padding(.horizontal, Theme.Spacing.card)
                                    .padding(.vertical, Theme.Spacing.standard)
                                    .background(isSelected ? Theme.securityGoldLight : Theme.canvasDeep)
                                    .foregroundColor(isSelected ? Theme.securityGold : Theme.inkSecondary)
                                    .overlay(
                                        RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                                            .strokeBorder(isSelected ? Theme.securityGold : Theme.borderFine, lineWidth: 1)
                                    )
                                    .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.card))
                                }
                                .buttonStyle(EKPressStyle())
                            }
                        }
                        .padding(.horizontal, Theme.Spacing.screen)
                    }
                }
                
                // RUN BUTTON
                Button {
                    vm.runTest()
                    HapticManager.impact(.medium)
                } label: {
                    Text("Run Simulation")
                        .font(Theme.roundedSecondary(size: 16, weight: .semibold, relativeTo: .headline))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.card)
                        .background(vm.selectedScenarios.isEmpty ? Theme.canvasDeep : Theme.inkPrimary)
                        .foregroundColor(vm.selectedScenarios.isEmpty ? Theme.inkTertiary : Theme.canvas)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                }
                .disabled(vm.selectedScenarios.isEmpty || vm.isLoading)
                .buttonStyle(EKPressStyle())
                .padding(.horizontal, Theme.Spacing.screen)
                
                GuillocheDivider().padding(.horizontal, Theme.Spacing.screen)
                
                // RESULTS
                if vm.isLoading {
                    ProgressView("Running Simulations...")
                        .padding(.vertical, Theme.Spacing.xLarge)
                } else if let error = vm.errorMessage {
                    Text(error)
                        .foregroundColor(Theme.bearRed)
                        .padding()
                } else if !vm.results.isEmpty {
                    ForEach(vm.results) { result in
                        VStack(spacing: Theme.Spacing.large) {
                            
                            // SUMMARY CARD
                            VStack(spacing: Theme.Spacing.standard) {
                                Text(result.name)
                                    .font(Theme.engravedSerif(size: 18, weight: .semibold, relativeTo: .title3))
                                    .foregroundColor(Theme.inkPrimary)
                                
                                Text("Portfolio down \(IndianFormatter.formatLakhsCrores(abs(result.impactInr))) (\(IndianFormatter.percent(result.impactPct)))")
                                    .font(Theme.serialNumberFont(size: 16, relativeTo: .headline))
                                    .foregroundColor(result.impactPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                            .padding(.horizontal, Theme.Spacing.screen)
                            
                            // TORNADO CHART
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("HOLDING IMPACT")
                                    .font(Theme.sectionCapsLabel())
                                    .foregroundColor(Theme.inkTertiary)
                                    .padding(.horizontal, Theme.Spacing.screen)
                                
                                Chart(result.holdings.prefix(10)) { h in
                                    BarMark(
                                        x: .value("Impact", h.impactPct),
                                        y: .value("Ticker", h.ticker)
                                    )
                                    .foregroundStyle(h.impactPct >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    .annotation(position: h.impactPct >= 0 ? .trailing : .leading) {
                                        Text(IndianFormatter.percent(h.impactPct))
                                            .font(Theme.microLabel())
                                            .foregroundColor(Theme.inkSecondary)
                                    }
                                }
                                .frame(height: 250)
                                .padding(.horizontal, Theme.Spacing.screen)
                            }
                            
                            // HOLDING CARDS
                            VStack(spacing: Theme.Spacing.standard) {
                                ForEach(result.holdings) { h in
                                    HStack {
                                        Text(h.ticker)
                                            .font(Theme.roundedSecondary(size: 14, weight: .semibold, relativeTo: .subheadline))
                                            .foregroundColor(Theme.inkPrimary)
                                        Spacer()
                                        Text("\(h.impactInr >= 0 ? "+" : "-")\(IndianFormatter.price(abs(h.impactInr))) (\(IndianFormatter.percent(h.impactPct)))")
                                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                            .foregroundColor(h.impactInr >= 0 ? Theme.bullGreen : Theme.bearRed)
                                    }
                                    .padding(Theme.Spacing.standard)
                                    .banknoteCard()
                                    .padding(.horizontal, Theme.Spacing.screen)
                                }
                            }
                            
                            if result.id != vm.results.last?.id {
                                GuillocheDivider().padding(.horizontal, Theme.Spacing.screen)
                            }
                        }
                    }
                }
                
                Spacer(minLength: 40)
            }
        }
        .background(Theme.canvas.edgesIgnoringSafeArea(.all))
        .navigationTitle("Stress Test")
        .navigationBarTitleDisplayMode(.inline)
    }
}
