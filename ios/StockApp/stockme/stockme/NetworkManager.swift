import Foundation
import Combine
import UserNotifications
import os.log

enum NetworkError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case serverError(Int, String?)
    case decodingError(String)
    case connectionFailed
    /// An authenticated request was rejected: the session token is missing or expired.
    case unauthorized
    /// POST /login returned 401: the username/password pair was wrong.
    case invalidCredentials
    case analysisDiagnostic(AnalysisErrorInfo)
    /// Detailed fetch failure — endpoint, HTTP status, raw body prefix for diagnostics
    case fetchFailed(endpoint: String, status: Int, body: String)

    /// User-facing copy. Never contains endpoints, HTTP codes or response bodies;
    /// those live in `diagnosticDetail` for logs and DEBUG-only diagnostics.
    var errorDescription: String? {
        switch self {
        case .invalidURL, .invalidResponse:
            return "Something went wrong. Please try again."
        case .serverError(let code, let msg):
            return Self.userMessage(status: code, serverDetail: msg)
        case .decodingError:
            return "We couldn't read the latest data. Please try again shortly."
        case .connectionFailed:
            return Self.userMessage(status: -1, serverDetail: nil)
        case .unauthorized:
            return Self.userMessage(status: 401, serverDetail: nil)
        case .invalidCredentials:
            return "Incorrect username or password."
        case .analysisDiagnostic(let info):
            return "\(info.userMessage) \(info.suggestedActionText)"
        case .fetchFailed(_, let status, _):
            return Self.userMessage(status: status, serverDetail: nil)
        }
    }

    /// Developer-facing detail (endpoint, status, body) for GlobalErrorDiagnoser and logs.
    var diagnosticDetail: String {
        switch self {
        case .invalidURL:        return "Invalid server URL"
        case .invalidResponse:   return "Response was not HTTP"
        case .serverError(let code, let msg): return "HTTP \(code): \(msg ?? "<no detail>")"
        case .decodingError(let detail): return "JSON parse failed: \(detail)"
        case .connectionFailed:  return "Connection failed"
        case .unauthorized:      return "HTTP 401: session token missing or expired"
        case .invalidCredentials: return "HTTP 401 on /login: invalid credentials"
        case .analysisDiagnostic(let info):
            return "[\(info.requestUrl)] HTTP \(info.httpStatusCode): \(info.displayDetail)"
        case .fetchFailed(let endpoint, let status, let body):
            return "[\(endpoint)] HTTP \(status): \(body.prefix(200))"
        }
    }

    /// Maps an HTTP status (negative = transport failure, 0 = no usable response)
    /// to friendly copy. `serverDetail` is shown only for validation/conflict
    /// statuses and only when it is short plain text.
    static func userMessage(status: Int, serverDetail: String?) -> String {
        let plainDetail = serverDetail.flatMap { detail -> String? in
            let trimmed = detail.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty, trimmed.count <= 200,
                  !trimmed.contains("{"), !trimmed.contains("[") else { return nil }
            return trimmed
        }
        switch status {
        case ..<0:
            return "Can't connect. Check your internet connection and try again."
        case 400, 422:
            return plainDetail ?? "Please check your input and try again."
        case 401:
            return "Your session has expired. Please sign in again."
        case 403:
            return "You don't have access to this."
        case 404:
            return "This information isn't available right now."
        case 409:
            return plainDetail ?? "That's already in progress."
        case 429:
            return "Too many requests. Please wait a minute and try again."
        case 500...599:
            return "Nivesh is having trouble right now. Please try again shortly."
        default:
            return "Something went wrong. Please try again."
        }
    }

    /// Extracts a human-readable message from a FastAPI error body:
    /// `{"detail": "..."}`, `{"detail": [{"msg": "..."}]}` or `{"detail": {"message": "..."}}`.
    static func serverDetail(from data: Data) -> String? {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        if let text = obj["detail"] as? String { return text.count <= 200 ? text : nil }
        if let list = obj["detail"] as? [[String: Any]] { return list.first?["msg"] as? String }
        if let dict = obj["detail"] as? [String: Any] { return dict["message"] as? String }
        return nil
    }

    var diagnosticInfo: AnalysisErrorInfo? {
        if case .analysisDiagnostic(let info) = self { return info }
        return nil
    }

    /// User-facing display string (same as errorDescription).
    var displayDetail: String {
        errorDescription ?? "Something went wrong. Please try again."
    }
}

private struct LoginRequest: Encodable {
    let username: String
    let password: String
}

@MainActor
class NetworkManager: ObservableObject {
    static let shared = NetworkManager()

    static let serverURLKey = "serverBaseURL"
    /// Home WiFi default. After DigitalOcean deploy, update via Settings tab —
    /// no rebuild needed (stored in UserDefaults).
    static let defaultURL   = "https://api.nivesh.qzz.io"

    var baseURL: String {
        let storedURL = UserDefaults.standard.string(forKey: Self.serverURLKey)
        let resolvedURL = ServerURLPolicy.resolve(storedURL: storedURL, defaultURL: Self.defaultURL)
        if storedURL != nil, storedURL != resolvedURL {
            UserDefaults.standard.removeObject(forKey: Self.serverURLKey)
        }
        return resolvedURL
    }

    func updateBaseURL(_ url: String) {
        let trimmed = url.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        UserDefaults.standard.set(trimmed, forKey: Self.serverURLKey)
    }

    var authToken: String? = nil

