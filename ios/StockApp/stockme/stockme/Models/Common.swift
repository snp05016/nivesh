// Models/Common.swift
// Domain: Shared foundational types — ticker identity, signal classification, local persistence, user auth

import SwiftUI
import Combine

// MARK: - Stock Identity

struct Stock: Codable, Identifiable {
    var id: String { ticker }
    let ticker: String
    let companyName: String
    let exchange: String // NSE or BSE
    var currentPrice: Double
    var changePercent: Double
    var signal: Signal?
}

// MARK: - Signal Classification

enum Signal: String, Codable {
    case bullish = "BULLISH"
    case cautiously_bullish = "CAUTIOUSLY BULLISH"
    case neutral = "NEUTRAL"
    case hold = "HOLD"
    case cautiously_bearish = "CAUTIOUSLY BEARISH"
    case bearish = "BEARISH"

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let raw = (try? container.decode(String.self))?.uppercased().trimmingCharacters(in: .whitespaces) ?? ""
        switch raw {
        case "BULLISH", "BUY", "STRONG BUY", "STRONG_BUY":
            self = .bullish
        case "CAUTIOUSLY BULLISH", "CAUTIOUS_BULLISH":
            self = .cautiously_bullish
        case "NEUTRAL":
            self = .neutral
        case "HOLD":
            self = .hold
        case "CAUTIOUSLY BEARISH", "CAUTIOUS_BEARISH":
            self = .cautiously_bearish
        case "BEARISH", "SELL", "AVOID", "STRONG SELL", "STRONG_SELL":
            self = .bearish
        default:
            self = .neutral // never crash on unknown signal
        }
    }

    var color: Color {
        switch self {
        case .bullish: return Theme.signalEmerald
        case .cautiously_bullish: return Theme.signalEmerald.opacity(0.7)
        case .neutral, .hold: return Theme.securityGold
        case .cautiously_bearish: return Theme.signalRuby.opacity(0.7)
        case .bearish: return Theme.signalRuby
        }
    }

    var label: String { self.rawValue }

    var shortLabel: String {
        switch self {
        case .bullish: return "BULL"
        case .cautiously_bullish: return "C.BULL"
        case .neutral: return "NEUT"
        case .hold: return "HOLD"
        case .cautiously_bearish: return "C.BEAR"
        case .bearish: return "BEAR"
        }
    }
}

// MARK: - User Auth

struct LoggedInUser: Codable {
    let userId: Int
    let username: String
    let displayName: String
    let token: String

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case username
        case displayName = "display_name"
        case token = "access_token"
    }
}

// MARK: - Local Persistence

@MainActor
class LocalReportManager: ObservableObject {
    /// Every mutation is written to disk (FINSEC-06), so "Void all records" and
    /// swipe-to-delete in ReportManagerView no longer come back on next launch.
    @Published var savedReports: [StockAnalysis] = [] {
        didSet { persist() }
    }

    private let fileURL: URL = {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        return docs.appendingPathComponent("saved_reports.json")
    }()

    init() {
        loadReports()
        // FINSEC-06: saved reports belong to the signed-in user; wipe them on logout.
        NotificationCenter.default.addObserver(forName: AuthManager.didLogout, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.savedReports = [] }
        }
    }

    private func persist() {
        if let encoded = try? JSONEncoder().encode(savedReports) {
            try? encoded.write(to: fileURL)
        }
    }

    func loadReports() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        if let decoded = try? JSONDecoder().decode([StockAnalysis].self, from: data) {
            self.savedReports = decoded.sorted { $0.analysisDate > $1.analysisDate }
        }
    }

    func saveReport(_ report: StockAnalysis) {
        savedReports = [report] + savedReports.filter { $0.ticker != report.ticker }
    }

    func deleteReport(ticker: String) {
        savedReports.removeAll { $0.ticker == ticker }
    }

    func getReport(for ticker: String) -> StockAnalysis? {
        return savedReports.first { $0.ticker == ticker }
    }
}
