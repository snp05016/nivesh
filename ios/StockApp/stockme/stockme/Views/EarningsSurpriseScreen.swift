import SwiftUI
import Combine

struct EarningsSurprise: Codable, Identifiable {
    var id: String { ticker + quarter }
    let ticker: String
    let company_name: String
    let quarter: String
    let estimated_eps: Double?
    let actual_eps: Double?
    let surprise_pct: Double?
    let classification: String // BEAT, MISS, INLINE
    let post_price_1d: Double?
    let post_price_5d: Double?
    let historical_score: Double?
    let serial_pattern: String?
}

class EarningsSurpriseViewModel: ObservableObject {
    @Published var surprises: [EarningsSurprise] = []
    @Published var isLoading: Bool = false
    @Published var errorMessage: String? = nil
    @Published var isCalendarView: Bool = false

    func fetchSurprises() {
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/earnings/surprises?period=current_quarter") else { return }
        
        self.isLoading = true
        self.errorMessage = nil
        
        URLSession.shared.dataTask(with: url) { data, response, error in
            DispatchQueue.main.async {
                self.isLoading = false
                if let error = error {
                    self.errorMessage = "Failed to load surprises: \(error.localizedDescription)"
                    return
                }
                guard let data = data else {
                    self.errorMessage = "No data received."
                    return
                }
                do {
                    let decoder = JSONDecoder()
                    self.surprises = try decoder.decode([EarningsSurprise].self, from: data)
                    // Sort biggest surprises first
                    self.surprises.sort { 
                        abs($0.surprise_pct ?? 0) > abs($1.surprise_pct ?? 0)
                    }
                } catch {
                    self.errorMessage = "Failed to parse data: \(error.localizedDescription)"
                }
            }
        }.resume()
    }
}

struct EarningsSurpriseScreen: View {
    @StateObject private var viewModel = EarningsSurpriseViewModel()
    
    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.large) {
                // Header
                HStack {
                    Text("Earnings Surprise")
                        .font(Theme.engravedSerif(size: 28, weight: .bold, relativeTo: .title))
                        .foregroundColor(Theme.inkPrimary)
                    Spacer()
                    
                    // Calendar toggle
                    Button(action: {
                        HapticManager.selection()
                        withAnimation {
                            viewModel.isCalendarView.toggle()
                        }
                    }) {
                        Image(systemName: viewModel.isCalendarView ? "list.bullet" : "calendar")
                            .font(.system(size: 20))
                            .foregroundColor(Theme.inkPrimary)
                            .padding(Theme.Spacing.small)
                            .background(Theme.canvasDeep)
                            .cornerRadius(Theme.CornerRadius.small)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .stroke(Theme.borderFine, lineWidth: 1)
                            )
                    }
                    .buttonStyle(EKPressStyle())
                }
                .padding(.horizontal, Theme.screenPadding)
                .padding(.top, Theme.Spacing.screen)
                
                if viewModel.isLoading {
                    ProgressView()
                        .padding(.top, 50)
                } else if let error = viewModel.errorMessage {
                    Text(error)
                        .font(Theme.officialStampFont(size: 14, relativeTo: .subheadline))
                        .foregroundColor(Theme.bearRed)
                        .padding(.horizontal, Theme.screenPadding)
                } else {
                    // Summary Hero
                    let beats = viewModel.surprises.filter { $0.classification == "BEAT" }.count
                    let misses = viewModel.surprises.filter { $0.classification == "MISS" }.count
                    let inlines = viewModel.surprises.filter { $0.classification == "INLINE" }.count
                    
                    VStack(spacing: Theme.Spacing.standard) {
                        Text("THIS QUARTER")
                            .font(Theme.officialStampFont(size: 12, relativeTo: .caption))
                            .foregroundColor(Theme.inkTertiary)
                            .tracking(1.5)
                        
                        HStack(spacing: Theme.Spacing.standard) {
                            SummaryBadge(label: "BEATS", count: beats, color: Theme.bullGreen)
                            SummaryBadge(label: "MISSES", count: misses, color: Theme.bearRed)
                            SummaryBadge(label: "INLINE", count: inlines, color: Theme.holdAmber)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.card)
                    .frame(maxWidth: .infinity)
                    .banknoteCard()
                    .padding(.horizontal, Theme.screenPadding)
                    
                    GuillocheDivider()
                        .padding(.horizontal, Theme.screenPadding)
                    
                    if viewModel.isCalendarView {
                        // Dummy calendar view
                        VStack(spacing: Theme.Spacing.card) {
                            Image(systemName: "calendar.badge.exclamationmark")
                                .font(.system(size: 40))
                                .foregroundColor(Theme.inkSecondary)
                            Text("Calendar View Coming Soon")
                                .font(Theme.engravedSerif(size: 16, weight: .regular, relativeTo: .body))
                                .foregroundColor(Theme.inkSecondary)
                        }
                        .padding(.vertical, 50)
                    } else {
                        LazyVStack(spacing: Theme.Spacing.card) {
                            ForEach(viewModel.surprises) { surprise in
                                NavigationLink(value: surprise.ticker) {
                                    SurpriseCard(surprise: surprise)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        }
                        .padding(.horizontal, Theme.screenPadding)
                        .padding(.bottom, Theme.Spacing.large)
                    }
                }
            }
        }
        .background(Theme.canvas.edgesIgnoringSafeArea(.all))
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            if viewModel.surprises.isEmpty {
                viewModel.fetchSurprises()
            }
        }
        // Assuming StockProfileView is registered in the main App NavigationStack
    }
}

