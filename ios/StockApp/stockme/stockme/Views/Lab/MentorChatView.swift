import SwiftUI

/// Questions about a session or one trade. Answers are grounded on listed facts;
/// `mode` says whether a language model or the rules engine wrote the answer.
struct MentorChatView: View {
    @StateObject private var vm: LabMentorViewModel
    @FocusState private var focused: Bool

    init(sessionId: String, orderId: String?) {
        _vm = StateObject(wrappedValue: LabMentorViewModel(sessionId: sessionId, orderId: orderId))
    }

    var body: some View {
        LabScreen(title: "Mentor") {
            Text(vm.orderId == nil ? "Ask about this session." : "Ask about order \(vm.orderId ?? "").")
                .font(Theme.engravedSerif(size: 13, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
            if vm.exchanges.isEmpty && !vm.isAsking {
                StateMessage(icon: "bubble.left.and.text.bubble.right",
                             message: "Try: “Was my position too large for this stock's volatility?”")
            }
            ForEach(vm.exchanges) { ex in LabMentorExchangeView(exchange: ex) }
            if vm.isAsking { StateSkeleton(lines: 3).accessibilityLabel("Waiting for the mentor") }
        }
        .safeAreaInset(edge: .bottom) {
            LabMentorComposer(draft: $vm.draft, canAsk: vm.canAsk, busy: vm.isAsking, focused: $focused) {
                HapticManager.selection()
                Task { await vm.ask() }
            }
        }
    }
}

private struct LabMentorComposer: View {
    @Binding var draft: String
    let canAsk: Bool
    let busy: Bool
    var focused: FocusState<Bool>.Binding
    let onSend: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.medium) {
            TextField("Your question", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .focused(focused)
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .padding(Theme.Spacing.medium)
                .background(RoundedRectangle(cornerRadius: Theme.CornerRadius.medium).fill(Theme.canvasDeep))
            Button(action: onSend) {
                Image(systemName: busy ? "hourglass" : "arrow.up.circle.fill")
                    .font(.title2)
                    .foregroundStyle(canAsk ? Theme.securityGold : Theme.inkTertiary)
                    .frame(minWidth: 44, minHeight: 44)
            }
            .buttonStyle(EKPressStyle())
            .disabled(!canAsk)
            .accessibilityLabel("Send question")
        }
        .padding(.horizontal, Theme.screenPadding)
        // Keep the send button clear of the app-wide AI button (CopilotFloatingButtonModifier), which
        // floats bottom-right over every screen: its icon (20) + padding (2 x card) + its inset (standard).
        .padding(.trailing, 20 + 2 * Theme.Spacing.card + Theme.Spacing.standard)
        .padding(.vertical, Theme.Spacing.medium)
        .background(Theme.canvas)
    }
}

private struct LabMentorExchangeView: View {
    let exchange: LabMentorExchange

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
            Text(exchange.question)
                .font(Theme.engravedSerif(size: 14, weight: .bold, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .multilineTextAlignment(.trailing)
            if let error = exchange.error { LabInlineError(message: error) }
            if let reply = exchange.reply { LabMentorReplyCard(reply: reply) }
        }
    }
}

private struct LabMentorReplyCard: View {
    let reply: LabMentorReply

    private var badge: (String, String) {
        switch reply.modeKind {
        case .llm: return ("AI", "sparkles")
        case .rules: return ("Rules", "list.bullet.rectangle")
        case .unknown: return (reply.mode ?? "Mentor", "questionmark.circle")
        }
    }

    var body: some View {
        LabCard {
            LabChip(text: badge.0, tint: Theme.securityGold, icon: badge.1)
                .accessibilityLabel(reply.modeKind == .llm ? "Written by an AI model" : "Written by the rules engine")
            Text(LabFormat.markdown(reply.answer))
                .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                .foregroundStyle(Theme.inkPrimary)
                .fixedSize(horizontal: false, vertical: true)
            if let facts = reply.groundedOn, !facts.isEmpty { LabGroundingDisclosure(facts: facts) }
            if let d = reply.disclaimer {
                Text(d).font(Theme.microLabel()).foregroundStyle(Theme.inkTertiary).fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

private struct LabGroundingDisclosure: View {
    let facts: [String: LabJSON]

    var body: some View {
        DisclosureGroup {
            VStack(alignment: .leading, spacing: Theme.Spacing.small) {
                ForEach(facts.keys.sorted(), id: \.self) { k in
                    LabKeyValueRow(key: LabFormat.humanize(k), value: facts[k]?.display ?? "—")
                }
            }
        } label: {
            Text("Facts this answer used (\(facts.count))")
                .font(Theme.engravedSerif(size: 12, weight: .bold, relativeTo: .footnote))
                .foregroundStyle(Theme.inkSecondary)
        }
        .tint(Theme.securityGold)
    }
}
