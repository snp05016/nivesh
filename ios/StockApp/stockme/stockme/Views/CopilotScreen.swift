import SwiftUI
import Combine

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let content: String
    let contextCards: [[String: Any]]?
    let isWelcome: Bool
    init(role: String, content: String, contextCards: [[String: Any]]? = nil, isWelcome: Bool = false) {
        self.role = role
        self.content = content
        self.contextCards = contextCards
        self.isWelcome = isWelcome
    }
}

fileprivate struct CapabilityRow: Identifiable {
    let id = UUID()
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String
}

fileprivate let welcomeCapabilities: [CapabilityRow] = [
    CapabilityRow(icon: "briefcase.fill",   iconColor: Theme.securityGold,       title: "Portfolio Insights",     subtitle: "Ask about your holdings, P&L, or risk exposure"),
    CapabilityRow(icon: "chart.line.uptrend.xyaxis", iconColor: Theme.bullGreen, title: "Stock Analysis", subtitle: "Deep research on any NSE stock (e.g. \"Analyze RELIANCE\")"),
    CapabilityRow(icon: "map.fill",          iconColor: Theme.avatarBlue,        title: "App Navigation",         subtitle: "Ask where any feature lives in the app"),
    CapabilityRow(icon: "book.pages.fill",   iconColor: Theme.holdAmber,         title: "Market Terms",           subtitle: "Tap underlined terms or ask me to explain concepts"),
    CapabilityRow(icon: "globe.asia.australia.fill", iconColor: Theme.signalEmerald, title: "Market Intel",    subtitle: "Sector trends, indices, upcoming earnings")
]

