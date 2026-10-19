import SwiftUI

// MARK: - Portfolio Charts Strip (backend-generated chart PNGs)

struct PortfolioChartsStrip: View {
    let userId: Int
    @State private var charts: [ChartItem] = []
    @State private var isLoading = false
    @State private var errorMsg: String? = nil
    @State private var expandedChart: ChartItem? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.standard) {
            // Section header
            VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                Text("पोर्टफोलियो चार्ट")
                    .font(.caption)
                    .foregroundStyle(Theme.inkSecondary)
                Text("PORTFOLIO CHARTS")
                    .font(.caption.weight(.semibold).monospaced())
                    .tracking(2.0)
                    .foregroundStyle(Theme.inkPrimary.opacity(0.7))
            }

            if isLoading {
                ScrollView(.horizontal) {
                    HStack(alignment: .top, spacing: Theme.Spacing.card) {
                        ForEach(0..<3, id: \.self) { _ in
                            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.tight)
                                    .fill(Theme.inkTertiary.opacity(0.08))
                                    .frame(width: UIScreen.main.bounds.width * 0.85, height: UIScreen.main.bounds.height * 0.22)
                                    .overlay(
                                        ProgressView()
                                            .tint(Theme.securityGold)
                                    )
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .fill(Theme.inkTertiary.opacity(0.12))
                                    .frame(width: UIScreen.main.bounds.width * 0.55, height: 10)
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.small)
                                    .fill(Theme.inkTertiary.opacity(0.08))
                                    .frame(width: UIScreen.main.bounds.width * 0.40, height: 8)
                            }
                            .padding(Theme.Spacing.medium)
                            .background(Theme.canvasDeep)
                            .cornerRadius(Theme.CornerRadius.large)
                            .overlay(
                                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                                    .stroke(Theme.borderSage, lineWidth: 0.5)
                            )
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
                .scrollIndicators(.hidden)
            } else if let err = errorMsg {
                // Error state with detailed debug info
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    HStack(spacing: Theme.Spacing.medium) {
                        Image(systemName: "chart.bar.xaxis")
                            .font(.subheadline)
                            .foregroundStyle(Theme.bearRed.opacity(0.6))
                        Text("Charts unavailable")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Theme.inkPrimary)
                    }
                    Text("Error: \(err)")
                        .font(.caption2.monospaced())
                        .foregroundStyle(Theme.bearRed.opacity(0.7))
                        .lineLimit(3)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(action: { HapticManager.selection(); fetchCharts() }) {
                        HStack(spacing: Theme.Spacing.small) {
                            Image(systemName: "arrow.clockwise")
                                .font(.caption2)
                            Text("RETRY")
                                .font(.caption2.weight(.bold))
                        }
                        .foregroundStyle(Theme.securityGold)
                        .padding(.horizontal, Theme.Spacing.standard)
                        .padding(.vertical, Theme.Spacing.tight)
                        .background(Theme.securityGold.opacity(0.08))
                        .cornerRadius(Theme.CornerRadius.tight)
                    }
                    .padding(.top, Theme.Spacing.small)
                }
                .padding(.vertical, Theme.Spacing.standard)
            } else if !charts.isEmpty {
                ScrollView(.horizontal) {
                    HStack(alignment: .top, spacing: Theme.Spacing.card) {
                        ForEach(charts) { chart in
                            chartCard(chart)
                        }
                    }
                    .padding(.horizontal, Theme.screenPadding)
                }
                .scrollIndicators(.hidden)
            } else {
                // Empty state — charts will populate after backend generates them
                HStack(spacing: Theme.Spacing.medium) {
                    Image(systemName: "chart.bar")
                        .font(.subheadline)
                        .foregroundStyle(Theme.inkTertiary.opacity(0.6))
                    Text("Charts will appear here after portfolio snapshot is generated")
                        .font(.caption)
                        .foregroundStyle(Theme.inkTertiary)
                }
                .padding(.vertical, Theme.Spacing.standard)
            }
        }
        .onAppear { fetchCharts() }
        .sheet(item: $expandedChart) { chart in
            expandedChartView(chart)
        }
    }

    private func chartCard(_ chart: ChartItem) -> some View {
        let cardWidth = UIScreen.main.bounds.width * 0.85
        let imageHeight = UIScreen.main.bounds.height * 0.22
        return Button(action: {
            HapticManager.impact(.light)
            expandedChart = chart
        }) {
            VStack(alignment: .leading, spacing: Theme.Spacing.tight) {
                // Chart image
                AuthenticatedChartImage(path: chart.url) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: cardWidth, height: imageHeight)
                            .clipped()
                            .cornerRadius(Theme.CornerRadius.tight)
                    case .failure(_):
                        Rectangle()
                            .fill(Theme.inkTertiary.opacity(0.08))
                            .frame(width: cardWidth, height: imageHeight)
                            .cornerRadius(Theme.CornerRadius.tight)
                            .overlay(
                                Image(systemName: "chart.bar.xaxis")
                                    .font(.title2)
                                    .foregroundStyle(Theme.inkTertiary.opacity(0.4))
                            )
                    case .empty:
                        Rectangle()
                            .fill(Theme.inkTertiary.opacity(0.06))
                            .frame(width: cardWidth, height: imageHeight)
                            .cornerRadius(Theme.CornerRadius.tight)
                            .overlay(ProgressView().tint(Theme.securityGold))
                    @unknown default:
                        EmptyView()
                    }
                }

                // Title and description
                VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                    Text(chart.title)
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(Theme.inkPrimary)
                        .lineLimit(1)

                    Text(chart.description)
                        .font(.caption2)
                        .foregroundStyle(Theme.inkTertiary)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, Theme.Spacing.small)
            }
            .frame(width: cardWidth)
            .padding(Theme.Spacing.medium)
            .background(Theme.canvasDeep)
            .cornerRadius(Theme.CornerRadius.large)
            .overlay(
                RoundedRectangle(cornerRadius: Theme.CornerRadius.large)
                    .stroke(Theme.borderSage, lineWidth: 0.5)
            )
        }
        .buttonStyle(EKPressStyle())
    }

    private func expandedChartView(_ chart: ChartItem) -> some View {
        NavigationStack {
            ZStack {
                Theme.canvas.ignoresSafeArea()

                VStack(spacing: Theme.Spacing.none) {
                    // Toolbar
                    HStack {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xSmall) {
                            Text(chart.title)
                                .font(.subheadline.weight(.bold))
                                .foregroundStyle(Theme.inkPrimary)
                            Text(chart.description)
                                .font(.caption)
                                .foregroundStyle(Theme.inkSecondary)
                        }
                        Spacer()
                        Button("Done") { expandedChart = nil }.buttonStyle(EKPressStyle())
                            .font(.footnote.weight(.medium))
                            .foregroundStyle(Theme.securityGold)
                    }
                    .padding(.horizontal, Theme.Spacing.card)
                    .padding(.vertical, Theme.Spacing.standard)
                    .background(Theme.canvasDeep)

                    // Full chart image
                    ScrollView([.horizontal, .vertical]) {
                        AuthenticatedChartImage(path: chart.url) { phase in
                            switch phase {
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fit)
                            case .failure(_):
                                VStack(spacing: Theme.Spacing.standard) {
                                    Image(systemName: "exclamationmark.triangle")
                                        .font(.largeTitle)
                                        .foregroundStyle(Theme.holdAmber)
                                    Text("Failed to load chart image")
                                        .font(.footnote)
                                        .foregroundStyle(Theme.inkSecondary)
                                }
                                .frame(maxWidth: .infinity, minHeight: 300)
                            case .empty:
                                ProgressView()
                                    .frame(maxWidth: .infinity, minHeight: 300)
                            @unknown default:
                                EmptyView()
                            }
                        }
                    }
                }
            }
        }
    }

    private func fetchCharts() {
        guard !isLoading else { return }
        isLoading = true
        errorMsg = nil
        Task {
            do {
                let resp = try await NetworkManager.shared.fetchPortfolioCharts(userId: userId)
                await MainActor.run {
                    charts = resp.charts
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMsg = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Authenticated chart image

/// Loads a portfolio chart PNG with the Bearer token. AsyncImage cannot send
/// Authorization, and the backend serves charts only to their owner (AUTH-04).
struct AuthenticatedChartImage<Content: View>: View {
    let path: String
    let content: (AsyncImagePhase) -> Content
    @State private var phase: AsyncImagePhase = .empty

    init(path: String, @ViewBuilder content: @escaping (AsyncImagePhase) -> Content) {
        self.path = path
        self.content = content
    }

    var body: some View {
        content(phase)
            .task(id: path) { await load() }
    }

    private func load() async {
        phase = .empty
        guard let url = URL(string: "\(NetworkManager.shared.baseURL)\(path)") else {
            phase = .failure(URLError(.badURL))
            return
        }
        do {
            let request = NetworkManager.shared.authRequest(url)
            let (data, response) = try await NetworkManager.shared.session.data(for: request)
            guard (response as? HTTPURLResponse)?.statusCode == 200,
                  let uiImage = UIImage(data: data) else {
                phase = .failure(URLError(.badServerResponse))
                return
            }
            phase = .success(Image(uiImage: uiImage))
        } catch {
            phase = .failure(error)
        }
    }
}
