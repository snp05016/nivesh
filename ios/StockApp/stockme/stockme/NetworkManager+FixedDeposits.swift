import Foundation

// MARK: - Fixed Deposit Marketplace
//
// MOCK DATA - simulated for demo purposes, not a real integration. Talks to
// a mock backend surface under /api/fixed-deposits (built concurrently by
// another agent against the CONTRACT documented in FixedDepositModels.swift).
// Mirrors the exact auth + error-handling shape of the Loan Marketplace
// extension (NetworkManager+Finance.swift): GET requests attach the bearer
// token via `authRequest(_:)` when logged in, decode failures surface as
// NetworkError.decodingError, and non-2xx responses surface as
// NetworkError.fetchFailed with the endpoint + status + raw body prefix for
// diagnostics.

extension NetworkManager {

    // MARK: - Scheme Discovery

    /// Fetches every mock FD scheme, optionally filtered server-side by
    /// tenure range. GET /api/fixed-deposits/schemes?min_tenure_months=&max_tenure_months=
    func fetchFDSchemes(minTenure: Int? = nil, maxTenure: Int? = nil) async throws -> [FDSchemeDTO] {
        var components = URLComponents(string: "\(baseURL)/api/fixed-deposits/schemes")
        var queryItems: [URLQueryItem] = []
        if let minTenure {
            queryItems.append(URLQueryItem(name: "min_tenure_months", value: String(minTenure)))
        }
        if let maxTenure {
            queryItems.append(URLQueryItem(name: "max_tenure_months", value: String(maxTenure)))
        }
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }

        let endpoint = "/api/fixed-deposits/schemes"
        guard let url = components?.url else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([FDSchemeDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches full detail for a single FD scheme.
    /// GET /api/fixed-deposits/schemes/{id}
    func getFDSchemeDetail(id: Int) async throws -> FDSchemeDTO {
        let endpoint = "/api/fixed-deposits/schemes/\(id)"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(FDSchemeDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Calculator

    /// Projects the maturity amount for a given principal/tenure/rate. MOCK
    /// DATA - simulated for demo purposes, not a real integration; a plain
    /// compound-interest projection, not financial advice.
    /// POST /api/fixed-deposits/calculator
    func calculateFDMaturity(principal: Double, tenure: Int, rate: Double) async throws -> FDCalculatorResponse {
        let endpoint = "/api/fixed-deposits/calculator"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        let body = FDCalculatorRequest(principalAmount: principal, tenureMonths: tenure, interestRatePct: rate)
        request.httpBody = try? JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(FDCalculatorResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Bookings

    /// Submits a (mock) FD booking. MOCK DATA — no real payment processing
    /// happens for either UPI or Net Banking. `deviceId` is checked against
    /// the mock KYC device-binding gate on the backend before any
    /// auto-confirmation — a `failed` status with a populated
    /// `decisionReason` means the booking failed closed (e.g. "SIM binding
    /// required" / "KYC incomplete").
    /// POST /api/fixed-deposits/bookings
    func bookFixedDeposit(_ requestBody: FDBookingRequest, idempotencyKey: String? = nil) async throws -> FDBookingResponse {
        let endpoint = "/api/fixed-deposits/bookings"
        let request = try makeJSONPOST(endpoint: endpoint, body: requestBody, idempotencyKey: idempotencyKey)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(FDBookingResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches every (mock) FD booking for the current user.
    /// GET /api/fixed-deposits/bookings
    func fetchFDBookings() async throws -> [FDBookingResponse] {
        let endpoint = "/api/fixed-deposits/bookings"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.timeoutInterval = 20
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode([FDBookingResponse].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}
