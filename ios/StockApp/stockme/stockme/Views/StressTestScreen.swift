import SwiftUI
import Charts
import Combine

// MARK: - API Response Models

struct StressTestJob: Codable {
    let jobId: String
    let status: String

    enum CodingKeys: String, CodingKey {
        case jobId = "job_id"
        case status
    }
}

struct StressTestProgressResponse: Codable {
    let progressPct: Int
    let stage: String
    let tickerCount: Int

    enum CodingKeys: String, CodingKey {
        case progressPct = "progress_pct"
        case stage
        case tickerCount = "ticker_count"
    }
}

struct StressTestJobResponse: Codable {
    let status: String
    let progressPct: Int
    let stage: String
    let results: [StressTestResult]?

    enum CodingKeys: String, CodingKey {
        case status
        case progressPct = "progress_pct"
        case stage
        case results
    }
}

struct StressTestScores: Codable {
    let riskScore: Int
    let stressScore: Int
    let macroFragility: Int
    let liquidityScore: Int
    let concentrationScore: Int
    let tailRiskScore: Int

    enum CodingKeys: String, CodingKey {
        case riskScore = "risk_score"
        case stressScore = "stress_score"
        case macroFragility = "macro_fragility"
        case liquidityScore = "liquidity_score"
        case concentrationScore = "concentration_score"
        case tailRiskScore = "tail_risk_score"
    }
}

struct StressTestResult: Codable, Identifiable {
    var id: String { name }
    let name: String
    let impactPct: Double
    let impactInr: Double
    let holdings: [StressTestHolding]
    let scores: StressTestScores

    enum CodingKeys: String, CodingKey {
        case name
        case impactPct = "impact_pct"
        case impactInr = "impact_inr"
        case holdings
        case scores
    }
}

struct StressTestHolding: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let sector: String
    let value: Double
    let weightPct: Double
    let impactPct: Double
    let impactInr: Double
    let liquidityPenaltyPct: Double
    let liquidityPenaltyInr: Double

    enum CodingKeys: String, CodingKey {
        case ticker
        case companyName = "company_name"
        case sector
        case value
        case weightPct = "weight_pct"
        case impactPct = "impact_pct"
        case impactInr = "impact_inr"
        case liquidityPenaltyPct = "liquidity_penalty_pct"
        case liquidityPenaltyInr = "liquidity_penalty_inr"
    }
}

// MARK: - ViewModel

class StressTestViewModel: ObservableObject {
    @Published var selectedScenarios: Set<String> = []
    @Published var results: [StressTestResult] = []
    @Published var isLoading = false
    @Published var errorMessage: String? = nil

    @Published var progressPct: Int = 0
    @Published var progressStage: String = ""
    @Published var pollingStatus: String = ""

    private var pollingTask: Task<Void, Never>? = nil
    private var baseURL: String { NetworkManager.shared.baseURL }

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

    func runTest(userId: Int, token: String) {
        guard !selectedScenarios.isEmpty else { return }
        isLoading = true
        errorMessage = nil
        results = []
        progressPct = 0
        progressStage = ""
        pollingStatus = ""

        pollingTask?.cancel()

        Task { [weak self] in
            guard let self = self else { return }
            do {
                let body: [String: Any] = [
                    "portfolio_id": "holdings",
                    "scenarios": Array(self.selectedScenarios)
                ]

                var request = URLRequest(url: URL(string: "\(self.baseURL)/api/v1/portfolio/stress-test")!)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                request.httpBody = try JSONSerialization.data(withJSONObject: body)

                let (data, postResponse) = try await URLSession.shared.data(for: request)
                guard let httpResponse = postResponse as? HTTPURLResponse,
                      httpResponse.statusCode == 202 || httpResponse.statusCode == 200 else {
                    throw NSError(domain: "", code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "Server error: could not start stress test"])
                }

                let job = try JSONDecoder().decode(StressTestJob.self, from: data)

                if job.status == "completed" {
                    let jobFull = try JSONDecoder().decode(StressTestJobResponse.self, from: data)
                    await MainActor.run {
                        self.results = jobFull.results ?? []
                        self.isLoading = false
                        HapticManager.success()
                    }
                    return
                }

                await self.startPolling(jobId: job.jobId, token: token)
            } catch {
                await MainActor.run {
                    self.errorMessage = error.localizedDescription
                    self.isLoading = false
                    HapticManager.error()
                }
            }
        }
    }

    private func startPolling(jobId: String, token: String) {
        pollingTask = Task { [weak self] in
            guard let self = self else { return }
            let maxRetries = 300
            var attempts = 0

            while attempts < maxRetries && !Task.isCancelled {
                do {
                    var request = URLRequest(url: URL(string: "\(self.baseURL)/api/v1/portfolio/stress-test/\(jobId)")!)
                    request.httpMethod = "GET"
                    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

                    let (data, _) = try await URLSession.shared.data(for: request)
                    let jobResponse = try JSONDecoder().decode(StressTestJobResponse.self, from: data)

                    await MainActor.run {
                        self.progressPct = jobResponse.progressPct
                        self.progressStage = jobResponse.stage
                        self.pollingStatus = jobResponse.status
                    }

                    if jobResponse.status == "completed" {
                        await MainActor.run {
                            self.results = jobResponse.results ?? []
                            self.isLoading = false
                            self.progressPct = 100
                            HapticManager.success()
                        }
                        return
                    }
                } catch {
                    attempts += 1
                }

                attempts += 1
                try? await Task.sleep(nanoseconds: 1_000_000_000)
            }

            if attempts >= maxRetries {
                await MainActor.run {
                    self.errorMessage = "Stress test is taking longer than expected. Please try again."
                    self.isLoading = false
                    HapticManager.error()
                }
            }
        }
    }

    func cancel() {
        pollingTask?.cancel()
        pollingTask = nil
        isLoading = false
        progressPct = 0
        progressStage = ""
        pollingStatus = ""
    }
}

