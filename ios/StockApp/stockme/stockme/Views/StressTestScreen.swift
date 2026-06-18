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
    let progressPct: Int?
    let stage: String?
    let checkpoint: String?
    let results: [StressTestResult]?

    enum CodingKeys: String, CodingKey {
        case status
        case progressPct = "progress_pct"
        case stage
        case checkpoint
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

// MARK: - Checkpoint Model

struct StressCheckpoint: Identifiable {
    let id: String
    let label: String
    let icon: String
}

// MARK: - Diagnostic Info

struct StressDiagnostic {
    let urlAttempted: String
    let httpStatus: Int?       // nil = never reached server
    let errorDomain: String?
    let errorCode: Int?
    let rawBody: String?       // first 400 chars of response body

    var summary: String {
        if let status = httpStatus {
            switch status {
            case 401: return "HTTP 401 — Token invalid or expired. Log out and back in."
            case 403: return "HTTP 403 — Access denied."
            case 404: return "HTTP 404 — Endpoint not found. Server may need restart."
            case 422: return "HTTP 422 — Request body rejected by server."
            case 500: return "HTTP 500 — Server crash. Check server logs."
            default:  return "HTTP \(status) — Unexpected response."
            }
        }
        if let code = errorCode {
            switch code {
            case NSURLErrorCannotConnectToHost:  return "Cannot connect to \(urlAttempted). Is the server running?"
            case NSURLErrorTimedOut:             return "Connection timed out after 30s."
            case NSURLErrorNetworkConnectionLost: return "Network connection lost mid-request."
            case NSURLErrorNotConnectedToInternet: return "No internet connection."
            default: return "Network error (code \(code))."
            }
        }
        return "Unknown failure."
    }
}

// MARK: - ViewModel

class StressTestViewModel: ObservableObject {
    @Published var selectedScenarios: Set<String> = []
    @Published var results: [StressTestResult] = []
    @Published var isLoading = false
    @Published var errorMessage: String? = nil
    @Published var diagnostic: StressDiagnostic? = nil

    @Published var progressPct: Int = 0
    @Published var progressStage: String = ""
    @Published var activeCheckpoint: String = "init"

    private var pollingTask: Task<Void, Never>? = nil

    let scenarios = [
        ("NIFTY_CRASH", "Nifty Crash", "chart.line.down.right"),
        ("OIL_SHOCK", "Oil Shock", "drop.fill"),
        ("RATE_HIKE", "Rate Hike", "arrow.up.right.circle"),
        ("FII_EXODUS", "FII Exodus", "airplane.departure"),
        ("GLOBAL_RECESSION", "Recession", "globe.americas"),
        ("POLICY_SHOCK", "Policy Shock", "building.columns"),
        ("CURRENCY_CRASH", "Currency Crash", "indianrupeesign.circle"),
    ]

    let checkpoints: [StressCheckpoint] = [
        StressCheckpoint(id: "init",      label: "Initializing",        icon: "cpu"),
        StressCheckpoint(id: "enrich",    label: "Loading Market Data", icon: "arrow.down.circle"),
        StressCheckpoint(id: "covariance", label: "Building Risk Model", icon: "point.3.connected.trianglepath.dotted"),
        StressCheckpoint(id: "scenarios", label: "Running Scenarios",   icon: "waveform.path.ecg"),
        StressCheckpoint(id: "scoring",   label: "Risk Scoring",        icon: "chart.bar.xaxis"),
        StressCheckpoint(id: "done",      label: "Complete",            icon: "checkmark.seal.fill"),
    ]

    func checkpointIndex(for key: String) -> Int {
        checkpoints.firstIndex(where: { $0.id == key }) ?? 0
    }

    var activeIndex: Int { checkpointIndex(for: activeCheckpoint) }

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
        diagnostic = nil
        results = []
        progressPct = 0
        progressStage = ""
        activeCheckpoint = "init"

        pollingTask?.cancel()

        // Capture baseURL on main actor before entering the Task
        let serverURL = NetworkManager.shared.baseURL
        let endpoint = "\(serverURL)/api/v1/portfolio/stress-test"

        Task { [weak self] in
            guard let self = self else { return }
            do {
                let body: [String: Any] = [
                    "portfolio_id": "holdings",
                    "scenarios": Array(self.selectedScenarios)
                ]

                var request = URLRequest(url: URL(string: endpoint)!)
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                request.timeoutInterval = 30
                request.httpBody = try JSONSerialization.data(withJSONObject: body)

                let (data, postResponse) = try await URLSession.shared.data(for: request)

                guard let httpResponse = postResponse as? HTTPURLResponse else {
                    let diag = StressDiagnostic(urlAttempted: endpoint, httpStatus: nil,
                                               errorDomain: nil, errorCode: nil, rawBody: nil)
                    await MainActor.run {
                        self.diagnostic = diag
                        self.errorMessage = "Invalid response from server."
                        self.isLoading = false
                        HapticManager.error()
                    }
                    return
                }

                let bodyPreview = String(data: data, encoding: .utf8).map { String($0.prefix(400)) }

                guard httpResponse.statusCode == 200 || httpResponse.statusCode == 202 else {
                    // Extract FastAPI detail field if present
                    var detail = bodyPreview ?? "No body"
                    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let d = json["detail"] as? String {
                        detail = d
                    }
                    let diag = StressDiagnostic(urlAttempted: endpoint,
                                               httpStatus: httpResponse.statusCode,
                                               errorDomain: nil, errorCode: nil, rawBody: detail)
                    await MainActor.run {
                        self.diagnostic = diag
                        self.errorMessage = diag.summary
                        self.isLoading = false
                        HapticManager.error()
                    }
                    return
                }

                let job = try JSONDecoder().decode(StressTestJob.self, from: data)

                if job.status == "completed" {
                    let jobFull = try JSONDecoder().decode(StressTestJobResponse.self, from: data)
                    await MainActor.run {
                        self.results = jobFull.results ?? []
                        self.progressPct = 100
                        self.activeCheckpoint = "done"
                        self.isLoading = false
                        HapticManager.success()
                    }
                    return
                }

                await self.startPolling(jobId: job.jobId, token: token, serverURL: serverURL)
            } catch {
                let nsErr = error as NSError
                let diag = StressDiagnostic(urlAttempted: endpoint, httpStatus: nil,
                                           errorDomain: nsErr.domain, errorCode: nsErr.code,
                                           rawBody: nsErr.localizedDescription)
                await MainActor.run {
                    self.diagnostic = diag
                    self.errorMessage = diag.summary
                    self.isLoading = false
                    HapticManager.error()
                }
            }
        }
    }

    private func startPolling(jobId: String, token: String, serverURL: String) {
        pollingTask = Task { [weak self] in
            guard let self = self else { return }
            let maxRetries = 300
            var attempts = 0
            let pollEndpoint = "\(serverURL)/api/v1/portfolio/stress-test/\(jobId)"

            while attempts < maxRetries && !Task.isCancelled {
                do {
                    var request = URLRequest(url: URL(string: pollEndpoint)!)
                    request.httpMethod = "GET"
                    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

                    let (data, response) = try await URLSession.shared.data(for: request)

                    guard let httpResponse = response as? HTTPURLResponse else { continue }

                    if httpResponse.statusCode >= 400 {
                        var detail = String(data: data, encoding: .utf8).map { String($0.prefix(400)) }
                        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                           let d = json["detail"] as? String { detail = d }
                        let diag = StressDiagnostic(urlAttempted: pollEndpoint,
                                                   httpStatus: httpResponse.statusCode,
                                                   errorDomain: nil, errorCode: nil, rawBody: detail)
                        await MainActor.run {
                            self.diagnostic = diag
                            self.errorMessage = diag.summary
                            self.isLoading = false
                            HapticManager.error()
                        }
                        return
                    }

                    let jobResponse = try JSONDecoder().decode(StressTestJobResponse.self, from: data)

                    await MainActor.run {
                        self.progressPct = jobResponse.progressPct ?? 0
                        self.progressStage = jobResponse.stage ?? ""
                        if let cp = jobResponse.checkpoint {
                            self.activeCheckpoint = cp
                        }
                    }

                    if jobResponse.status == "completed" {
                        await MainActor.run {
                            self.results = jobResponse.results ?? []
                            self.isLoading = false
                            self.progressPct = 100
                            self.activeCheckpoint = "done"
                            HapticManager.success()
                        }
                        return
                    }

                    if jobResponse.status == "failed" {
                        await MainActor.run {
                            self.errorMessage = "Simulation failed. Please try again."
                            self.isLoading = false
                            HapticManager.error()
                        }
                        return
                    }
                } catch {
                    let nsErr = error as NSError
                    if nsErr.code == NSURLErrorTimedOut || nsErr.code == NSURLErrorCannotConnectToHost {
                        let diag = StressDiagnostic(urlAttempted: pollEndpoint, httpStatus: nil,
                                                   errorDomain: nsErr.domain, errorCode: nsErr.code,
                                                   rawBody: nsErr.localizedDescription)
                        await MainActor.run { self.diagnostic = diag }
                        attempts += 5
                    }
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
        activeCheckpoint = "init"
        diagnostic = nil
    }
}

// MARK: - Diagnostic Card

struct StressDiagnosticCard: View {
    let message: String?
    let diagnostic: StressDiagnostic?
    let serverURL: String
    @State private var expanded = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Summary row
            HStack(spacing: Theme.Spacing.standard) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(Theme.bearRed)
                Text(message ?? "Unknown error")
                    .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .body))
                    .foregroundColor(Theme.bearRed)
                    .multilineTextAlignment(.leading)
                Spacer()
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) { expanded.toggle() }
                } label: {
                    Image(systemName: expanded ? "chevron.up" : "chevron.down")
                        .font(Theme.engravedSerif(size: 12, weight: .medium))
                        .foregroundColor(Theme.inkTertiary)
                }
                .buttonStyle(EKPressStyle())
            }

            // Debug rows (collapsed by default)
            if expanded {
                GuillocheDivider()

                VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                    DiagRow(label: "Server", value: serverURL)
                    if let d = diagnostic {
                        if let url = Optional(d.urlAttempted), url != serverURL {
                            DiagRow(label: "Endpoint", value: url)
                        }
                        if let status = d.httpStatus {
                            DiagRow(label: "HTTP Status", value: "\(status)")
                        }
                        if let domain = d.errorDomain, let code = d.errorCode {
                            DiagRow(label: "Error", value: "\(domain) \(code)")
                        }
                        if let body = d.rawBody {
                            DiagRow(label: "Body", value: body)
                        }
                    }
                }

                Text("Change server URL in Settings → Server URL")
                    .font(Theme.microLabel())
                    .foregroundColor(Theme.inkTertiary)
            }
        }
        .padding(Theme.Spacing.card)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.bearRedLight)
        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium))
        .overlay(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
            .strokeBorder(Theme.bearRed.opacity(0.4), lineWidth: 1))
        .padding(.horizontal, Theme.screenPadding)
    }
}

