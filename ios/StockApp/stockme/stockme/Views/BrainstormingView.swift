import SwiftUI

struct BrainstormingView: View {
    @State private var topic: String = ""
    @State private var riskTolerance: String = "Moderate"
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var results: [BrainstormIdea] = []
    
    let riskOptions = ["Conservative", "Moderate", "Aggressive"]
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.large) {
                
                // Form Section
                VStack(alignment: .leading, spacing: Theme.Spacing.card) {
                    Text("Brainstorm Ideas")
                        .font(Theme.engravedSerif(size: 24, weight: .bold, relativeTo: .title))
                        .foregroundColor(Theme.inkPrimary)
                    
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("Topic")
                            .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(Theme.inkSecondary)
                            .tracking(1.5)
                        
                        TextField("e.g. EV battery stocks...", text: $topic)
                            .padding(Theme.Spacing.standard)
                            .background(Theme.canvasDeep)
                            .cornerRadius(Theme.CornerRadius.medium)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.medium)
                                    .stroke(Theme.borderFine, lineWidth: 1)
                            )
                    }
                    
                    VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                        Text("Risk Tolerance")
                            .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(Theme.inkSecondary)
                            .tracking(1.5)
                        
                        Picker("Risk Tolerance", selection: $riskTolerance) {
                            ForEach(riskOptions, id: \.self) { option in
                                Text(option).tag(option)
                            }
                        }
                        .pickerStyle(.segmented)
                        .colorMultiply(Theme.securityGold) // Security gold accent
                    }
                    
                    Button(action: {
                        HapticManager.selection()
                        Task {
                            await submitBrainstorm()
                        }
                    }) {
                        Text("Generate Ideas")
                            .font(Theme.officialStampFont(size: 16, relativeTo: .headline))
                            .foregroundColor(Theme.canvas)
                            .frame(maxWidth: .infinity)
                            .padding(Theme.Spacing.card)
                            .background(Theme.securityGold)
                            .cornerRadius(Theme.CornerRadius.medium)
                    }
                    .ekPress()
                    .disabled(topic.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                    .opacity((topic.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading) ? 0.5 : 1.0)
                    
                    if let error = errorMessage {
                        Text(error)
                            .font(Theme.engravedSerif(size: 14, relativeTo: .footnote))
                            .foregroundColor(Theme.bearRed)
                            .padding(.top, Theme.Spacing.medium)
                    }
                }
                .padding(Theme.Spacing.card)
                .banknoteCard()
                .padding(.horizontal, Theme.screenPadding)
                
                if !results.isEmpty || isLoading {
                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)
                }
                
                // Results Section
                if isLoading {
                    ProgressView()
                        .tint(Theme.securityGold)
                        .padding()
                } else if !results.isEmpty {
                    VStack(spacing: Theme.Spacing.card) {
                        ForEach(results) { idea in
                            VStack(alignment: .leading, spacing: Theme.Spacing.medium) {
                                HStack(alignment: .top) {
                                    Text(idea.title)
                                        .font(Theme.engravedSerif(size: 18, weight: .bold, relativeTo: .headline))
                                        .foregroundColor(Theme.inkPrimary)
                                    Spacer()
                                    if let ticker = idea.ticker, !ticker.isEmpty {
                                        Text(ticker)
                                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                            .foregroundColor(Theme.inkSecondary)
                                            .padding(.horizontal, Theme.Spacing.medium)
                                            .padding(.vertical, Theme.Spacing.small)
                                            .background(Theme.canvasDeep)
                                            .cornerRadius(Theme.CornerRadius.small)
                                            .overlay(
                                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                                    .stroke(Theme.securityGoldLight, lineWidth: 0.5)
                                            )
                                    }
                                }
                                
                                Text(idea.description)
                                    .font(Theme.engravedSerif(size: 15, relativeTo: .body))
                                    .foregroundColor(Theme.inkSecondary)
                                    .lineSpacing(4)
                            }
                            .padding(Theme.Spacing.card)
                            .banknoteCard()
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
            }
            .padding(.vertical, Theme.Spacing.xLarge)
        }
        .background(Theme.canvas)
        .navigationTitle("Brainstorm")
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private func submitBrainstorm() async {
        isLoading = true
        errorMessage = nil
        results = []
        
        do {
            let response = try await NetworkManager.shared.brainstorm(topic: topic, riskTolerance: riskTolerance)
            results = response.ideas
            HapticManager.success()
        } catch {
            errorMessage = "Failed to fetch ideas: \(error.localizedDescription)"
            HapticManager.error()
        }
        
        isLoading = false
    }
}