struct CopilotScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @Environment(\.dismiss) var dismiss
    @State private var messageText: String = ""
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: "assistant", content: "", isWelcome: true)
    ]
    @State private var isTyping: Bool = false
    @State private var dotOffset: CGFloat = 0

    let currentContext: [String: Any]?

    /// Hardcoded app navigation map so the copilot can guide users to any feature.
    private static let appNavigationContext: [String: Any] = [
        "app_navigation": """
        TAB BAR (5 tabs at bottom):
        Tab 1 - Home: Main dashboard, market indices, morning brief, quick analysis access.
        Tab 2 - Markets: Hub for all analytical tools. Contains sub-sections:
          - Overview: Cards showing all market tools
          - Earnings Dashboard: YoY growth, earnings calendar, beat/miss, post-result movers
          - Technical Momentum Scanner: OI trends, golden/death cross, sector rotation signals
          - Pre-IPO Marketplace: OTC price discovery, SME board, unlisted shares
          - Screener: Standard stock discovery, search by name/ticker, preset screens
          - Alerts: Price watch, target triggers, surveillance flags
          - Strategy Lab: Backtest trading strategies against historical data
          - NL Screener: Natural language stock search (e.g. "profitable midcaps with zero debt")
          - Correlation Matrix: Cross-asset correlation heat-map for portfolio diversification
          - Market Anomalies: Unusual volume spikes, price breakouts, order book surveillance
          - Sector Rotation: Capital flow heat-map across NSE sectors
          - Stress Test: Portfolio shock simulation under macroeconomic scenarios
          - Earnings Surprise: Historical beats/misses + current quarter estimates
        Tab 3 - Ideas: Expert stock ideas, curated research, thematic baskets from SEBI-registered advisors.
        Tab 4 - News: Multimedia news feed, articles, real-time financial newswire.
        Tab 5 - Portfolio: Holdings, net worth, daily P&L, transaction history, allocation breakdown, risk analysis, red flags, trade journal, exports (Excel/PDF).
        
        ADDITIONAL FEATURES:
        - AI Copilot (floating sparkles button): Available everywhere via the gold sparkles icon in bottom-right corner.
        - Stock Analysis: Tap any stock to open StockActionHubView with 5 analysis types (Quick Scan, Standard, Deep Dive, Technical Only, Fundamental Only).
        - Settings (gear icon on Home screen): Server URL, theme (dark/light), biometric lock, dev tools (triple-tap profile card).
        - Glossary: Tap underlined terms anywhere to see definitions. Full glossary in Settings > Learn Financial Terms.
        - AI How It Works: Pipeline explainer accessible from StockActionHubView info button.
        - Morning Brief: Daily AI-generated portfolio summary card on Home screen.
        """
    ]

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                VStack(spacing: Theme.Spacing.none) {
                    ScrollViewReader { proxy in
                        ScrollView {
                            VStack(spacing: Theme.Spacing.card) {
                                ForEach(messages) { msg in
                                    if msg.isWelcome {
                                        welcomeCard
                                    } else if msg.role == "user" {
                                        userBubble(msg.content)
                                    } else {
                                        assistantBubble(msg)
                                    }
                                }
                                if isTyping {
                                    typingIndicator()
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.vertical, Theme.Spacing.standard)
                        }
                        .onChange(of: messages.count) { _ in
                            if let last = messages.last {
                                withAnimation { proxy.scrollTo(last.id, anchor: .bottom) }
                            }
                        }
                    }

                    VStack(spacing: Theme.Spacing.none) {
                        GuillocheDivider()

                        // Context chip
                        if let context = currentContext, let ticker = context["ticker"] as? String {
                            HStack {
                                HStack(spacing: Theme.Spacing.small) {
                                    Image(systemName: "target")
                                        .font(Theme.serialNumberFont(size: 9, relativeTo: .caption2))
                                    Text(ticker)
                                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                }
                                .foregroundColor(Theme.securityGold)
                                .padding(.horizontal, Theme.Spacing.medium)
                                .padding(.vertical, Theme.Spacing.xSmall)
                                .background(Theme.securityGold.opacity(0.08))
                                .clipShape(Capsule())
                                .overlay(Capsule().stroke(Theme.securityGold.opacity(0.3), lineWidth: 0.5))
                                Spacer()
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, Theme.Spacing.small)
                        }

                        HStack(spacing: Theme.Spacing.standard) {
                            TextField("Ask Copilot...", text: $messageText)
                                .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                                .foregroundColor(Theme.inkPrimary)
                                .padding(.horizontal, Theme.Spacing.card)
                                .padding(.vertical, Theme.Spacing.standard)
                                .background(Theme.canvasDeep)
                                .cornerRadius(Theme.CornerRadius.large)
                                .overlay(
                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                        .stroke(Theme.borderFine, lineWidth: 0.5)
                                )

                            Button(action: sendMessage) {
                                ZStack {
                                    Circle()
                                        .fill(messageText.isEmpty ? Theme.inkTertiary.opacity(0.2) : Theme.securityGold)
                                        .frame(width: 44, height: 44)
                                    Image(systemName: "arrow.up")
                                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                                        .foregroundColor(messageText.isEmpty ? Theme.inkTertiary : Theme.canvas)
                                }
                            }
                            .disabled(messageText.isEmpty || isTyping)
                            .buttonStyle(EKPressStyle())
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.vertical, Theme.Spacing.standard)
                    }
                    .background(Theme.canvas)
                }
            }
            .navigationTitle("Copilot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    HStack(spacing: Theme.Spacing.tight) {
                        Image(systemName: "sparkles")
                            .font(Theme.engravedSerif(size: 14, weight: .semibold))
                            .foregroundColor(Theme.securityGold)
                        Text("AI COPILOT")
                            .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                            .tracking(1.5)
                            .foregroundColor(Theme.inkPrimary)
                    }
                }
                ToolbarItem(placement: .navigationBarLeading) {
                    Button(action: {
                        HapticManager.selection()
                        dismiss()
                    }) {
                        Image(systemName: "xmark")
                            .font(Theme.engravedSerif(size: 14, weight: .semibold))
                            .foregroundColor(Theme.inkTertiary)
                    }
                    .buttonStyle(EKPressStyle())
                }
            }
            .toolbarBackground(Theme.canvas, for: .navigationBar)
        }
    }

    // MARK: - Welcome Card

    private var welcomeCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.none) {
            // Hero section
            VStack(spacing: Theme.Spacing.small) {
                ZStack {
                    Circle()
                        .fill(Theme.securityGold.opacity(0.12))
                        .frame(width: 52, height: 52)
                    Image(systemName: "sparkles")
                        .font(Theme.engravedSerif(size: 24, weight: .bold))
                        .foregroundColor(Theme.securityGold)
                }

                Text("Your AI Copilot")
                    .font(Theme.engravedSerif(size: 20, weight: .bold, relativeTo: .title3))
                    .foregroundColor(Theme.inkPrimary)

                Text("I can help with your finances, portfolio, and navigating the app")
                    .font(Theme.engravedSerif(size: 13, weight: .regular, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Theme.Spacing.standard)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, Theme.Spacing.large)

            GuillocheDivider()
                .padding(.horizontal, Theme.Spacing.card)

            // Capability rows
            VStack(spacing: Theme.Spacing.none) {
                ForEach(Array(welcomeCapabilities.enumerated()), id: \.offset) { idx, cap in
                    capabilityRowView(cap)
                    if idx < welcomeCapabilities.count - 1 {
                        Rectangle()
                            .fill(Theme.borderFine)
                            .frame(height: 0.5)
                            .padding(.leading, Theme.Spacing.xLarge + Theme.Spacing.card)
                    }
                }
            }
            .padding(.vertical, Theme.Spacing.small)
        }
        .background(Theme.canvasDeep)
        .cornerRadius(Theme.CornerRadius.card)
        .overlay(
            RoundedRectangle(cornerRadius: Theme.CornerRadius.card)
                .stroke(Theme.borderSage, lineWidth: 0.5)
        )
        .overlay(alignment: .top) {
            Rectangle()
                .fill(
                    LinearGradient(colors: [Theme.securityGold.opacity(0.6), Theme.securityGold.opacity(0.1)],
                                   startPoint: .leading, endPoint: .trailing)
                )
                .frame(height: 2.5)
                .clipShape(RoundedRectangle(cornerRadius: Theme.CornerRadius.small))
        }
        .id("welcome-card")
    }

    private func capabilityRowView(_ cap: CapabilityRow) -> some View {
        HStack(spacing: Theme.Spacing.card) {
            ZStack {
                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                    .fill(cap.iconColor.opacity(0.12))
                    .frame(width: 36, height: 36)
                Image(systemName: cap.icon)
                    .font(Theme.engravedSerif(size: 15, weight: .semibold))
                    .foregroundColor(cap.iconColor)
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text(cap.title)
                    .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .callout))
                    .foregroundColor(Theme.inkPrimary)
                Text(cap.subtitle)
                    .font(Theme.engravedSerif(size: 11, weight: .regular, relativeTo: .caption))
                    .foregroundColor(Theme.inkSecondary)
                    .lineLimit(2)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(Theme.sectionCapsLabel(size: 10))
                .foregroundColor(Theme.inkTertiary)
        }
        .padding(.horizontal, Theme.Spacing.card)
        .padding(.vertical, Theme.Spacing.standard)
        .contentShape(Rectangle())
    }

    // MARK: - User Bubble

    private func userBubble(_ text: String) -> some View {
        HStack {
            Spacer()
            Text(stripEmoji(text))
                .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
                .padding(.horizontal, Theme.Spacing.card)
                .padding(.vertical, Theme.Spacing.standard)
                .background(Theme.canvasDeep)
                .cornerRadius(Theme.CornerRadius.large)
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                        .stroke(Theme.borderFine, lineWidth: 0.5)
                )
                .padding(.leading, Theme.Spacing.xLarge)
        }
    }

    // MARK: - Assistant Bubble

    private func assistantBubble(_ msg: ChatMessage) -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            // Avatar
            ZStack {
                Circle()
                    .fill(Theme.securityGold.opacity(0.12))
                    .frame(width: 32, height: 32)
                Image(systemName: "sparkles")
                    .font(Theme.engravedSerif(size: 14, weight: .bold))
                    .foregroundColor(Theme.securityGold)
            }

            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("COPILOT")
                    .font(Theme.officialStampFont(size: 9, relativeTo: .caption2))
                    .tracking(1.5)
                    .foregroundColor(Theme.securityGold)
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, 2)
                    .background(Theme.securityGold.opacity(0.1))
                    .clipShape(Capsule())

                Text(stripEmoji(msg.content))
                    .font(Theme.engravedSerif(size: 15, weight: .regular, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                    .lineSpacing(4)

                if let cards = msg.contextCards {
                    ForEach(0..<cards.count, id: \.self) { idx in
                        if let signal = cards[idx]["signal"] as? String {
                            HStack(spacing: Theme.Spacing.tight) {
                                Circle()
                                    .fill(signal.contains("BULL") ? Theme.bullGreen : Theme.bearRed)
                                    .frame(width: 6, height: 6)
                                Text("Signal:")
                                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                    .foregroundColor(Theme.inkSecondary)
                                Text(signal)
                                    .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                                    .foregroundColor(signal.contains("BULL") ? Theme.bullGreen : Theme.bearRed)
                            }
                            .padding(.horizontal, Theme.Spacing.medium)
                            .padding(.vertical, Theme.Spacing.tight)
                            .background(Theme.canvasDeep)
                            .cornerRadius(Theme.CornerRadius.small)
                            .padding(.top, Theme.Spacing.xSmall)
                        }
                    }
                }
            }
            .padding(Theme.Spacing.card)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()

            Spacer()
        }
    }

    // MARK: - Typing Indicator

    private func typingIndicator() -> some View {
        HStack(alignment: .top, spacing: Theme.Spacing.standard) {
            ZStack {
                Circle()
                    .fill(Theme.securityGold.opacity(0.12))
                    .frame(width: 32, height: 32)
                Image(systemName: "sparkles")
                    .font(Theme.engravedSerif(size: 14, weight: .bold))
                    .foregroundColor(Theme.securityGold)
            }

            HStack(spacing: Theme.Spacing.xSmall) {
                Circle().fill(Theme.securityGold.opacity(0.6)).frame(width: 5, height: 5).offset(y: dotOffset)
                Circle().fill(Theme.securityGold.opacity(0.8)).frame(width: 5, height: 5).offset(y: -dotOffset)
                Circle().fill(Theme.securityGold).frame(width: 5, height: 5).offset(y: dotOffset)
            }
            .padding(.horizontal, Theme.Spacing.card)
            .padding(.vertical, Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.large)
            .onAppear {
                withAnimation(Animation.easeInOut(duration: 0.6).repeatForever()) {
                    dotOffset = 3
                }
            }

            Spacer()
        }
    }

    // MARK: - Actions

    private func sendMessage() {
        guard !messageText.isEmpty else { return }
        HapticManager.heavy()
        let userMsg = ChatMessage(role: "user", content: messageText)
        messages.append(userMsg)

        let msgToSend = messageText
        messageText = ""
        isTyping = true

        Task {
            do {
                let response = try await fetchCopilotResponse(userMessage: msgToSend)
                await MainActor.run {
                    HapticManager.success()
                    messages.append(ChatMessage(
                        role: "assistant",
                        content: response.reply,
                        contextCards: response.context_cards
                    ))
                    isTyping = false
                }
            } catch {
                await MainActor.run {
                    HapticManager.error()
                    messages.append(ChatMessage(
                        role: "assistant",
                        content: "Sorry, I encountered an error: \(error.localizedDescription)"
                    ))
                    isTyping = false
                }
            }
        }
    }

    private func fetchCopilotResponse(userMessage: String) async throws -> CopilotResponse {
        let history = messages.map { ["role": $0.role, "content": $0.content] }

        let requestBody: [String: Any] = [
            "user_message": userMessage,
            "conversation_history": history,
            "current_context": (currentContext ?? [:]).merging(Self.appNavigationContext) { _, new in new }
        ]

        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/copilot/chat") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authManager.currentUser?.token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody, options: [])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode(CopilotResponse.self, from: data)
    }
}