private struct DiagRow: View {
    let label: String
    let value: String
    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return HStack(alignment: .top, spacing: Theme.Spacing.small) {
            Text(label)
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .tracking(0.8)
                .foregroundColor(Theme.inkTertiary)
                .frame(width: colW * 0.20, alignment: .leading)
            Text(value)
                .font(Theme.serialNumberFont(size: 11, relativeTo: .caption))
                .foregroundColor(Theme.inkSecondary)
                .multilineTextAlignment(.leading)
        }
    }
}

// MARK: - Checkpoint Tracker

struct StressCheckpointTracker: View {
    let checkpoints: [StressCheckpoint]
    let activeIndex: Int
    let progressPct: Int
    let stage: String

    var body: some View {
        let colW = UIScreen.main.bounds.width - 2 * Theme.screenPadding
        return VStack(spacing: Theme.Spacing.medium) {
            // Step indicators
            HStack(spacing: 0) {
                ForEach(checkpoints.indices, id: \.self) { idx in
                    let cp = checkpoints[idx]
                    let isDone    = idx < activeIndex
                    let isActive  = idx == activeIndex
                    let isPending = idx > activeIndex

                    VStack(spacing: Theme.Spacing.small) {
                        ZStack {
                            Circle()
                                .fill(isDone ? Theme.bullGreen : isActive ? Theme.securityGold : Theme.canvasDeep)
                                .frame(width: 32, height: 32)
                                .overlay(
                                    Circle()
                                        .strokeBorder(
                                            isDone ? Theme.bullGreen : isActive ? Theme.securityGold : Theme.borderFine,
                                            lineWidth: 1.5
                                        )
                                )

                            if isDone {
                                Image(systemName: "checkmark")
                                    .font(Theme.engravedSerif(size: 13, weight: .bold))
                                    .foregroundColor(.white)
                            } else if isActive {
                                Image(systemName: cp.icon)
                                    .font(Theme.engravedSerif(size: 13, weight: .medium))
                                    .foregroundColor(Theme.securityGold)
                            } else {
                                Image(systemName: cp.icon)
                                    .font(Theme.engravedSerif(size: 13))
                                    .foregroundColor(Theme.inkTertiary)
                            }
                        }
                        .animation(.easeInOut(duration: 0.3), value: activeIndex)

                        Text(cp.label)
                            .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                            .tracking(0.5)
                            .foregroundColor(
                                isDone ? Theme.bullGreen :
                                isActive ? Theme.securityGold :
                                Theme.inkTertiary
                            )
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .frame(width: colW * 0.17)
                    }

                    if idx < checkpoints.count - 1 {
                        Rectangle()
                            .fill(idx < activeIndex ? Theme.bullGreen : Theme.borderFine)
                            .frame(height: 1.5)
                            .frame(maxWidth: .infinity)
                            .padding(.bottom, Theme.Spacing.sectionGap)
                            .animation(.easeInOut(duration: 0.4), value: activeIndex)
                    }
                }
            }
            .padding(.horizontal, Theme.screenPadding)

            // Active stage label + progress bar
            VStack(spacing: Theme.Spacing.small) {
                if !stage.isEmpty {
                    Text(stage)
                        .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .caption))
                        .foregroundColor(Theme.inkSecondary)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .animation(.none, value: stage)
                }

                ProgressView(
                    value: Double(min(max(progressPct, 0), 100)),
                    total: 100
                )
                .progressViewStyle(.linear)
                .tint(Theme.securityGold)
                .animation(.easeInOut(duration: 0.5), value: progressPct)

                HStack {
                    Text("\(progressPct)% complete")
                        .font(Theme.serialNumberFont(size: 11, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                    Spacer()
                }
            }
            .padding(.horizontal, Theme.screenPadding)
        }
        .padding(.vertical, Theme.Spacing.card)
        .banknoteCard()
        .padding(.horizontal, Theme.screenPadding)
    }
}