    /// `var` only so unit tests can swap in a stub-protocol session (AuthRequestTests).
    var session: URLSession

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30   // was 1200 — connection-tied; v2 engine runs server-side
        config.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: config)
    }

    private var currentUserId: Int? {
        guard let data = UserDefaults.standard.data(forKey: "nivesh_user_v1"),
              let user = try? JSONDecoder().decode(LoggedInUser.self, from: data) else { return nil }
        return user.userId
    }

    // MARK: - Input Sanitization (Fixes 3.4, 3.6, 3.26, 3.28, 3.29)

    /// Fix 3.4+3.6: Sanitize ticker input — strip SQL injection chars, emoji, enforce max length.
    private func sanitizeTicker(_ raw: String) -> String {
        var cleaned = raw.uppercased()
        let forbiddenChars = CharacterSet(charactersIn: "$;-%'\"").union(.symbols)
        cleaned = cleaned.unicodeScalars
            .filter { !forbiddenChars.contains($0) && $0.properties.generalCategory != .otherSymbol }
            .map { String($0) }.joined()
        return String(cleaned.prefix(20))
    }

    /// Fix 3.26: Strip exchange suffix (.NS, .BO) for endpoints requiring separate params.
    private func stripExchangeSuffix(_ ticker: String) -> String {
        return ticker.replacingOccurrences(of: ".NS", with: "")
                     .replacingOccurrences(of: ".BO", with: "")
    }

    /// Fix 3.28: Validate JWT has three-part header.payload.signature format.
    private func isJWTFormatValid(_ token: String) -> Bool {
        let parts = token.components(separatedBy: ".")
        return parts.count == 3 && parts.allSatisfy { !$0.isEmpty }
    }

    /// Fix 3.29: Route all-numeric tickers as BSE codes. Reject single-digit noise.
    private func classifyNumericInput(_ raw: String) -> String? {
        let digits = raw.filter { $0.isNumber }
        guard digits == raw, !raw.isEmpty else { return nil }
        if raw.count >= 5 { return "BSE" }
        return nil
    }

    /// Fix 3.14: Format date as IST string (India Standard Time, +05:30).
    /// All calendar/earnings queries must use IST before encoding into backend params.
    static func istDateString(from date: Date = Date()) -> String {
        let fmt = DateFormatter()
        fmt.timeZone = TimeZone(identifier: "Asia/Kolkata")
        fmt.dateFormat = "yyyy-MM-dd"
        return fmt.string(from: date)
    }

    func authRequest(_ url: URL) -> URLRequest {
        var req = URLRequest(url: url)
        if let token = authToken {
            if !isJWTFormatValid(token) {
                print("[NetworkManager] WARNING: JWT format suspicious — attaching anyway")
            }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let corrId = generateCorrelationID(subsystem: "ios")
        req.setValue(corrId, forHTTPHeaderField: "X-Correlation-ID")
        // Lets the backend refuse builds that predate token auth (426 update-required).
        req.setValue(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String, forHTTPHeaderField: "X-App-Version")
        req.setValue(Bundle.main.infoDictionary?["CFBundleVersion"] as? String, forHTTPHeaderField: "X-App-Build")
        return req
    }

    // MARK: - Correlation ID

    /// Generates a unique correlation ID for every outgoing request.
    /// Format: ``nivesh_ios_{subsystem}_{uuid_short}``
    /// Logged to both os_log and print() for Xcode console visibility.
    func generateCorrelationID(subsystem: String) -> String {
        let short = UUID().uuidString.prefix(8)
        let corrId = "nivesh_ios_\(subsystem)_\(short)"
        let logMsg = "[Nivesh] CorrelationID: \(corrId)"
        os_log(.info, "%{public}@", logMsg)
        print(logMsg)
        return corrId
    }

    private func dataWithRetry(for request: URLRequest, retries: Int = 1) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch {
            if (error as NSError).code == -999 && retries > 0 {
                // If it was just a tab-switch cancellation, we still want to finish if possible, 
                // but usually the caller handles the retry logic via .onAppear
                throw error
            }
            throw error
        }
    }

    // MARK: - Auth

    func login(username: String, password: String) async throws -> LoggedInUser {
        guard let url = URL(string: "\(baseURL)/login") else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(LoginRequest(username: username, password: password))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        if http.statusCode == 401 { throw NetworkError.invalidCredentials }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, NetworkError.serverDetail(from: data))
        }
        return try JSONDecoder().decode(LoggedInUser.self, from: data)
    }
    
    private struct RegisterRequest: Encodable {
        let username: String
        let password: String
        let display_name: String
    }

    func register(username: String, password: String, displayName: String) async throws -> LoggedInUser {
        guard let url = URL(string: "\(baseURL)/register") else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(RegisterRequest(username: username, password: password, display_name: displayName))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        // 400 carries the server's reason (duplicate username, password policy).
        if http.statusCode == 400 {
            throw NetworkError.serverError(400, NetworkError.serverDetail(from: data) ?? "That username is taken. Try another.")
        }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, NetworkError.serverDetail(from: data))
        }
        return try JSONDecoder().decode(LoggedInUser.self, from: data)
    }

    // MARK: - v2 Analysis Engine (background job model)

    func startAnalysisJob(ticker: String, exchange: String, userId: Int?, deepScan: Bool = false, scanType: String, language: String? = nil, debateRounds: Int? = nil, riskTolerance: String? = nil) async throws -> StartJobResponse {
        guard let url = URL(string: "\(baseURL)/analyze") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(StartJobRequest(ticker: ticker, exchange: exchange, userId: userId, deepScan: deepScan, scanType: scanType, language: language, debateRounds: debateRounds, riskTolerance: riskTolerance))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        if http.statusCode == 409 {
            // Already running — decode and return the existing job ID
            return try JSONDecoder().decode(StartJobResponse.self, from: data)
        }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, NetworkError.serverDetail(from: data))
        }
        return try JSONDecoder().decode(StartJobResponse.self, from: data)
    }

    func pollJob(jobId: String, userId: Int?) async throws -> JobStatus {
        var urlStr = "\(baseURL)/analyze/job/\(jobId)"
        if let uid = userId { urlStr += "?user_id=\(uid)" }
        guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 10
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, NetworkError.serverDetail(from: data))
        }
        return try JSONDecoder().decode(JobStatus.self, from: data)
    }

    /// Poll a job but return raw dict — no StockAnalysis decode. Resilient to schema changes.
    func pollJobRaw(jobId: String, userId: Int?) async throws -> [String: Any]? {
        var urlStr = "\(baseURL)/analyze/job/\(jobId)"
        if let uid = userId { urlStr += "?user_id=\(uid)" }
        guard let url = URL(string: urlStr) else { return nil }
        var request = authRequest(url)
        request.timeoutInterval = 10
        let (data, _) = try await session.data(for: request)
        return try JSONSerialization.jsonObject(with: data) as? [String: Any]
    }

    func cancelJob(jobId: String, userId: Int?) async throws {
        var urlStr = "\(baseURL)/analyze/\(jobId)/cancel"
        if let uid = userId { urlStr += "?user_id=\(uid)" }
        guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.timeoutInterval = 10
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, String(data: data, encoding: .utf8))
        }
    }

    func getActiveJob(userId: Int) async throws -> JobStatus? {
        guard let url = URL(string: "\(baseURL)/analyze/active?user_id=\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 10
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        guard (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError(http.statusCode, String(data: data, encoding: .utf8))
        }
        let decoder = JSONDecoder()
        // active returns either a JobStatus or {"status":"NONE"}
        if let job = try? decoder.decode(JobStatus.self, from: data), job.ticker != nil || job.jobId != nil {
            return job
        }
        return nil
    }

    // MARK: - Portfolio

    struct TransactionItem: Codable, Identifiable {
        let id: Int
        let ticker: String
        let transactionType: String
        let quantity: Double
        let price: Double
        let fees: Double?
        let date: String?
        let notes: String?

        enum CodingKeys: String, CodingKey {
            case id, ticker, quantity, price, fees, date, notes
            case transactionType = "transaction_type"
        }
    }

    func fetchTransactions(userId: Int, ticker: String) async throws -> [TransactionItem] {
        guard let url = URL(string: "\(baseURL)/portfolio/transactions/\(ticker)?user_id=\(userId)") else {
            throw NetworkError.invalidURL
        }
        let req = authRequest(url)
        let (data, response) = try await dataWithRetry(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        return (try? JSONDecoder().decode([TransactionItem].self, from: data)) ?? []
    }

    private struct PortfolioResponse: Decodable {
        let holdings: [HoldingDTO]
    }
    
    private struct HoldingDTO: Decodable {
        let ticker: String
        let company_name: String
        let shares: Double
        let buy_price: Double
        let current_price: Double
        let day_change_pct: Double?
        let notes: String?
        let purchase_date: String?
        let target_price: Double?
    }

    func fetchMutualFunds() async throws -> [MutualFundDTO] {
        guard let url = URL(string: "\(baseURL)/api/mutual-funds/") else {
            throw NetworkError.invalidURL
        }
        let req = authRequest(url)
        let (data, response) = try await dataWithRetry(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        return (try? JSONDecoder().decode([MutualFundDTO].self, from: data)) ?? []
    }

    func getPortfolio(userId: Int) async throws -> [PortfolioHolding] {
        guard let url = URL(string: "\(baseURL)/portfolio/\(userId)") else { throw NetworkError.invalidURL }
        let req = authRequest(url)
        let (data, response) = try await dataWithRetry(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        
        do {
            let resp = try JSONDecoder().decode(PortfolioResponse.self, from: data)
            return resp.holdings.map { dto in
                let stock = Stock(
                    ticker: dto.ticker,
                    companyName: dto.company_name,
                    exchange: "NSE",
                    currentPrice: dto.current_price,
                    changePercent: dto.day_change_pct ?? 0.0,
                    signal: nil
                )
                return PortfolioHolding(
                    stock: stock,
                    shares: dto.shares,
                    buyPrice: dto.buy_price,
                    purchaseDate: dto.purchase_date,
                    notes: dto.notes,
                    targetPrice: dto.target_price
                )
            }
        } catch {
            print("Decoding error in getPortfolio: \(error)")
            throw NetworkError.decodingError(error.localizedDescription)
        }
    }

    
    func addHolding(userId: Int, ticker: String, companyName: String, shares: Double, buyPrice: Double, purchaseDate: Date, notes: String, targetPrice: Double, transactionType: String = "BUY") async throws {
        struct Req: Encodable {
            let user_id: Int; let ticker: String; let exchange: String; let company_name: String; let shares: Double; let buy_price: Double
            let group_name: String; let purchase_date: String; let notes: String; let target_price: Double; let transaction_type: String
        }
        guard let url = URL(string: "\(baseURL)/portfolio") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let formatter = DateFormatter()
        formatter.dateFormat = "dd-MMM-yyyy"
        let body = Req(
            user_id: userId, ticker: ticker, exchange: "NSE", company_name: companyName, shares: shares, buy_price: buyPrice,
            group_name: "holdings", purchase_date: formatter.string(from: purchaseDate), notes: notes, target_price: targetPrice,
            transaction_type: transactionType.uppercased()
        )
        request.httpBody = try JSONEncoder().encode(body)
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
    }

    func saveNote(userId: Int, ticker: String, note: String) async throws {
        struct Req: Encodable { let user_id: Int; let ticker: String; let note: String }
        guard let url = URL(string: "\(baseURL)/portfolio/note") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, note: note))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
    }

    // MARK: - Morning Summary

    func getMorningSummary(userId: Int) async throws -> MorningSummaryResponse {
        guard let url = URL(string: "\(baseURL)/morning-summary/\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 30
        request.cachePolicy = .reloadIgnoringLocalCacheData
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        if http.statusCode == 401 { throw NetworkError.unauthorized }
        guard (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do {
            return try JSONDecoder().decode(MorningSummaryResponse.self, from: data)
        } catch {
            print("[MorningBrief] Decode error: \(error)")
            if let jsonString = String(data: data, encoding: .utf8) {
                print("[MorningBrief] Payload: \(jsonString)")
            }
            throw NetworkError.invalidResponse
        }
    }

    // MARK: - Market Indices

    func getMarketIndices() async throws -> MarketIndicesResponse {
        guard let url = URL(string: "\(baseURL)/market-indices") else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        return try JSONDecoder().decode(MarketIndicesResponse.self, from: data)
    }

    // MARK: - Watchlist

    func addToWatchlist(userId: Int, ticker: String, exchange: String, companyName: String) async throws -> Bool {
        struct Req: Encodable { let user_id: Int; let ticker: String; let exchange: String; let company_name: String }
        struct Resp: Decodable { let already_exists: Bool?; let success: Bool? }
        guard let url = URL(string: "\(baseURL)/watchlist/add") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, exchange: exchange, company_name: companyName))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        let resp = try JSONDecoder().decode(Resp.self, from: data)
        return resp.success == true
    }

    func removeFromWatchlist(userId: Int, ticker: String) async throws {
        struct Req: Encodable { let user_id: Int; let ticker: String }
        guard let url = URL(string: "\(baseURL)/watchlist/remove") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    func getWatchlist(userId: Int) async throws -> [WatchlistItem] {
        guard let url = URL(string: "\(baseURL)/watchlist/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 15
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        if http.statusCode == 401 { throw NetworkError.unauthorized }
        guard (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        struct Resp: Decodable { let watchlist: [WatchlistItem] }
        let decoded = try JSONDecoder().decode(Resp.self, from: data)
        return decoded.watchlist
    }

    // MARK: - Portfolio Management

    func removeHolding(userId: Int, ticker: String) async throws {
        struct Req: Encodable { let user_id: Int; let ticker: String }
        guard let url = URL(string: "\(baseURL)/portfolio/remove") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    func updateHolding(userId: Int, ticker: String, shares: Double, buyPrice: Double) async throws {
        struct Req: Encodable { let user_id: Int; let ticker: String; let shares: Double; let buy_price: Double }
        guard let url = URL(string: "\(baseURL)/portfolio/update") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, shares: shares, buy_price: buyPrice))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    // MARK: - Price Alerts

    func addAlert(userId: Int, ticker: String, targetPrice: Double, direction: String, companyName: String) async throws -> Int {
        struct Req: Encodable { let user_id: Int; let ticker: String; let target_price: Double; let direction: String; let company_name: String }
        struct Resp: Decodable { let alert_id: Int }
        guard let url = URL(string: "\(baseURL)/alerts/add") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, target_price: targetPrice, direction: direction, company_name: companyName))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return (try? JSONDecoder().decode(Resp.self, from: data))?.alert_id ?? 0
    }

    func getAlerts(userId: Int) async throws -> [PriceAlert] {
        guard let url = URL(string: "\(baseURL)/alerts/\(userId)") else { throw NetworkError.invalidURL }
        let request = authRequest(url)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return (try? JSONDecoder().decode(AlertsResponse.self, from: data))?.alerts ?? []
    }

    func removeAlert(userId: Int, alertId: Int) async throws {
        struct Req: Encodable { let user_id: Int; let alert_id: Int }
        guard let url = URL(string: "\(baseURL)/alerts/remove") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, alert_id: alertId))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    func checkAlerts(userId: Int) async throws -> [TriggeredAlert] {
        guard let url = URL(string: "\(baseURL)/alerts/check/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 20
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return (try? JSONDecoder().decode(AlertCheckResponse.self, from: data))?.newlyTriggered ?? []
    }

    // MARK: - Sector Performance

    func getSectorPerformance() async throws -> [SectorPerformance] {
        guard let url = URL(string: "\(baseURL)/sector-performance") else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        struct Resp: Decodable { let sectors: [SectorPerformance] }
        return (try? JSONDecoder().decode(Resp.self, from: data))?.sectors ?? []
    }

    // MARK: - Excel Export

    func exportPortfolioExcel(userId: Int) async throws -> Data {
        guard let url = URL(string: "\(baseURL)/portfolio/export/excel/\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 30
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.serverError((response as? HTTPURLResponse)?.statusCode ?? 500, "Export failed")
        }
        return data
    }

    func exportPortfolioPDF(userId: Int) async throws -> URL {
        guard let url = URL(string: "\(baseURL)/portfolio/export/pdf/\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.timeoutInterval = 30
        let (tempURL, response) = try await session.download(for: request)
        do {
            try Self.requirePDFResponse(response)
        } catch {
            try? FileManager.default.removeItem(at: tempURL)
            throw error
        }
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        let pdfURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("portfolio_summary_\(formatter.string(from: Date())).pdf")
        try? FileManager.default.removeItem(at: pdfURL)
        try FileManager.default.moveItem(at: tempURL, to: pdfURL)
        return pdfURL
    }

    /// Throws unless the response is HTTP 2xx with a PDF body.
    nonisolated static func requirePDFResponse(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse,
              (200...299).contains(http.statusCode),
              http.mimeType == "application/pdf" else {
            let status = (response as? HTTPURLResponse)?.statusCode ?? -1
            throw NetworkError.serverError(status, "Couldn't create the PDF. Please try again.")
        }
    }

    func fetchBenchmark(userId: Int) async throws -> BenchmarkData {
        let endpoint = "/portfolio/benchmark?user_id=\(userId)"
        let data = try await _fetchDecode(BenchmarkData.self, endpoint: endpoint)
        return data
    }

    // MARK: - Nifty History

    func getNiftyHistory(days: Int = 365) async -> [NiftyPricePoint] {
        guard let url = URL(string: "\(baseURL)/nifty-history?days=\(days)") else { return [] }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return [] }
        struct Resp: Decodable { let prices: [NiftyPricePoint] }
        return (try? JSONDecoder().decode(Resp.self, from: data))?.prices ?? []
    }

    // MARK: - Quarterly Financials

    func getQuarterlyFinancialsResponse(ticker: String, exchange: String = "NSE") async -> QuarterlyFinancialsResponse? {
        guard let url = URL(string: "\(baseURL)/quarterly-financials?ticker=\(ticker)&exchange=\(exchange)") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        if let result = try? JSONDecoder().decode(QuarterlyFinancialsResponse.self, from: data) { return result }
        // Fallback: backend might return old format without promoter_history
        struct OldResp: Decodable { let quarters: [QuarterlyFinancial] }
        if let old = try? JSONDecoder().decode(OldResp.self, from: data) {
            return QuarterlyFinancialsResponse(quarters: old.quarters, promoterHistory: [])
        }
        return nil
    }

    func getQuarterlyFinancials(ticker: String, exchange: String = "NSE") async -> [QuarterlyFinancial] {
        await getQuarterlyFinancialsResponse(ticker: ticker, exchange: exchange)?.quarters ?? []
    }

    // MARK: - Earnings Calendar

    func getEarningsCalendar() async -> [EarningsEvent] {
        guard let url = URL(string: "\(baseURL)/earnings-calendar") else { return [] }
        var request = URLRequest(url: url)
        request.timeoutInterval = 30
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return [] }
        struct Resp: Decodable { let events: [EarningsEvent] }
        return (try? JSONDecoder().decode(Resp.self, from: data))?.events ?? []
    }

    // MARK: - Macro Strip

    func getMacroStrip() async -> MacroStrip? {
        guard let url = URL(string: "\(baseURL)/macro-strip") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 8
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(MacroStrip.self, from: data)
    }

    // MARK: - Analyst Ratings

    func getAnalystRatings(ticker: String, exchange: String = "NSE") async -> AnalystRatingsResponse? {
        guard let url = URL(string: "\(baseURL)/analyst-ratings?ticker=\(ticker)&exchange=\(exchange)") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 12
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(AnalystRatingsResponse.self, from: data)
    }

    // MARK: - Signal Warnings

    func getSignalWarnings(userId: Int) async -> [SignalWarning] {
        guard let url = URL(string: "\(baseURL)/portfolio/signal-warnings?user_id=\(userId)") else { return [] }
        var request = authRequest(url)
        request.timeoutInterval = 10
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return [] }
        return (try? JSONDecoder().decode(SignalWarningsResponse.self, from: data))?.warnings ?? []
    }

    // MARK: - Health

    func checkHealth() async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/health") else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.timeoutInterval = 5
        let (_, response) = try await session.data(for: request)
        return (response as? HTTPURLResponse)?.statusCode == 200
    }

    // MARK: - Quick Info

    func quickInfo(ticker: String, exchange: String = "NSE") async -> QuickInfo? {
        guard let url = URL(string: "\(baseURL)/quick-info?ticker=\(ticker)&exchange=\(exchange)") else { return nil }
        var request = URLRequest(url: url)
        request.timeoutInterval = 10
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(QuickInfo.self, from: data)
    }

    // MARK: - Stock OHLCV History

    func fetchStockHistory(ticker: String, exchange: String = "NSE", period: String = "1y") async -> StockHistoryResponse? {
        guard let encoded = ticker.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(baseURL)/api/v1/market/stock-history?ticker=\(encoded)&exchange=\(exchange)&period=\(period)") else {
            print("[fetchStockHistory] Invalid URL for ticker=\(ticker) exchange=\(exchange)")
            return nil
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        do {
            let (data, resp) = try await session.data(for: request)
            guard let http = resp as? HTTPURLResponse else {
                print("[fetchStockHistory] Non-HTTP response for \(ticker)")
                return nil
            }
            guard http.statusCode == 200 else {
                let body = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                print("[fetchStockHistory] HTTP \(http.statusCode) for \(ticker): \(body)")
                return nil
            }
            do {
                if let array = try? JSONDecoder().decode([OHLCVPoint].self, from: data) {
                    return StockHistoryResponse(ticker: ticker, exchange: exchange, period: period, prices: array)
                }
                return try JSONDecoder().decode(StockHistoryResponse.self, from: data)
            } catch {
                let body = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
                print("[fetchStockHistory] Decode error for \(ticker): \(error.localizedDescription) — body: \(body)")
                return nil
            }
        } catch {
            let ns = error as NSError
            print("[fetchStockHistory] Network error for \(ticker): domain=\(ns.domain) code=\(ns.code) desc=\(ns.localizedDescription)")
            return nil
        }
    }

    // MARK: - Unified Stock Profile

    func fetchStockProfile(ticker: String, exchange: String = "NSE") async throws -> StockProfileResponse {
        let endpoint = "/api/v1/stock-profile?ticker=\(ticker)&exchange=\(exchange)"
        guard let encoded = ticker.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(baseURL)\(endpoint)") else {
            print("[fetchStockProfile] Invalid URL: \(baseURL)\(endpoint)")
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            let ns = error as NSError
            print("[fetchStockProfile] Network error for \(ticker): domain=\(ns.domain) code=\(ns.code) desc=\(ns.localizedDescription)")
            throw NetworkError.fetchFailed(endpoint: endpoint, status: -1, body: "domain=\(ns.domain) code=\(ns.code) desc=\(ns.localizedDescription)")
        }
        guard let http = response as? HTTPURLResponse else {
            print("[fetchStockProfile] Non-HTTP response for \(ticker)")
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Non-HTTP response")
        }
        guard http.statusCode == 200 else {
            let body = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
            print("[fetchStockProfile] HTTP \(http.statusCode) for \(ticker): \(body)")
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(body))
        }
        do {
            return try JSONDecoder().decode(StockProfileResponse.self, from: data)
        } catch {
            let body = String(data: data, encoding: .utf8)?.prefix(500) ?? "<non-utf8>"
            print("[fetchStockProfile] Decode error for \(ticker): \(error.localizedDescription) — body: \(body)")
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: "Decode: \(error.localizedDescription)")
        }
    }

    // MARK: - Dividends

    func fetchDividends(ticker: String, exchange: String = "NSE") async throws -> DividendData {
        let endpoint = "/dividends/\(ticker.uppercased())?exchange=\(exchange)"
        let data = try await _fetchDecode(DividendData.self, endpoint: endpoint)
        return data
    }

    // MARK: - Sentiment Trend

    func fetchSentimentTrend(ticker: String, days: Int = 30) async throws -> SentimentTrend {
        let endpoint = "/market/sentiment-trend/\(ticker.uppercased())?days=\(days)"
        let data = try await _fetchDecode(SentimentTrend.self, endpoint: endpoint)
        return data
    }

    // MARK: - Piotroski F-Score

    func fetchPiotroski(ticker: String) async -> PiotroskiData? {
        guard let encoded = ticker.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed),
              let url = URL(string: "\(baseURL)/fundamentals/piotroski/\(encoded)") else { return nil }
        var request = authRequest(url)
        request.timeoutInterval = 12
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(PiotroskiData.self, from: data)
    }

    // MARK: - Fundamentals v1

    func fetchFinancials(
        symbol: String,
        exchange: String = "NSE",
        periodType: String = "quarterly",
        consolidation: String = "standalone",
        periods: Int = 8
    ) async throws -> FinancialStatementResponse {
        return try await _fetchDecode(
            FinancialStatementResponse.self,
            endpoint: "/api/v1/fundamentals/financials?ticker=\(symbol)&exchange=\(exchange)&period_type=\(periodType)&consolidation=\(consolidation)&periods=\(periods)",
            timeout: 20
        )
    }

    func fetchShareholding(symbol: String, exchange: String = "NSE") async throws -> ShareholdingResponse {
        return try await _fetchDecode(
            ShareholdingResponse.self,
            endpoint: "/api/v1/fundamentals/shareholding?ticker=\(symbol)&exchange=\(exchange)",
            timeout: 20
        )
    }

    func fetchCorporateActions(symbol: String, exchange: String = "NSE") async throws -> CorporateActionsResponse {
        return try await _fetchDecode(
            CorporateActionsResponse.self,
            endpoint: "/api/v1/fundamentals/corporate-actions?ticker=\(symbol)&exchange=\(exchange)",
            timeout: 20
        )
    }

    func fetchValuation(symbol: String, exchange: String = "NSE") async throws -> ValuationResponse {
        return try await _fetchDecode(
            ValuationResponse.self,
            endpoint: "/api/v1/fundamentals/valuation?ticker=\(symbol)&exchange=\(exchange)",
            timeout: 20
        )
    }

    func fetchRiskSignals(symbol: String, exchange: String = "NSE") async throws -> RiskSignalsResponse {
        return try await _fetchDecode(
            RiskSignalsResponse.self,
            endpoint: "/api/v1/fundamentals/risk-signals?ticker=\(symbol)&exchange=\(exchange)",
            timeout: 20
        )
    }

    // MARK: - Search

    func searchStocks(q: String) async -> [StockEntry] {
        guard !q.isEmpty,
              let encoded = q.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed),
              let url = URL(string: "\(baseURL)/api/v1/search?query=\(encoded)") else { return [] }
        var request = authRequest(url)
        request.timeoutInterval = 5
        guard let (data, resp) = try? await session.data(for: request),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return [] }
        struct SearchResult: Decodable {
            let ticker: String
            let company_name: String
            let sector: String
            let exchange: String
        }
        guard let results = try? JSONDecoder().decode([SearchResult].self, from: data) else { return [] }
        return results.map { StockEntry(ticker: $0.ticker, companyName: $0.company_name, exchange: $0.exchange, sector: $0.sector) }
    }

    // MARK: - Risk Analysis

    func fetchRiskAnalysis(userId: Int) async throws -> RiskAnalysis {
        guard let url = URL(string: "\(baseURL)/portfolio/risk-analysis/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 30
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(RiskAnalysis.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    func fetchRedFlags(userId: Int) async throws -> RedFlagsResponse {
        guard let url = URL(string: "\(baseURL)/portfolio/red-flags/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 30
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(RedFlagsResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    func fetchMacroImpact(userId: Int) async throws -> MacroImpactResponse {
        guard let url = URL(string: "\(baseURL)/macro-impact/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 30
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(MacroImpactResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Home Feed

    func fetchHomeFeed(userId: Int) async throws -> HomeFeedResponse {
        let endpoint = "/api/v1/home-feed?user_id=\(userId)"
        return try await _fetchDecode(HomeFeedResponse.self, endpoint: endpoint)
    }

    func fetchDailyAction(userId: Int) async -> DailyActionResponse? {
        guard let url = URL(string: "\(baseURL)/daily-action/\(userId)") else { return nil }
        var req = authRequest(url)
        req.timeoutInterval = 15
        guard let (data, resp) = try? await session.data(for: req),
              let http = resp as? HTTPURLResponse, http.statusCode == 200 else { return nil }
        return try? JSONDecoder().decode(DailyActionResponse.self, from: data)
    }

    // MARK: - Push Notifications

    func registerDeviceToken(token: String) async throws {
        guard let userId = currentUserId else { return }
        struct Req: Encodable { let user_id: Int; let device_token: String; let platform: String }
        guard let url = URL(string: "\(baseURL)/notifications/register-device") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, device_token: token, platform: "ios"))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    struct NotificationPayload: Decodable {
        let title: String
        let body: String
        let data: [String: String]?
    }

    func sendTestNotification(ticker: String, exchange: String) async throws -> NotificationPayload {
        guard let userId = currentUserId else { throw NetworkError.invalidURL }
        struct Req: Encodable { let user_id: Int; let ticker: String; let exchange: String }
        guard let url = URL(string: "\(baseURL)/notifications/test") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, exchange: exchange))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return try JSONDecoder().decode(NotificationPayload.self, from: data)
    }

    func sendMorningSummaryNotification() async throws -> NotificationPayload {
        guard let userId = currentUserId else { throw NetworkError.invalidURL }
        struct Req: Encodable { let user_id: Int }
        guard let url = URL(string: "\(baseURL)/notifications/morning-summary-push") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return try JSONDecoder().decode(NotificationPayload.self, from: data)
    }

    struct HarvestYouTubeResponse: Decodable {
        let channel_harvest: HarvestResult
        let portfolio_harvest: HarvestResult
    }

    struct HarvestResult: Decodable {
        let channels_processed: Int?
        let total_channels: Int?
        let videos_added: Int?
        let tickers_processed: Int?
        let by_ticker: [String: Int]?
    }

    func triggerYouTubeHarvest() async throws -> HarvestYouTubeResponse {
        guard let url = URL(string: "\(baseURL)/api/v1/admin/harvest-youtube") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        return try JSONDecoder().decode(HarvestYouTubeResponse.self, from: data)
    }

    func scheduleLocalNotification(title: String, body: String, userInfo: [String: Any]) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            guard settings.authorizationStatus == .authorized else { return }
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            content.userInfo = userInfo
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
            let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: trigger)
            UNUserNotificationCenter.current().add(request)
        }
    }

    func fetchTimeframeConflicts(userId: Int) async throws -> TimeframeConflictsResponse {
        guard let url = URL(string: "\(baseURL)/portfolio/timeframe-conflicts/\(userId)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 15
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(TimeframeConflictsResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    func fetchScreener(preset: String) async throws -> [ScreenerResult] {
        guard let url = URL(string: "\(baseURL)/screener?preset=\(preset)") else { throw NetworkError.invalidURL }
        var req = URLRequest(url: url)
        req.timeoutInterval = 20
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode([ScreenerResult].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Trade Journal

    func fetchTradeJournal(userId: Int) async throws -> [TradeJournalEntry] {
        guard let url = URL(string: "\(baseURL)/trade-journal/\(userId)") else { throw NetworkError.invalidURL }
        let request = authRequest(url)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do {
            let resp = try JSONDecoder().decode(TradeJournalResponse.self, from: data)
            return resp.entries
        } catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    func addTradeJournalEntry(userId: Int, ticker: String, companyName: String?, action: String, price: Double, reason: String, mood: String?) async throws -> TradeJournalEntry {
        struct Req: Encodable {
            let user_id: Int; let ticker: String; let company_name: String?
            let action: String; let price_at_time: Double; let reason_text: String; let mood: String?
        }
        guard let url = URL(string: "\(baseURL)/trade-journal") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, company_name: companyName, action: action, price_at_time: price, reason_text: reason, mood: mood))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        // The POST returns {success, entry_id, ticker, action} — fetch the full entry after
        // Construct a minimal entry from the response
        struct AddResp: Decodable { let entry_id: Int; let ticker: String; let action: String }
        let resp = try JSONDecoder().decode(AddResp.self, from: data)
        return TradeJournalEntry(id: resp.entry_id, ticker: resp.ticker, companyName: companyName, action: resp.action, priceAtTime: price, reasonText: reason, outcomeText: nil, mood: mood, createdAt: nil)
    }

    func updateTradeJournalOutcome(entryId: Int, userId: Int, outcomeText: String, mood: String?) async throws {
        struct Req: Encodable { let outcome_text: String; let mood: String? }
        guard let url = URL(string: "\(baseURL)/trade-journal/\(entryId)?user_id=\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(outcome_text: outcomeText, mood: mood))
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    func deleteTradeJournalEntry(entryId: Int, userId: Int) async throws {
        guard let url = URL(string: "\(baseURL)/trade-journal/\(entryId)?user_id=\(userId)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = "DELETE"
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
    }

    func fetchTradeJournalStats(userId: Int) async throws -> TradeJournalStatsResponse {
        guard let url = URL(string: "\(baseURL)/trade-journal/\(userId)/stats") else { throw NetworkError.invalidURL }
        let request = authRequest(url)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(TradeJournalStatsResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Earnings Dashboard (Sections 1–5)

    // MARK: - Diagnostic fetch helper

    /// Shared fetch + decode with detailed error diagnostics.
    /// Never returns nil/empty silently — errors are thrown with exact endpoint/status/body.
    func _fetchDecode<T: Decodable>(
        _ type: T.Type, endpoint: String, timeout: TimeInterval = 15
    ) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            let err = NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL: \(baseURL)\(endpoint)")
            GlobalErrorDiagnoser.shared.trackNetworkError(err, endpoint: endpoint)
            throw err
        }
        var req = authRequest(url)
        req.timeoutInterval = timeout
        let data: Data, response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            let body = (error as NSError).localizedDescription
            let err = NetworkError.fetchFailed(endpoint: endpoint, status: -1, body: "Network error: \(body)")
            GlobalErrorDiagnoser.shared.trackNetworkError(err, endpoint: endpoint)
            throw err
        }
        guard let http = response as? HTTPURLResponse else {
            let err = NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not an HTTP response")
            GlobalErrorDiagnoser.shared.trackNetworkError(err, endpoint: endpoint)
            throw err
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            let err = NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(body))
            GlobalErrorDiagnoser.shared.trackNetworkError(err, endpoint: endpoint)
            throw err
        }
        do {
            return try JSONDecoder().decode(type, from: data)
        } catch {
            let rawStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<non-utf8>"
            let keys = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]).map { Array($0.keys).joined(separator: ", ") } ?? "?"
            let err = NetworkError.decodingError("\(error.localizedDescription) | Raw keys: \(keys) | Body: \(rawStr)")
            GlobalErrorDiagnoser.shared.trackNetworkError(err, endpoint: endpoint)
            throw err
        }
    }

    // MARK: - Earnings Intelligence

    func fetchEarningsProgress() async throws -> EarningsProgressResponse {
        return try await _fetchDecode(EarningsProgressResponse.self, endpoint: "/api/v1/earnings/progress")
    }

    func fetchEarningsFeed(marketCap: String = "all", sort: String = "latest") async throws -> [EarningsResult] {
        let resp: EarningsFeedResponse = try await _fetchDecode(
            EarningsFeedResponse.self,
            endpoint: "/api/v1/earnings/feed?market_cap=\(marketCap)&sort=\(sort)",
            timeout: 20
        )
        return resp.results
    }

    func fetchEarningsCalendarDay(date: String) async throws -> [EarningsResult] {
        struct Resp: Decodable { let results: [EarningsResult] }
        let r = try await _fetchDecode(Resp.self, endpoint: "/api/v1/earnings/calendar?date=\(date)")
        return r.results
    }

    func fetchEarningsEstimates(ticker: String) async throws -> EarningsEstimate {
        return try await _fetchDecode(EarningsEstimate.self, endpoint: "/api/v1/earnings/estimates?ticker=\(ticker)")
    }

    func fetchPostResultMovers() async throws -> [PostResultMover] {
        let resp: PostResultMoversResponse = try await _fetchDecode(
            PostResultMoversResponse.self, endpoint: "/api/v1/earnings/post-result-movers"
        )
        return resp.movers
    }

    func setEarningsAlert(userId: Int, ticker: String, date: String) async throws {
        struct Req: Encodable { let user_id: Int; let ticker: String; let earnings_date: String }
        struct Resp: Decodable { let status: String?; let id: Int? }
        guard let url = URL(string: "\(baseURL)/api/v1/earnings/alerts") else {
            throw NetworkError.fetchFailed(endpoint: "/api/v1/earnings/alerts", status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(user_id: userId, ticker: ticker, earnings_date: date))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: "/api/v1/earnings/alerts", status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: "/api/v1/earnings/alerts", status: http.statusCode, body: String(body))
        }
        // Success — log the created alert ID for debugging
        if let resp = try? JSONDecoder().decode(Resp.self, from: data), let id = resp.id {
            print("[Nivesh] Earnings alert created: id=\(id), ticker=\(ticker), date=\(date)")
        }
    }

    // MARK: - Portfolio Charts

    func fetchPortfolioCharts(userId: Int) async throws -> PortfolioChartsResponse {
        guard let url = URL(string: "\(baseURL)/api/v1/portfolio/charts/\(userId)") else {
            throw NetworkError.fetchFailed(endpoint: "/api/v1/portfolio/charts/\(userId)", status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.timeoutInterval = 90  // chart generation can take 30-60s for large portfolios
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let body = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: "/api/v1/portfolio/charts/\(userId)", status: (response as? HTTPURLResponse)?.statusCode ?? 0, body: String(body))
        }
        do {
            return try JSONDecoder().decode(PortfolioChartsResponse.self, from: data)
        } catch {
            throw NetworkError.decodingError(error.localizedDescription)
        }
    }

    // MARK: - Advisor Intelligence

    func fetchAdvisoryConsensus(userId: Int) async throws -> AdvisoryConsensusResponse {
        guard let url = URL(string: "\(baseURL)/api/v1/portfolio/advisor-consensus?user_id=\(userId)&days=7") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.timeoutInterval = 30
        let (data, response) = try await dataWithRetry(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else { throw NetworkError.invalidResponse }
        do { return try JSONDecoder().decode(AdvisoryConsensusResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Portfolio Valuation History

    func fetchValuationHistory(userId: Int, days: Int = 90) async throws -> ValuationHistoryResponse {
        guard let url = URL(string: "\(baseURL)/api/v1/portfolio/valuation-history?user_id=\(userId)&days=\(days)") else {
            throw NetworkError.invalidURL
        }
        var req = authRequest(url)
        req.timeoutInterval = 30
        let (data, response) = try await dataWithRetry(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
        do { return try JSONDecoder().decode(ValuationHistoryResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Macro Context

    func fetchMacroContext(ticker: String, exchange: String = "NSE", sector: String = "") async -> MacroContextData? {
        var components = URLComponents(string: "\(baseURL)/macro-context/\(ticker)")!
        components.queryItems = [
            URLQueryItem(name: "exchange", value: exchange),
            URLQueryItem(name: "sector", value: sector),
        ]
        guard let url = components.url else { return nil }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return try JSONDecoder().decode(MacroContextData.self, from: data)
        } catch {
            print("[MacroContext] Fetch failed: \(error)")
            return nil
        }
    }

    // MARK: - Options Strategy

    func getOptionsPayoff(spotPrice: Double, legs: [OptionLeg]) async throws -> OptionsPayoffResponse {
        let endpoint = "/api/v1/options/payoff"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15

        let body = OptionsPayoffRequest(spotPrice: spotPrice, legs: legs)
        request.httpBody = try JSONEncoder().encode(body)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        return try JSONDecoder().decode(OptionsPayoffResponse.self, from: data)
    }

    // MARK: - IPO Hub
    //
    // Endpoints match backend/routers/ipo.py exactly: GET /api/ipo (list, optional
    // ?status=), GET /api/ipo/{id}, GET /api/ipo/{id}/subscription-status,
    // GET /api/ipo/calendar. The backend returns plain JSON arrays (no envelope)
    // and has no server-side month filter on /calendar — filtering by month is
    // done client-side using the already-fetched list.

    /// Fetches the IPO list, optionally filtered by status (open/upcoming/closed/listed).
    func getIPOList(status: IPOStatus? = nil) async throws -> [IPOListing] {
        var endpoint = "/api/ipo"
        if let status { endpoint += "?status=\(status.rawValue)" }
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([IPOListing].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches full detail (price band, lot size, issue size, GMP, dates) for a single IPO.
    func getIPODetail(id: String) async throws -> IPOListing {
        let endpoint = "/api/ipo/\(id)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(IPOListing.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches live subscription status (times subscribed per category) for a single IPO.
    func getIPOSubscription(id: String) async throws -> IPOSubscriptionDetail {
        let endpoint = "/api/ipo/\(id)/subscription-status"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(IPOSubscriptionDetail.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches all IPOs for the calendar view. The backend endpoint has no server-side
    /// month filter (kept for backward compatibility, see routers/ipo.py), so callers
    /// filter the returned list to the month they need.
    func getIPOCalendar() async throws -> [IPOListing] {
        let endpoint = "/api/ipo/calendar"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([IPOListing].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

}

// MARK: - Community Forum
//
// Endpoints match backend/routers/forum.py exactly (prefix /api/forum):
// GET /boards (list), GET /boards/{board_id}/threads (list),
// GET /threads/{thread_id} (detail), POST /threads (create, auth),
// POST /threads/{thread_id}/posts (reply, auth), POST /posts/{post_id}/vote
// (auth), POST /polls/{poll_id}/vote (auth). The backend returns plain JSON
// (no envelope). Mutating calls use `authRequest(_:)` so the Bearer token is
// attached automatically.

extension NetworkManager {

    /// Fetches all discussion boards (general market + per-stock boards).
    func getForumBoards() async throws -> [ForumBoard] {
        let endpoint = "/api/forum/boards"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([ForumBoard].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches thread summaries for a single board.
    func getForumThreads(boardId: Int) async throws -> [ForumThreadSummary] {
        let endpoint = "/api/forum/boards/\(boardId)/threads"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([ForumThreadSummary].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches a thread with all its posts and poll (if any).
    func getForumThreadDetail(threadId: Int) async throws -> ForumThreadDetail {
        let endpoint = "/api/forum/threads/\(threadId)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ForumThreadDetail.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Creates a new thread (with opening post, and optional poll) on a board. Requires auth.
    func createForumThread(boardId: Int, title: String, body: String, pollQuestion: String? = nil, pollOptions: [String]? = nil) async throws -> ForumThreadDetail {
        struct Req: Encodable {
            let board_id: Int
            let title: String
            let body: String
            let poll_question: String?
            let poll_options: [String]?
        }
        let endpoint = "/api/forum/threads"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(board_id: boardId, title: title, body: body, poll_question: pollQuestion, poll_options: pollOptions))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ForumThreadDetail.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Replies to a thread, optionally nested under a parent post. Requires auth.
    func createForumPost(threadId: Int, body: String, parentPostId: Int? = nil) async throws -> ForumPost {
        struct Req: Encodable {
            let body: String
            let parent_post_id: Int?
        }
        let endpoint = "/api/forum/threads/\(threadId)/posts"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(body: body, parent_post_id: parentPostId))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ForumPost.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Upvotes/downvotes a post. Re-voting the same direction removes the vote server-side. Requires auth.
    func voteForumPost(postId: Int, direction: String) async throws -> ForumVoteResult {
        struct Req: Encodable { let direction: String }
        let endpoint = "/api/forum/posts/\(postId)/vote"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(direction: direction))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ForumVoteResult.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Casts (or moves) a user's single vote on a poll. Requires auth.
    func voteForumPoll(pollId: Int, optionId: Int) async throws -> ForumPoll {
        struct Req: Encodable { let option_id: Int }
        let endpoint = "/api/forum/polls/\(pollId)/vote"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(Req(option_id: optionId))

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ForumPoll.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}

// MARK: - Mutual Fund Hub
//
// Endpoints match backend/routers/mutual_funds.py (prefix /api/mutual-funds).
// GET / (list — see fetchMutualFunds() above for the original minimal-shape
// caller), GET /{scheme_code} (detail), GET /{scheme_code}/nav-history?days=
// (NAV history for the chart). The backend paths key off `scheme_code`
// (a string, e.g. "INF209K01157"), NOT the integer `id` — do not pass the
// row id in the URL path. There is NO /holdings or /sip-calculator endpoint
// on the backend as of this writing — those calls below will 404; callers
// fall back gracefully (nav-history/holdings render empty state,
// sip-calculator computes locally via SIPCalculationResult.computeLocally)
// so the UI works before and after a future backend pass adds them.

extension NetworkManager {

    /// Fetches full detail for a single mutual fund scheme, keyed by scheme_code.
    func getMutualFundDetail(schemeCode: String) async throws -> MutualFundDTO {
        let endpoint = "/api/mutual-funds/\(schemeCode)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(MutualFundDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches NAV history points for the fund's chart, trimmed server-side to `range`.
    func getMutualFundNAVHistory(schemeCode: String, range: MutualFundNAVRange) async throws -> [MutualFundNAVPoint] {
        // Backend takes `days` (1-365), not a named range — translate here.
        let days = min(range.approxDays, 365)
        let endpoint = "/api/mutual-funds/\(schemeCode)/nav-history?days=\(days)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([MutualFundNAVPoint].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches the fund's top portfolio holdings. NOTE: no backend route
    /// exists for this yet (see file header) — always 404s today.
    func getMutualFundHoldings(schemeCode: String) async throws -> [MutualFundHolding] {
        let endpoint = "/api/mutual-funds/\(schemeCode)/holdings"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([MutualFundHolding].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Requests a SIP projection from the backend calculator. Throws if the
    /// endpoint isn't live yet — callers should fall back to
    /// `SIPCalculationResult.computeLocally`.
    func calculateSIP(monthlyAmount: Double, annualReturnPct: Double, years: Double) async throws -> SIPCalculationResult {
        let endpoint = "/api/mutual-funds/sip-calculator"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        let body = SIPCalculationRequest(monthlyAmount: monthlyAmount, annualReturnPct: annualReturnPct, years: years)
        request.httpBody = try? JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(SIPCalculationResult.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}

// MARK: - Harvester API (Market Intelligence — merged into port 8000)

extension NetworkManager {
    /// Harvester endpoints are now served by the main backend on port 8000.
    var harvesterBaseURL: String { baseURL }

    func fetchHarvesterFeed(ticker: String? = nil, limit: Int = 20) async throws -> HarvesterFeedResponse {
        var urlStr = "\(harvesterBaseURL)/harvester/feed?limit=\(limit)"
        if let t = ticker, !t.isEmpty {
            let enc = t.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? t
            urlStr += "&ticker=\(enc)"
        }
        guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode(HarvesterFeedResponse.self, from: data)
    }

    func fetchGovernanceCards(ticker: String) async throws -> [HarvestedCard] {
        let enc = ticker.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? ticker
        guard let url = URL(string: "\(harvesterBaseURL)/harvester/governance/\(enc)") else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, _) = try await session.data(for: request)
        return try JSONDecoder().decode([HarvestedCard].self, from: data)
    }

    func fetchHarvesterSources() async throws -> [HarvesterSourceStatus] {
        guard let url = URL(string: "\(harvesterBaseURL)/harvester/sources") else {
            throw NetworkError.invalidURL
        }
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode([HarvesterSourceStatus].self, from: data)
    }

    func brainstorm(topic: String, riskTolerance: String) async throws -> BrainstormResponse {
        guard let url = URL(string: "\(baseURL)/brainstorm") else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let body = ["topic": topic, "risk_tolerance": riskTolerance]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, resp) = try await session.data(for: request)
        if let httpResp = resp as? HTTPURLResponse, httpResp.statusCode != 200 {
            throw NetworkError.invalidResponse
        }
        return try JSONDecoder().decode(BrainstormResponse.self, from: data)
    }

    // MARK: - YouTube Summary

    func fetchYouTubeSummary(videoId: String) async throws -> YouTubeVideoSummaryResponse {
        // Try cached summary first
        if let url = URL(string: "\(baseURL)/api/v1/youtube/summary/\(videoId)") {
            var req = authRequest(url)
            req.httpMethod = "GET"
            let (data, resp) = try await dataWithRetry(for: req)
            if let http = resp as? HTTPURLResponse, http.statusCode == 200 {
                return try JSONDecoder().decode(YouTubeVideoSummaryResponse.self, from: data)
            }
        }
        // Generate summary (cache miss or error)
        guard let url = URL(string: "\(baseURL)/api/v1/youtube/summary") else {
            throw NetworkError.invalidURL
        }
        var req = authRequest(url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["url": "https://www.youtube.com/watch?v=\(videoId)", "force_refresh": false] as [String: Any]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (data, resp) = try await dataWithRetry(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw NetworkError.invalidResponse
        }
        return try JSONDecoder().decode(YouTubeVideoSummaryResponse.self, from: data)
    }

    // MARK: - Notifications Inbox

    func fetchNotifications(limit: Int = 50) async throws -> [NotificationDTO] {
        let endpoint = "/api/v1/notifications?limit=\(limit)"
        return try await _fetchDecode([NotificationDTO].self, endpoint: endpoint)
    }

    func markNotificationRead(id: Int) async throws {
        let endpoint = "/api/v1/notifications/\(id)/read"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.httpMethod = "PUT"
        let (_, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw NetworkError.invalidResponse
        }
    }
}
