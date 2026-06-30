import SwiftUI
import Combine

struct MarketAnomaly: Identifiable, Codable {
    var id: String { ticker + anomaly_type }
    let ticker: String
    let company: String?
    let anomaly_type: String
    let severity: String
    let detail: String
    let price: Double
    let change_pct: Double
    let timestamp: String
}

@MainActor
class MarketAnomalyViewModel: ObservableObject {
    @Published var anomalies: [MarketAnomaly] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    @Published var selectedFilter: String = "ALL"
    
    var availableFilters: [String] {
        let types = Set(anomalies.map { $0.anomaly_type })
        return ["ALL"] + Array(types).sorted()
    }
    
    var filteredAnomalies: [MarketAnomaly] {
        if selectedFilter == "ALL" {
            return anomalies
        }
        return anomalies.filter { $0.anomaly_type == selectedFilter }
    }
    
    func fetchAnomalies() async {
        isLoading = true
        errorMessage = nil
        
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)/api/v1/market/anomalies?limit=20") else { return }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decoded = try JSONDecoder().decode([MarketAnomaly].self, from: data)
            self.anomalies = decoded
        } catch {
            self.errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
}

struct MarketAnomalyScreen: View {
    @StateObject private var vm = MarketAnomalyViewModel()
    @State private var showHelp = false
    
    var body: some View {
        Group {
            ZStack {
                Theme.canvasDeep.ignoresSafeArea()
                
                ScrollView {
                    VStack(spacing: Theme.Spacing.large) {
                        if !vm.availableFilters.isEmpty {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: Theme.Spacing.standard) {
                                    ForEach(vm.availableFilters, id: \.self) { filter in
                                        Button(action: { HapticManager.selection();  HapticManager.selection()
                                            withAnimation {
                                                vm.selectedFilter = filter
                                            }
                                        }) {
                                            Text(filter.replacingOccurrences(of: "_", with: " "))
                                                .font(Theme.labelStyle)
                                                .padding(.horizontal, Theme.Spacing.standard)
                                                .padding(.vertical, Theme.Spacing.tight)
                                                .background(vm.selectedFilter == filter ? Theme.inkPrimary : Color.clear)
                                                .foregroundColor(vm.selectedFilter == filter ? Theme.canvas : Theme.inkSecondary)
                                                .overlay(
                                                    RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                                        .stroke(vm.selectedFilter == filter ? Theme.inkPrimary : Theme.borderFine, lineWidth: 1)
                                                )
                                        }
                                        .buttonStyle(EKPressStyle())
                                        .simultaneousGesture(TapGesture().onEnded {
                                            HapticManager.selection()
                                        })
                                    }
                                }
                                .padding(.horizontal, Theme.screenPadding)
                            }
                        }
                        
                        if vm.isLoading && vm.anomalies.isEmpty {
                            ProgressView("Scanning Market...")
                                .padding()
                        } else if let error = vm.errorMessage {
                            Text("Error: \(error)")
                                .foregroundColor(Theme.bearRed)
                                .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                                .padding()
                        } else if vm.filteredAnomalies.isEmpty {
                            Text("No anomalies found")
                                .foregroundColor(Theme.inkSecondary)
                                .font(Theme.engravedSerif(size: 16, relativeTo: .body))
                                .padding()
                        } else {
                            LazyVStack(spacing: Theme.Spacing.card) {
                                ForEach(vm.filteredAnomalies) { anomaly in
                                    AnomalyCard(anomaly: anomaly)
                                }
                            }
                            .padding(.horizontal, Theme.screenPadding)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.large)
                }
                .refreshable {
                    HapticManager.selection()
                    await vm.fetchAnomalies()
                }
            }
            .navigationTitle("Anomaly Scanner")
            .navigationBarTitleDisplayMode(.inline)
            .task {
                if vm.anomalies.isEmpty {
                    await vm.fetchAnomalies()
                }
            }
            .toolbar { HapticManager.selection();  ToolbarItem(placement: .navigationBarTrailing) { HelpTypedButton(showHelp: $showHelp) } }
        }
        .helpSheet(isPresented: $showHelp, title: FeatureHelp.anomalies.title, subtitle: FeatureHelp.anomalies.subtitle, sections: FeatureHelp.anomalies.sections)
    }
}

struct AnomalyCard: View {
    let anomaly: MarketAnomaly
    
    var severityColor: Color {
        switch anomaly.severity {
        case "HIGH": return Theme.bearRed
        case "MEDIUM": return Theme.holdAmber
        default: return Theme.signalEmerald
        }
    }
    
    var body: some View {
        NavigationLink(destination: Text("Stock Profile for \(anomaly.ticker)").font(Theme.engravedSerif(size: 24, relativeTo: .title))) {
            VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                        Text(anomaly.ticker)
                            .font(Theme.officialStampFont(size: 18, relativeTo: .title3))
                            .tracking(1.5)
                            .foregroundColor(Theme.inkPrimary)
                        
                        if let company = anomaly.company {
                            Text(company)
                                .font(Theme.engravedSerif(size: 14, relativeTo: .subheadline))
                                .foregroundColor(Theme.inkSecondary)
                                .lineLimit(1)
                                .truncationMode(.tail)
                        }
                    }
                    
                    Spacer()
                    
                    VStack(alignment: .trailing, spacing: Theme.Spacing.xSmall) {
                        Text(IndianFormatter.price(anomaly.price))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 16, relativeTo: .body))
                            .foregroundColor(Theme.inkPrimary)
                        
                        Text(IndianFormatter.percent(anomaly.change_pct))
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                            .font(Theme.serialNumberFont(size: 14, relativeTo: .subheadline))
                            .foregroundColor(anomaly.change_pct >= 0 ? Theme.bullGreen : Theme.bearRed)
                    }
                }
                
                GuillocheDivider()
                
                HStack {
                    Text(anomaly.anomaly_type.replacingOccurrences(of: "_", with: " "))
                        .font(Theme.labelStyle)
                        .foregroundColor(Theme.inkPrimary)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .background(Theme.canvasShadow)
                        .cornerRadius(Theme.CornerRadius.small)
                    
                    Spacer()
                    
                    Text(anomaly.severity)
                        .font(Theme.labelStyle)
                        .foregroundColor(severityColor)
                        .padding(.horizontal, Theme.Spacing.tight)
                        .padding(.vertical, Theme.Spacing.xSmall)
                        .overlay(
                            RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                .stroke(severityColor.opacity(0.3), lineWidth: 1)
                        )
                }
                
                Text(anomaly.detail)
                    .font(Theme.engravedSerif(size: 14, relativeTo: .body))
                    .foregroundColor(Theme.inkSecondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .multilineTextAlignment(.leading)
            }
            .padding(Theme.Spacing.card)
            .banknoteCard()
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(EKPressStyle())
        .simultaneousGesture(TapGesture().onEnded {
            HapticManager.selection()
        })
    }
}