// MARK: - Screen

struct StressTestScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var vm = StressTestViewModel()
    @State private var showHelp = false

    var body: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Spacing.xLarge) {
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
                        .padding(.horizontal, Theme.screenPadding)

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: Theme.Spacing.standard) {
                            ForEach(vm.scenarios, id: \.0) { id, name, icon in
                                let isSelected = vm.selectedScenarios.contains(id)
                                Button {
                                    vm.toggleScenario(id)
                                } label: {
                                    HStack(spacing: Theme.Spacing.small) {
                                        Image(systemName: icon)
                                            .font(Theme.engravedSerif(size: 14))
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
                        .padding(.horizontal, Theme.screenPadding)
                    }
                }

                // RUN / CANCEL BUTTON
                if vm.isLoading {
                    Button {
                        vm.cancel()
                        HapticManager.selection()
                    } label: {
                        HStack(spacing: Theme.Spacing.standard) {
                            Image(systemName: "xmark.circle")
                                .font(Theme.engravedSerif(size: 16))
                            Text("Cancel Simulation")
                                .font(Theme.roundedSecondary(size: 16, weight: .semibold, relativeTo: .headline))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Spacing.card)
                        .background(Theme.bearRedLight)
                        .foregroundColor(Theme.bearRed)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                .strokeBorder(Theme.bearRed.opacity(0.4), lineWidth: 1)
                        )
                        .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.large))
                    }
                    .buttonStyle(EKPressStyle())
                    .padding(.horizontal, Theme.screenPadding)
                } else {
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
                    .disabled(vm.selectedScenarios.isEmpty)
                    .buttonStyle(EKPressStyle())
                    .padding(.horizontal, Theme.screenPadding)
                }

                GuillocheDivider().padding(.horizontal, Theme.screenPadding)

                // CHECKPOINT TRACKER (shown while loading)
                if vm.isLoading {
                    StressCheckpointTracker(
                        checkpoints: vm.checkpoints,
                        activeIndex: vm.activeIndex,
                        progressPct: vm.progressPct,
                        stage: vm.progressStage
                    )
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }

                // ERROR + DIAGNOSTIC CARD
                if vm.errorMessage != nil || vm.diagnostic != nil {
                    StressDiagnosticCard(message: vm.errorMessage, diagnostic: vm.diagnostic,
                                        serverURL: NetworkManager.shared.baseURL)
                }

                // RESULTS
                if !vm.results.isEmpty {
                    ForEach(vm.results) { result in
                        StressScenarioSection(result: result)

                        if result.id != vm.results.last?.id {
                            GuillocheDivider().padding(.horizontal, Theme.screenPadding)
                        }
                    }
                }

                Spacer(minLength: 40)
            }
        }
        .background(Theme.canvas.edgesIgnoringSafeArea(.all))
        .navigationTitle("Stress Test")
        .navigationBarTitleDisplayMode(.inline)
        .animation(.easeInOut(duration: 0.4), value: vm.isLoading)
        .helpSheet(isPresented: $showHelp, title: FeatureHelp.stressTest.title, subtitle: FeatureHelp.stressTest.subtitle, sections: FeatureHelp.stressTest.sections)
    }
}

