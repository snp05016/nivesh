import SwiftUI
import Combine
// MARK: - SSE Agent Event
struct AgentEvent: Identifiable, Equatable {
    let id = UUID()
    let agentName: String
    let status: String       // "thinking", "complete", "error"
    let message: String
    let timestamp: Date

    static func == (lhs: AgentEvent, rhs: AgentEvent) -> Bool { lhs.id == rhs.id }
}

// MARK: - SSE Stream Client
@MainActor
final class AgentStreamClient: ObservableObject {
    @Published var events: [AgentEvent] = []
    @Published var isConnected = false
    @Published var connectionFailed = false
    private var task: Task<Void, Never>?

    func connect(userId: Int, ticker: String) {
        disconnect()
        isConnected = true
        connectionFailed = false
        task = Task {
            let urlString = "\(NetworkManager.shared.baseURL)/api/v1/dashboard/stream?user_id=\(userId)&ticker=\(ticker)"
            guard let url = URL(string: urlString) else {
                await MainActor.run { self.connectionFailed = true; self.isConnected = false }
                return
            }
            var request = URLRequest(url: url)
            request.timeoutInterval = 120
            if let token = NetworkManager.shared.authToken {
                request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            }
            do {
                let (bytes, _) = try await URLSession.shared.bytes(for: request)
                for try await line in bytes.lines {
                    guard !Task.isCancelled else { break }
                    guard line.hasPrefix("data: ") else { continue }
                    let jsonStr = String(line.dropFirst(6))
                    guard let data = jsonStr.data(using: .utf8),
                          let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
                    let agent = obj["agent"] as? String ?? "Unknown"
                    let status = obj["status"] as? String ?? "thinking"
                    let message = obj["message"] as? String ?? ""
                    let event = AgentEvent(agentName: agent, status: status, message: message, timestamp: Date())
                    await MainActor.run { self.events.append(event) }
                    if status == "complete" || status == "error" { break }
                }
                await MainActor.run {
                    if self.events.isEmpty { self.connectionFailed = true }
                    self.isConnected = false
                }
            } catch {
                if !Task.isCancelled {
                    await MainActor.run { self.connectionFailed = true; self.isConnected = false }
                }
            }
        }
    }

    func disconnect() {
        task?.cancel()
        task = nil
        events = []
        isConnected = false
        connectionFailed = false
    }
}

// MARK: - Dialectic Progress View
struct DialecticProgressView: View {
    @StateObject private var client = AgentStreamClient()
    @State private var showFallback = false
    @State private var fallbackStep = 0
    @State private var reconnectAttempts = 0
    @Environment(\.scenePhase) private var scenePhase
    let userId: Int?
    let ticker: String

    private static let fallbackStages: [(agent: String, message: String)] = [
        ("Market Analyst", "Fetching technical indicators and price data..."),
        ("News Analyst", "Scanning headlines and sentiment streams..."),
        ("Fundamentals Analyst", "Reviewing financial statements and ratios..."),
        ("Bull Researcher", "Building the bullish thesis with catalysts..."),
        ("Bear Researcher", "Challenging assumptions and finding risks..."),
        ("Risk Committee", "Finalizing risk clearance and confidence score..."),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // Header
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("\u{0935}\u{093F}\u{0936}\u{094D}\u{0932}\u{0947}\u{0937}\u{0923} \u{092A}\u{094D}\u{0930}\u{0917}\u{0924}\u{093F}")
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
                Text("AI ANALYSIS IN PROGRESS")
                    .font(.caption.weight(.semibold).monospaced())
                    .tracking(2.0)
                    .foregroundStyle(Theme.inkPrimary)
            }
            .padding(.bottom, Theme.Spacing.card)

            SectionDivider()
                .padding(.bottom, Theme.Spacing.card)