// MARK: - Screen

struct StressTestScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var vm = StressTestViewModel()
    @State private var showHelp = false

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.xLarge) {
                HelpInlineButton(showHelp: $showHelp)
                    .padding(.horizontal, Theme.screenPadding)

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
                    vm.runTest(userId: authManager.currentUser?.userId ?? 0, token: authManager.currentUser?.token ?? "")
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

                // PROGRESS / LOADING
                if vm.isLoading && !vm.progressStage.isEmpty {
                    VStack(spacing: Theme.Spacing.standard) {
                        ProgressView(value: Double(vm.progressPct), total: 100)
                            .tint(Theme.securityGold)
                            .frame(maxWidth: .infinity)
                            .padding(.horizontal, Theme.Spacing.screen)

                        HStack {
                            Text(vm.progressStage)
                                .font(Theme.roundedSecondary(size: 13, weight: .regular, relativeTo: .caption1))
                                .foregroundColor(Theme.inkSecondary)
                                .lineLimit(2)
                            Spacer()
                            Text("\(vm.progressPct)%")
                                .font(Theme.serialNumberFont(size: 13, relativeTo: .caption1))
                                .foregroundColor(Theme.securityGold)
                        }
                        .padding(.horizontal, Theme.Spacing.screen)

                        Button {
                            vm.cancel()
                            HapticManager.selection()
                        } label: {
                            Text("Cancel")
                                .font(Theme.roundedSecondary(size: 13, weight: .medium, relativeTo: .caption1))
                                .foregroundColor(Theme.bearRed)
                                .padding(.horizontal, Theme.Spacing.card)
                                .padding(.vertical, Theme.Spacing.small)
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                        .strokeBorder(Theme.bearRed.opacity(0.4), lineWidth: 1)
                                )
                        }
                        .buttonStyle(EKPressStyle())
                    }
                    .padding(.vertical, Theme.Spacing.xLarge)
                    .banknoteCard()
                    .padding(.horizontal, Theme.Spacing.screen)
                } else if vm.isLoading {
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

                            // 2x3 SCORECARD GRID
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                Text("RISK SCORES")
                                    .font(Theme.sectionCapsLabel())
                                    .foregroundColor(Theme.inkTertiary)
                                    .padding(.horizontal, Theme.Spacing.screen)

                                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.standard), count: 2), spacing: Theme.Spacing.standard) {
                                    ScoreTile(label: "Risk Score", value: result.scores.riskScore, color: Theme.bearRed)
                                    ScoreTile(label: "Stress Score", value: result.scores.stressScore, color: Theme.holdAmber)
                                    ScoreTile(label: "Macro Fragility", value: result.scores.macroFragility, color: Theme.securityGold)
                                    ScoreTile(label: "Liquidity", value: result.scores.liquidityScore, color: Theme.bullGreen)
                                    ScoreTile(label: "Concentration", value: result.scores.concentrationScore, color: Theme.inkSecondary)
                                    ScoreTile(label: "Tail Risk", value: result.scores.tailRiskScore, color: Theme.bearRed)
                                }
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
        .helpSheet(isPresented: $showHelp, title: FeatureHelp.stressTest.title, subtitle: FeatureHelp.stressTest.subtitle, sections: FeatureHelp.stressTest.sections)
    }
}

// MARK: - ScoreTile

struct ScoreTile: View {
    let label: String
    let value: Int
    let color: Color

    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("\(value)")
                .font(Theme.serialNumberFont(size: 24, relativeTo: .title2))
                .foregroundColor(color)
            Text(label)
                .font(Theme.microLabel())
                .foregroundColor(Theme.inkTertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Spacing.standard)
        .padding(.horizontal, Theme.Spacing.card)
        .background(Theme.canvasDeep)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                .strokeBorder(Theme.borderFine, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
    }
}