struct SummaryBadge: View {
    let label: String
    let count: Int
    let color: Color
    
    var body: some View {
        VStack(spacing: Theme.Spacing.small) {
            Text("\(count)")
                .font(Theme.serialNumberFont(size: 24, relativeTo: .title2))
                .foregroundColor(color)
            Text(label)
                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                .foregroundColor(Theme.inkSecondary)
                .tracking(1.0)
        }
        .frame(maxWidth: .infinity)
    }
}

struct SurpriseCard: View {
    let surprise: EarningsSurprise
    
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(surprise.ticker)
                        .font(Theme.serialNumberFont(size: 18, relativeTo: .headline))
                        .foregroundColor(Theme.inkPrimary)
                    Text(surprise.company_name)
                        .font(Theme.engravedSerif(size: 14, weight: .regular, relativeTo: .subheadline))
                        .foregroundColor(Theme.inkSecondary)
                        .lineLimit(1)
                }
                Spacer()
                
                // Classification Badge
                Text(surprise.classification)
                    .font(Theme.labelStyle)
                    .padding(.horizontal, Theme.Spacing.tight)
                    .padding(.vertical, Theme.Spacing.xSmall)
                    .background(classificationColor(surprise.classification).opacity(0.1))
                    .foregroundColor(classificationColor(surprise.classification))
                    .cornerRadius(Theme.CornerRadius.small)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                            .stroke(classificationColor(surprise.classification).opacity(0.3), lineWidth: 1)
                    )
            }
            
            Divider().background(Theme.borderFine)
            
            HStack(spacing: Theme.Spacing.card) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("EST EPS")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                    Text(surprise.estimated_eps != nil ? "₹\(String(format: "%.2f", surprise.estimated_eps!))" : "-")
                        .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                        .foregroundColor(Theme.inkSecondary)
                }
                
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text("ACTUAL EPS")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                    Text(surprise.actual_eps != nil ? "₹\(String(format: "%.2f", surprise.actual_eps!))" : "-")
                        .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                        .foregroundColor(Theme.inkPrimary)
                }
                
                Spacer()
                
                VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                    Text("SURPRISE")
                        .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        .foregroundColor(Theme.inkTertiary)
                    if let pct = surprise.surprise_pct {
                        Text(IndianFormatter.percent(pct))
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(classificationColor(surprise.classification))
                    } else {
                        Text("-")
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(Theme.inkSecondary)
                    }
                }
            }
            
            // Post-earnings and serial pattern
            if surprise.post_price_5d != nil || surprise.serial_pattern != nil {
                HStack(alignment: .bottom) {
                    if let pattern = surprise.serial_pattern {
                        HStack(spacing: Theme.Spacing.xSmall) {
                            Image(systemName: surprise.classification == "BEAT" ? "flame.fill" : "exclamationmark.triangle.fill")
                                .font(.system(size: 10))
                            Text(pattern.uppercased())
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                        }
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.securityGoldLight.opacity(0.1))
                        .foregroundColor(Theme.securityGold)
                        .cornerRadius(Theme.CornerRadius.small)
                    }
                    
                    Spacer()
                    
                    if let post5d = surprise.post_price_5d {
                        VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                            Text("5D REACTION")
                                .font(Theme.officialStampFont(size: 10, relativeTo: .caption2))
                                .foregroundColor(Theme.inkTertiary)
                            Text(IndianFormatter.percent(post5d))
                                .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                                .foregroundColor(post5d >= 0 ? Theme.bullGreen : Theme.bearRed)
                        }
                    }
                }
                .padding(.top, Theme.Spacing.small)
            }
        }
        .banknoteCard()
    }
    
    private func classificationColor(_ cls: String) -> Color {
        switch cls {
        case "BEAT": return Theme.bullGreen
        case "MISS": return Theme.bearRed
        default: return Theme.holdAmber
        }
    }
}
