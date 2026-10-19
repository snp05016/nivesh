// Models/Common.swift
// Domain: Shared foundational types — ticker identity, signal classification, local persistence, user auth

import SwiftUI
import Combine
import OSLog

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
        didSet { if !isLoading { persist() } }
    }

    /// Set while loadReports assigns, so a launch never rewrites the file.
    private var isLoading = false

    static var defaultFileURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("saved_reports.json")
    }

    private let fileURL: URL

    /// Original bytes of a file that held reports this build cannot decode.
    var backupURL: URL {
        fileURL.deletingPathExtension().appendingPathExtension("undecodable.json")
    }

    /// `fileURL` is injectable so tests can use a temp file.
    init(fileURL: URL = LocalReportManager.defaultFileURL) {
        self.fileURL = fileURL
        loadReports()
        // FINSEC-06: saved reports belong to the signed-in user; wipe them on logout.
        NotificationCenter.default.addObserver(forName: AuthManager.didLogout, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in
                guard let self else { return }
                self.savedReports = []
                try? FileManager.default.removeItem(at: self.backupURL)
            }
        }
    }

    /// IOSCORE-13: atomic, so an interrupted write cannot leave a truncated file.
    private func persist() {
        do {
            let encoded = try JSONEncoder().encode(savedReports)
            try encoded.write(to: fileURL, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        } catch {
            os_log(.error, "[Nivesh/Reports] Saving reports failed: %{public}@", error.localizedDescription)
        }
    }

    /// IOSCORE-13: decoded element by element, so one report that no longer
    /// decodes (e.g. after a StockAnalysis schema change) does not hide the rest.
    /// Loading never writes the file. If any element fails to decode, the
    /// original bytes are first copied to `backupURL` (never overwriting an
    /// existing backup), so a later save cannot destroy reports a hotfix or
    /// downgrade could still read.
    func loadReports() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        let decoded = (try? JSONDecoder().decode([LossyReport].self, from: data))?.compactMap(\.value) ?? []
        let rawCount = ((try? JSONSerialization.jsonObject(with: data)) as? [Any])?.count
        if rawCount != decoded.count, !data.isEmpty,
           !FileManager.default.fileExists(atPath: backupURL.path) {
            do {
                try data.write(to: backupURL, options: [.withoutOverwriting, .completeFileProtectionUntilFirstUserAuthentication])
            } catch {
                os_log(.error, "[Nivesh/Reports] Backup of undecodable reports not written: %{public}@", error.localizedDescription)
            }
        }
        isLoading = true
        defer { isLoading = false }
        savedReports = decoded.sorted { $0.analysisDate > $1.analysisDate }
    }

    private struct LossyReport: Decodable {
        let value: StockAnalysis?
        init(from decoder: Decoder) throws {
            value = try? StockAnalysis(from: decoder)
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
