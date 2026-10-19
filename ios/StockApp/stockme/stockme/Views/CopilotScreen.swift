import SwiftUI
import Combine

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let content: String
    let contextCards: [[String: Any]]?
    let isWelcome: Bool
    /// Client-side failure bubble: shown with Retry, never sent back to the model.
    let isError: Bool
    init(role: String, content: String, contextCards: [[String: Any]]? = nil, isWelcome: Bool = false, isError: Bool = false) {
        self.role = role
        self.content = content
        self.contextCards = contextCards
        self.isWelcome = isWelcome
        self.isError = isError
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
    @State private var sendTask: Task<Void, Never>?

    let currentContext: [String: Any]?

    /// App navigation map so the copilot can guide users to any feature.
    /// The Markets list is generated from MarketSection so it never goes stale.
    static let appNavigationContext: [String: Any] = [
        "app_navigation": """
        TAB BAR (5 tabs at bottom):
        Tab 1 - Home: Main dashboard, market indices, morning brief, quick analysis access.
        Tab 2 - Markets: Hub for all analytical tools. Contains sub-sections:
        \(MarketSection.allCases.filter { ReleaseGate.isVisible($0) }.map { "  - \($0.englishTitle): \($0.description)" }.joined(separator: "\n"))
        Tab 3 - Experts: Expert stock ideas, curated research, thematic baskets from SEBI-registered advisors.
        Tab 4 - News: Multimedia news feed, articles, real-time financial newswire.
        Tab 5 - Portfolio: Holdings, net worth, daily P&L, transaction history, allocation breakdown, risk analysis, red flags, trade journal, exports (Excel/PDF).

        ADDITIONAL FEATURES:
        - AI Copilot (floating sparkles button): Available everywhere via the gold sparkles icon in bottom-right corner.
        - Stock Analysis: Tap any stock to open its action hub, which runs a Standard, Deep Scan or Extreme Scan AI report, or opens the cached report.
        - Settings (profile avatar in the Home screen header): trading preferences, notifications, AI preferences, theme (dark/light), biometric lock, data & privacy, account.
        - Calculators (FD, EMI, SIP, Gratuity): Portfolio > Tools card, or Settings > Tools > Calculators.
        - Price Alerts: bell icon in the Home screen header (also Markets > Alerts); the notification inbox is the tray icon on the Alerts screen and Portfolio > Inbox.
        - Glossary: Tap underlined terms anywhere to see definitions. Full glossary via the book icon in the Home screen header.
        - AI How It Works: Pipeline explainer accessible from the stock action hub info button.
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

                            // While a reply is pending this is a Stop button that cancels the request.
                            Button(action: {
                                HapticManager.selection()
                                if isTyping { sendTask?.cancel() } else { sendMessage() }
                            }) { ZStack {
                                    Circle()
                                        .fill(sendButtonActive ? Theme.securityGold : Theme.inkTertiary.opacity(0.2))
                                        .frame(width: 44, height: 44)
                                    Image(systemName: isTyping ? "xmark" : "arrow.up")
                                        .font(Theme.engravedSerif(size: 16, weight: .bold))
                                        .foregroundColor(sendButtonActive ? Theme.canvas : Theme.inkTertiary)
                                }
                            }
                            .disabled(!sendButtonActive)
                            .buttonStyle(EKPressStyle())
                            .accessibilityLabel(isTyping ? "Stop" : "Send message")
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
                    .accessibilityLabel("Close assistant")
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
                    .padding(.vertical, Theme.Spacing.xSmall)
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

                if msg.isError {
                    if msg.id == messages.last?.id {
                        Button(action: { HapticManager.selection(); retry(msg) }) {
                            Label("Retry", systemImage: "arrow.clockwise")
                                .font(Theme.officialStampFont(size: 11, relativeTo: .caption))
                                .foregroundColor(Theme.securityGold)
                        }
                        .buttonStyle(EKPressStyle())
                        .disabled(isTyping)
                        .accessibilityLabel("Retry last question")
                    }
                } else {
                    CopilotDisclaimerCaption()
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
                guard !MotionPolicy.isReduced() else { return }
                withAnimation(Animation.easeInOut(duration: 0.6).repeatForever()) {
                    dotOffset = 3
                }
            }

            Spacer()
        }
    }

    // MARK: - Actions

    private var sendButtonActive: Bool { isTyping || !messageText.isEmpty }

    private func sendMessage() {
        let text = messageText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isTyping else { return }
        messageText = ""
        send(text)
    }

    /// Resends the question whose reply failed (drops the failed pair first so it is not duplicated).
    private func retry(_ failed: ChatMessage) {
        guard !isTyping, let i = messages.firstIndex(where: { $0.id == failed.id }), i > 0,
              messages[i - 1].role == "user" else { return }
        let text = messages[i - 1].content
        messages.removeSubrange((i - 1)...i)
        if messageText == text { messageText = "" }
        send(text)
    }

    /// History is captured before the new question is appended, so the question is sent once
    /// (as user_message). On failure the draft is restored; Stop undoes the send.
    private func send(_ text: String) {
        let history = Self.historyPayload(from: messages)
        let userMsg = ChatMessage(role: "user", content: text)
        let userID = userMsg.id
        messages.append(userMsg)
        isTyping = true

        sendTask = Task {
            do {
                let response = try await fetchCopilotResponse(userMessage: text, history: history)
                try Task.checkCancellation()
                HapticManager.success()
                messages.append(ChatMessage(
                    role: "assistant",
                    content: response.reply,
                    contextCards: response.context_cards
                ))
                A11y.announce(stripEmoji(response.reply))
            } catch {
                if messageText.isEmpty { messageText = text }
                if Task.isCancelled || error is CancellationError || (error as? URLError)?.code == .cancelled {
                    messages.removeAll { $0.id == userID }
                } else {
                    HapticManager.error()
                    let copy = Self.friendlyError(error)
                    messages.append(ChatMessage(role: "assistant", content: copy, isError: true))
                    A11y.announce(copy)
                }
            }
            isTyping = false
            sendTask = nil
        }
    }

    /// LLM conversation history: real user/assistant turns only (no welcome stub, error bubbles,
    /// blank entries or questions whose reply failed), capped to the last 20.
    static func historyPayload(from messages: [ChatMessage]) -> [[String: String]] {
        let kept = messages.indices.filter { i in
            let m = messages[i]
            guard !m.isWelcome, !m.isError, m.role == "user" || m.role == "assistant",
                  !m.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return false }
            return !(m.role == "user" && i + 1 < messages.count && messages[i + 1].isError)
        }
        return kept.suffix(20).map { ["role": messages[$0].role, "content": messages[$0].content] }
    }

    /// User-facing copy for a failed request; never the raw localizedDescription.
    static func friendlyError(_ error: Error) -> String {
        if let net = error as? NetworkError, let copy = net.errorDescription { return copy }
        if error is URLError { return NetworkError.userMessage(status: -1, serverDetail: nil) }
        return "Copilot couldn't answer that. Please try again."
    }

    private func fetchCopilotResponse(userMessage: String, history: [[String: String]]) async throws -> CopilotResponse {
        let requestBody: [String: Any] = [
            "user_message": userMessage,
            "conversation_history": history,
            "current_context": (currentContext ?? [:]).merging(Self.appNavigationContext) { _, new in new }
        ]

        return try await NetworkManager.shared.copilotChat(requestBody)
    }
}

/// Shown under every assistant reply (SEBI: AI output is not investment advice).
struct CopilotDisclaimerCaption: View {
    var body: some View {
        Text("AI-generated. Not investment advice.")
            .font(Theme.engravedSerif(size: 10, weight: .regular, relativeTo: .caption2))
            .foregroundColor(Theme.inkTertiary)
            .accessibilityIdentifier("copilot.disclaimer")
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
                    .accessibilityLabel("Open AI assistant")
                    .padding(.trailing, Theme.screenPadding + Theme.Spacing.standard)
                    .padding(.bottom, Theme.Spacing.standard + Theme.tabBarHeight)
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
