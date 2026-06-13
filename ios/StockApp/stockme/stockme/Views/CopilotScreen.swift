import SwiftUI
import Combine

struct ChatMessage: Identifiable {
    let id = UUID()
    let role: String
    let content: String
    let contextCards: [[String: Any]]?
}

struct CopilotScreen: View {
    @EnvironmentObject var authManager: AuthManager
    @Environment(\.dismiss) var dismiss
    @State private var messageText: String = ""
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: "assistant", content: "How can I assist you with your financial analysis today?", contextCards: nil)
    ]
    @State private var isTyping: Bool = false
    @State private var dotOffset: CGFloat = 0

    let currentContext: [String: Any]?

    var body: some View {
        NavigationStack {
            ZStack {
                Theme.canvasShadow.ignoresSafeArea()
                Theme.canvas.opacity(0.8).ignoresSafeArea()
                
                VStack(spacing: Theme.Spacing.none) {
                    ScrollViewReader { proxy in
                        ScrollView {
                            VStack(spacing: Theme.Spacing.card) {
                                ForEach(messages) { msg in
                                    if msg.role == "user" {
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
                        
                        // Context Chips
                        if let context = currentContext, let ticker = context["ticker"] as? String {
                            HStack {
                                Text("[ \(ticker) ]")
                                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                                    .foregroundColor(Theme.securityGold)
                                    .padding(.horizontal, Theme.Spacing.small)
                                    .padding(.vertical, Theme.Spacing.xSmall)
                                    .background(Theme.securityGold.opacity(0.1))
                                    .cornerRadius(Theme.CornerRadius.small)
                                Spacer()
                            }
                            .padding(.horizontal, Theme.screenPadding)
                            .padding(.top, Theme.Spacing.small)
                        }
                        
                        // Input field
                        HStack(spacing: Theme.Spacing.standard) {
                            TextField("Ask Copilot...", text: $messageText)
                                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                                .padding(Theme.Spacing.standard)
                                .background(Theme.canvasDeep)
                                .cornerRadius(Theme.CornerRadius.medium)
                            
                            Button(action: sendMessage) {
                                Image(systemName: "paperplane.fill")
                                    .font(.system(size: 18, weight: .bold)) // Only SF symbol sizes allowed to use system
                                    .foregroundColor(messageText.isEmpty ? Theme.inkTertiary : Theme.canvas)
                                    .padding(Theme.Spacing.standard)
                                    .background(messageText.isEmpty ? Theme.canvasDeep : Theme.securityGold)
                                    .clipShape(Circle())
                            }
                            .disabled(messageText.isEmpty || isTyping)
                            .buttonStyle(EKPressStyle())
                        }
                        .padding(Theme.screenPadding)
                    }
                    .background(Theme.canvas)
                }
            }
            .navigationTitle("Financial Copilot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") {
                        HapticManager.selection()
                        dismiss()
                    }
                    .font(Theme.officialStampFont(size: 12, relativeTo: .body))
                    .foregroundColor(Theme.securityGold)
                }
            }
        }
    }
    
    private func userBubble(_ text: String) -> some View {
        HStack {
            Spacer()
            Text(stripEmoji(text))
                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                .foregroundColor(Theme.inkPrimary)
                .padding(Theme.Spacing.standard)
                .background(Theme.canvasDeep)
                .cornerRadius(Theme.CornerRadius.large)
                .padding(.leading, Theme.Spacing.xLarge)
        }
    }
    
    private func assistantBubble(_ msg: ChatMessage) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                Text("COPILOT")
                    .font(Theme.officialStampFont(size: 10, relativeTo: .caption))
                    .foregroundColor(Theme.securityGold)
                
                Text(stripEmoji(msg.content))
                    .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                    .foregroundColor(Theme.inkPrimary)
                
                if let cards = msg.contextCards {
                    ForEach(0..<cards.count, id: \.self) { idx in
                        if let signal = cards[idx]["signal"] as? String {
                            HStack {
                                Text("Signal:")
                                    .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                                    .foregroundColor(Theme.inkSecondary)
                                Text(signal)
                                    .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                                    .foregroundColor(signal.contains("BULL") ? Theme.bullGreen : Theme.bearRed)
                            }
                            .padding(.top, Theme.Spacing.xSmall)
                        }
                    }
                }
            }
            .padding(Theme.Spacing.standard)
            .frame(maxWidth: .infinity, alignment: .leading)
            .banknoteCard()
            .padding(.trailing, Theme.Spacing.xLarge)
            
            Spacer()
        }
    }
    
    private func typingIndicator() -> some View {
        HStack {
            HStack(spacing: Theme.Spacing.xSmall) {
                Circle().frame(width: 6, height: 6).offset(y: dotOffset)
                Circle().frame(width: 6, height: 6).offset(y: -dotOffset)
                Circle().frame(width: 6, height: 6).offset(y: dotOffset)
            }
            .foregroundColor(Theme.securityGold)
            .padding(Theme.Spacing.standard)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.large)
            .onAppear {
                withAnimation(Animation.easeInOut(duration: 0.5).repeatForever()) {
                    dotOffset = 4
                }
            }
            Spacer()
        }
    }
    
    private func sendMessage() {
        guard !messageText.isEmpty else { return }
        HapticManager.heavy()
        let userMsg = ChatMessage(role: "user", content: messageText, contextCards: nil)
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
                        content: "Sorry, I encountered an error: \(error.localizedDescription)", 
                        contextCards: nil
                    ))
                    isTyping = false
                }
            }
        }
    }
    
    private func fetchCopilotResponse(userMessage: String) async throws -> CopilotResponse {
        // Construct history
        let history = messages.map { ["role": $0.role, "content": $0.content] }
        
        let requestBody: [String: Any] = [
            "user_message": userMessage,
            "conversation_history": history,
            "current_context": currentContext ?? [:]
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
                            .font(.system(size: 20, weight: .bold)) // Only SF symbol sizes
                            .foregroundColor(Theme.canvas)
                            .padding(Theme.Spacing.card)
                            .background(Theme.securityGold)
                            .clipShape(Circle())
                            .shadow(color: Theme.securityGold.opacity(0.4), radius: 8, x: 0, y: 4)
                    }
                    .buttonStyle(EKPressStyle())
                    .padding(.trailing, Theme.screenPadding)
                    .padding(.bottom, Theme.Spacing.xLarge + Theme.Spacing.standard)
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