            if !showFallback && client.events.isEmpty && client.isConnected {
                // Initial connecting state
                HStack(spacing: Theme.Spacing.medium) {
                    ProgressView()
                        .tint(Theme.securityGold)
                    Text("Initializing agent graph...")
                        .font(.caption)
                        .foregroundStyle(Theme.inkSecondary)
                }
            } else if !showFallback && !client.events.isEmpty {
                // Live SSE events
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: Theme.Spacing.none) {
                            ForEach(client.events) { event in
                                AgentEventRow(event: event)
                                    .id(event.id)
                            }
                        }
                    }
                    .onChange(of: client.events.count) { _, _ in
                        if let last = client.events.last {
                            withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                        }
                    }
                }
                .frame(maxHeight: 320)
            } else {
                // Fallback: pre-defined stages with sequential reveal
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: Theme.Spacing.none) {
                            ForEach(0..<min(fallbackStep, Self.fallbackStages.count), id: \.self) { i in
                                let stage = Self.fallbackStages[i]
                                let status: String = i < fallbackStep - 1 ? "complete"
                                    : (i == fallbackStep - 1 && fallbackStep > Self.fallbackStages.count ? "complete" : "thinking")
                                AgentEventRow(event: AgentEvent(
                                    agentName: stage.agent,
                                    status: status,
                                    message: stage.message,
                                    timestamp: Date()
                                ))
                                .id(i)
                            }
                        }
                    }
                    .onChange(of: fallbackStep) { _, _ in
                        withAnimation { proxy.scrollTo(fallbackStep - 1, anchor: .bottom) }
                    }
                }
                .frame(maxHeight: 320)
            }
        }
        .padding(Theme.Spacing.card)
        .glassCard()
        .banknoteCard()
        .onAppear {
            if let uid = userId {
                client.connect(userId: uid, ticker: ticker)
            }
            // Fallback timer: if no events after 3 seconds, start sequential animation
            DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                if client.events.isEmpty {
                    showFallback = true
                    advanceFallback()
                }
            }
        }
        .onDisappear { client.disconnect() }
        // Fix 3.9: SSE lifecycle — disconnect on background, reconnect on foreground
        .onChange(of: scenePhase) { _, newPhase in
            switch newPhase {
            case .background:
                client.disconnect()
                reconnectAttempts = 0
            case .active:
                guard let uid = userId else { return }
                let delay = pow(2.0, Double(min(reconnectAttempts, 4)))
                Task {
                    try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                    client.connect(userId: uid, ticker: ticker)
                }
                reconnectAttempts += 1
            default: break
            }
        }
    }

    private func advanceFallback() {
        guard showFallback else { return }
        guard fallbackStep < Self.fallbackStages.count else { return }
        fallbackStep += 1
        let delay: TimeInterval = fallbackStep < Self.fallbackStages.count ? 1.8 : 0
        if fallbackStep < Self.fallbackStages.count {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                advanceFallback()
            }
        }
    }
}

// MARK: - Agent Event Row
struct AgentEventRow: View {
    let event: AgentEvent
    @State private var pulse = false

    private var statusColor: Color {
        switch event.status {
        case "thinking": return Theme.securityGold
        case "complete": return Theme.bullGreen
        case "error": return Theme.bearRed
        default: return Theme.inkSecondary
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.medium) {
            // Timeline dot + connector
            VStack(spacing: Theme.Spacing.none) {
                Circle()
                    .fill(statusColor)
                    .frame(width: 8, height: 8)
                    .shadow(color: statusColor.opacity(pulse ? 0.8 : 0.2), radius: pulse ? 8 : 4)
                Rectangle()
                    .fill(Theme.inkTertiary.opacity(0.15))
                    .frame(width: 1)
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(event.agentName)
                    .font(.caption.weight(.bold).monospaced())
                    .foregroundStyle(statusColor)
                Text(event.message)
                    .font(.caption2)
                    .foregroundStyle(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(event.timestamp, style: .time)
                    .font(.caption2.monospaced())
                    .foregroundStyle(Theme.inkTertiary)
            }
            .padding(.bottom, Theme.Spacing.standard)
        }
        .onAppear {
            if event.status == "thinking" {
                withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) {
                    pulse = true
                }
            }
        }
    }
}