struct CopilotResponse: Codable {
    let reply: String
    let context_cards: [[String: AnyCodable]]?

    enum CodingKeys: String, CodingKey {
        case reply
        case context_cards
    }
}

// AnyCodable helper for parsing varied JSON
struct AnyCodable: Codable {
    let value: Any

    init(value: Any) { self.value = value }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let intVal = try? container.decode(Int.self) { value = intVal }
        else if let doubleVal = try? container.decode(Double.self) { value = doubleVal }
        else if let boolVal = try? container.decode(Bool.self) { value = boolVal }
        else if let stringVal = try? container.decode(String.self) { value = stringVal }
        else if let arrayVal = try? container.decode([AnyCodable].self) { value = arrayVal.map { $0.value } }
        else if let dictVal = try? container.decode([String: AnyCodable].self) { value = dictVal.mapValues { $0.value } }
        else { throw DecodingError.dataCorruptedError(in: container, debugDescription: "AnyCodable value cannot be decoded") }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let intVal = value as? Int { try container.encode(intVal) }
        else if let doubleVal = value as? Double { try container.encode(doubleVal) }
        else if let boolVal = value as? Bool { try container.encode(boolVal) }
        else if let stringVal = value as? String { try container.encode(stringVal) }
        else if let arrayVal = value as? [Any] {
            let encodableArray = arrayVal.map { AnyCodable(value: $0) }
            try container.encode(encodableArray)
        } else if let dictVal = value as? [String: Any] {
            let encodableDict = dictVal.mapValues { AnyCodable(value: $0) }
            try container.encode(encodableDict)
        } else {
            try container.encodeNil()
        }
    }
}

