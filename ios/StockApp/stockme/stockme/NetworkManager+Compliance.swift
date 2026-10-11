import Foundation

// MARK: - Entitlements + Compliance Disclosures
//
// DEMO-GRADE. `fetchDisclosure(key:)` and `fetchKeyFactStatement(...)` talk
// to the REAL /api/v1/compliance/... surface (backend/routers/compliance.py
// + backend/services/disclosure_service.py) — every disclosure body
// returned is clearly-labelled placeholder/demo copy for a portfolio
// project, NOT real legal advice or a real regulatory filing.
// `fetchEntitlements()` talks to the REAL
// GET /api/v1/subscription/entitlements endpoint (backend/routers/
// subscription.py, backed by services/entitlement_service.py) — kept here
// rather than in NetworkManager+Subscription.swift per this feature's file
// layout, even though the endpoint lives under the /api/v1/subscription
// prefix. All calls follow the auth + error-handling shape already used by
// the Loan Marketplace extension (see NetworkManager+Finance.swift) —
// GET requests attach the bearer token via `authRequest(_:)` when logged
// in, decode failures surface as NetworkError.decodingError, and non-2xx
// responses surface as NetworkError.fetchFailed with the endpoint + status
// + raw body prefix for diagnostics.

extension NetworkManager {

    // MARK: - Entitlements

    /// Fetches the signed-in user's effective tier + per-feature entitlement
    /// map, used to gate PremiumUpsellBanner / PaywallView on real
    /// server-side state instead of static client-side assumptions.
    /// GET /api/v1/subscription/entitlements
    func fetchEntitlements() async throws -> EntitlementsDTO {
        let endpoint = "/api/v1/subscription/entitlements"
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
        do { return try JSONDecoder().decode(EntitlementsDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Disclosures

    /// Fetches static, illustrative disclosure content for `key`
    /// (see DisclosureKey — privacy_policy | data_sharing_governance |
    /// digital_lending_compliance | lending_service_provider |
    /// apr_disclosure | sim_binding_fraud_prevention).
    /// GET /api/v1/compliance/disclosures/{key}
    func fetchDisclosure(key: String) async throws -> DisclosureDTO {
        let endpoint = "/api/v1/compliance/disclosures/\(key)"
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
        do { return try JSONDecoder().decode(DisclosureDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches the computed Key Fact Statement (KFS) breakdown for a loan
    /// offer — loan_amount, interest_rate, all_fees, apr, tenure_months.
    /// GET /api/v1/compliance/key-fact-statement?loan_offer_id=
    func fetchKeyFactStatement(loanOfferId: Int) async throws -> KeyFactStatementDTO {
        try await fetchKeyFactStatement(queryItem: URLQueryItem(name: "loan_offer_id", value: String(loanOfferId)))
    }

    /// Fetches the computed Key Fact Statement (KFS) breakdown for a fixed
    /// deposit scheme — principal shown via `loan_amount`, interest_rate,
    /// all_fees (always 0 for FDs in this demo), apr, tenure_months.
    /// GET /api/v1/compliance/key-fact-statement?scheme_id=
    func fetchKeyFactStatement(schemeId: Int) async throws -> KeyFactStatementDTO {
        try await fetchKeyFactStatement(queryItem: URLQueryItem(name: "scheme_id", value: String(schemeId)))
    }

    private func fetchKeyFactStatement(queryItem: URLQueryItem) async throws -> KeyFactStatementDTO {
        var components = URLComponents(string: "\(baseURL)/api/v1/compliance/key-fact-statement")
        components?.queryItems = [queryItem]

        let endpoint = "/api/v1/compliance/key-fact-statement"
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
        do { return try JSONDecoder().decode(KeyFactStatementDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Account deletion (FINSEC-03)

    /// Schedules erasure of the signed-in account. The backend re-checks the
    /// password (403 when wrong) and erases the data after its grace period
    /// (`ERASURE_GRACE_DAYS`), unless `cancelAccountDeletion()` runs first.
    /// POST /api/v1/compliance/deletion-requests
    func requestAccountDeletion(password: String) async throws -> DeletionRequestDTO {
        var request = try complianceRequest("/api/v1/compliance/deletion-requests", method: "POST")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(["password": password])
        let (data, response) = try await session.data(for: request)
        try NetworkError.ensureOK(data: data, response: response)
        do { return try JSONDecoder().decode(DeletionRequestDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Latest deletion request for the signed-in user (`status` nil when none).
    /// GET /api/v1/compliance/deletion-requests/status
    func fetchDeletionStatus() async throws -> DeletionRequestDTO {
        let request = try complianceRequest("/api/v1/compliance/deletion-requests/status", method: "GET")
        let (data, response) = try await session.data(for: request)
        try NetworkError.ensureOK(data: data, response: response)
        do { return try JSONDecoder().decode(DeletionRequestDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Withdraws a pending deletion request during the grace period.
    /// POST /api/v1/compliance/deletion-requests/cancel
    func cancelAccountDeletion() async throws {
        let request = try complianceRequest("/api/v1/compliance/deletion-requests/cancel", method: "POST")
        let (data, response) = try await session.data(for: request)
        try NetworkError.ensureOK(data: data, response: response)
    }

    private func complianceRequest(_ endpoint: String, method: String) throws -> URLRequest {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else { throw NetworkError.invalidURL }
        var request = authRequest(url)
        request.httpMethod = method
        request.timeoutInterval = 20
        return request
    }
}

/// Deletion request state from /api/v1/compliance/deletion-requests*:
/// "pending" (erasure scheduled, cancellable), "completed", "cancelled", or nil.
struct DeletionRequestDTO: Decodable {
    let status: String?
}