// MARK: - Scenario Result Section

struct StressScenarioSection: View {
    let result: StressTestResult

    var body: some View {
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
            .padding(.horizontal, Theme.screenPadding)

            // TORNADO CHART
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                Text("HOLDING IMPACT")
                    .font(Theme.sectionCapsLabel())
                    .foregroundColor(Theme.inkTertiary)
                    .padding(.horizontal, Theme.screenPadding)

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
                .frame(height: UIScreen.main.bounds.height * 0.30)
                .padding(.horizontal, Theme.screenPadding)
            }

            // 2×3 SCORECARD GRID
            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                Text("RISK SCORES")
                    .font(Theme.sectionCapsLabel())
                    .foregroundColor(Theme.inkTertiary)
                    .padding(.horizontal, Theme.screenPadding)

                LazyVGrid(
                    columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.standard), count: 2),
                    spacing: Theme.Spacing.standard
                ) {
                    ScoreTile(label: "Risk Score",     value: result.scores.riskScore,          color: Theme.bearRed)
                    ScoreTile(label: "Stress Score",   value: result.scores.stressScore,        color: Theme.holdAmber)
                    ScoreTile(label: "Macro Fragility",value: result.scores.macroFragility,     color: Theme.securityGold)
                    ScoreTile(label: "Liquidity",      value: result.scores.liquidityScore,     color: Theme.bullGreen)
                    ScoreTile(label: "Concentration",  value: result.scores.concentrationScore, color: Theme.inkSecondary)
                    ScoreTile(label: "Tail Risk",      value: result.scores.tailRiskScore,      color: Theme.bearRed)
                }
                .padding(.horizontal, Theme.screenPadding)
            }

            // HOLDING ROWS
            VStack(spacing: Theme.Spacing.standard) {
                ForEach(result.holdings) { h in
                    HStack {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(h.ticker)
                                .font(Theme.roundedSecondary(size: 14, weight: .semibold, relativeTo: .subheadline))
                                .foregroundColor(Theme.inkPrimary)
                            Text(h.sector)
                                .font(Theme.microLabel())
                                .foregroundColor(Theme.inkTertiary)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                            Text("\(h.impactInr >= 0 ? "+" : "-")\(IndianFormatter.price(abs(h.impactInr)))")
                                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                .foregroundColor(h.impactInr >= 0 ? Theme.bullGreen : Theme.bearRed)
                            Text(IndianFormatter.percent(h.impactPct))
                                .font(Theme.serialNumberFont(size: 12, relativeTo: .caption))
                                .foregroundColor(h.impactInr >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                    }
                    .padding(Theme.Spacing.standard)
                    .banknoteCard()
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
        }
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
                .multilineTextAlignment(.center)
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