// MARK: - Floating Copilot Button Modifier
struct CopilotFloatingButtonModifier: ViewModifier {
    @State private var isShowingCopilot = false
    let currentContext: [String: Any]?

    func body(content: Content) -> some View {
        ZStack {
            content

            VStack {
                Spacer()
                HStack {
                    Spacer()
                    Button(action: {
                        HapticManager.selection()
                        isShowingCopilot = true
                    }) {
                        Image(systemName: "sparkles")
                            .font(Theme.engravedSerif(size: 20, weight: .bold))
                            .foregroundColor(Theme.canvas)
                            .padding(Theme.Spacing.card)
                            .background(Theme.securityGold)
                            .clipShape(Circle())
                            .shadow(color: Theme.securityGold.opacity(0.4), radius: 8, x: 0, y: 4)
                    }
                    .buttonStyle(EKPressStyle())
                    .padding(.trailing, Theme.screenPadding + Theme.Spacing.standard)
                    // This FAB is anchored to the full screen, so it floats over
                    // the tab bar. Add the tab-bar height so it sits on the same
                    // vertical plane as per-screen FABs (e.g. the Portfolio "+"),
                    // whose content stops at the top of the tab bar.
                    .padding(.bottom, Theme.Spacing.xLarge + Theme.Spacing.large + Theme.tabBarHeight)
                }
            }
        }
        .sheet(isPresented: $isShowingCopilot) {
            CopilotScreen(currentContext: currentContext)
        }
    }
}

extension View {
    func withCopilot(context: [String: Any]? = nil) -> some View {
        self.modifier(CopilotFloatingButtonModifier(currentContext: context))
    }
}
