import Foundation

// MARK: - Personal Finance & Loan Marketplace
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// endpoint under /api/finance/... and /api/loans/... below talks to a mock
// backend surface (backend/routers/finance.py, backend/routers/loans.py):
// no real bank-linking OAuth/Plaid flow, no real NBFC/credit-bureau pull,
// no government ID collection. All calls follow the auth + error-handling
// shape already used by the Mutual Fund Hub extension (see the
// `// MARK: - Mutual Fund Hub` section of NetworkManager.swift) — GET
// requests attach the bearer token via `authRequest(_:)` when logged in,
// decode failures surface as NetworkError.decodingError, and non-2xx
// responses surface as NetworkError.fetchFailed with the endpoint + status
// + raw body prefix for diagnostics.

extension NetworkManager {

    // MARK: - Money POSTs (IOSCORE-17)

    /// Builds an authenticated JSON POST for a money action (loan, disbursement,
    /// FD booking). 30 s timeout; encode failures throw instead of sending an
    /// empty body; `idempotencyKey` is sent as `Idempotency-Key` so a retry of the
    /// same user intent can be deduped server-side.
    func makeJSONPOST<B: Encodable>(endpoint: String, body: B?, idempotencyKey: String?) throws -> URLRequest {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 30
        if let body {
            request.httpBody = try JSONEncoder().encode(body)
        }
        if let idempotencyKey {
            request.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key")
        }
        return request
    }

    // MARK: - Finance Tracker

    /// Fetches every mock "linked" bank account for the current user.
    /// GET /api/finance/accounts
    func fetchLinkedAccounts() async throws -> [LinkedBankAccountDTO] {
        let endpoint = "/api/finance/accounts"
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
        do { return try JSONDecoder().decode([LinkedBankAccountDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches the aggregate balance summary card (total balance, monthly
    /// income/spend) across all mock linked accounts.
    /// GET /api/finance/summary
    func fetchFinanceSummary() async throws -> FinanceSummaryDTO {
        let endpoint = "/api/finance/summary"
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
        do { return try JSONDecoder().decode(FinanceSummaryDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches the (placeholder) spend-by-category breakdown.
    /// GET /api/finance/spend-categories
    func fetchSpendCategories() async throws -> [SpendCategoryDTO] {
        let endpoint = "/api/finance/spend-categories"
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
        do { return try JSONDecoder().decode([SpendCategoryDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// "Link Account (Demo)" button action — asks the mock backend to
    /// fabricate a new demo linked account. No real bank OAuth/Plaid flow.
    /// MOCK DATA - simulated for demo purposes, not a real integration.
    /// POST /api/finance/accounts/link-demo
    func linkAccountDemo(bankName: String, accountType: LinkedAccountType) async throws -> LinkedBankAccountDTO {
        let endpoint = "/api/finance/accounts/link-demo"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        let body = LinkAccountDemoRequest(bankName: bankName, accountType: accountType.rawValue)
        request.httpBody = try? JSONEncoder().encode(body)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(LinkedBankAccountDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Loan Marketplace

    /// Fetches every mock loan offer, optionally filtered server-side by
    /// loan_type (the only filter backend/routers/finance.py's
    /// GET /api/finance/loan-offers actually supports — amount/tenure
    /// filters are applied client-side by LoanViewModel).
    /// GET /api/finance/loan-offers?loan_type=
    func fetchLoanOffers(
        loanType: LoanType? = nil,
        minAmount: Double? = nil,
        maxAmount: Double? = nil,
        maxTenureMonths: Int? = nil
    ) async throws -> [LoanOfferDTO] {
        var components = URLComponents(string: "\(baseURL)/api/finance/loan-offers")
        if let loanType {
            components?.queryItems = [URLQueryItem(name: "loan_type", value: loanType.rawValue)]
        }

        let endpoint = "/api/finance/loan-offers"
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
        do { return try JSONDecoder().decode([LoanOfferDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches full detail for a single loan offer by filtering the
    /// full offer list — backend/routers/finance.py has no
    /// GET /api/finance/loan-offers/{id} detail endpoint.
    func getLoanOfferDetail(offerId: Int) async throws -> LoanOfferDTO {
        let offers = try await fetchLoanOffers()
        guard let match = offers.first(where: { $0.id == offerId }) else {
            throw NetworkError.fetchFailed(endpoint: "/api/finance/loan-offers", status: 404, body: "Offer \(offerId) not found")
        }
        return match
    }

    /// Submits a (mock) loan application. MOCK DATA — no real underwriting
    /// or credit-bureau pull happens server-side. `deviceId` is checked
    /// against the mock KYC device-binding gate in
    /// services/kyc_consent_service.py before any auto-approval.
    /// POST /api/finance/loan-applications
    func submitLoanApplication(_ requestBody: LoanApplicationRequest, idempotencyKey: String? = nil) async throws -> LoanApplicationResponse {
        let endpoint = "/api/finance/loan-applications"
        let request = try makeJSONPOST(endpoint: endpoint, body: requestBody, idempotencyKey: idempotencyKey)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(LoanApplicationResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Polls status for a previously-submitted (mock) loan application.
    /// GET /api/finance/loan-applications/{id}
    func getLoanApplicationStatus(applicationId: Int) async throws -> LoanApplicationResponse {
        let endpoint = "/api/finance/loan-applications/\(applicationId)"
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
        do { return try JSONDecoder().decode(LoanApplicationResponse.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // MARK: - Mock Loan Disbursement
    //
    // MOCK DATA - simulated for demo purposes, not a real integration. No
    // real funds are ever moved and no real NBFC is contacted. Best-effort
    // against the concurrent mock-loan-disbursement backend work — verify
    // endpoint paths/shape against the real router once it lands.

    /// "Request Disbursement (Demo)" button action for an approved (mock)
    /// loan application. POST /api/finance/loan-applications/{id}/disburse
    func requestDisbursement(applicationId: Int, idempotencyKey: String? = nil) async throws -> DisbursementDTO {
        let endpoint = "/api/finance/loan-applications/\(applicationId)/disburse"
        let request = try makeJSONPOST(endpoint: endpoint, body: Optional<EmptyJSONBody>.none, idempotencyKey: idempotencyKey)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        if http.statusCode == 409 {
            // Business-rule rejection (no primary bank account, already disbursed): {"detail": String}.
            throw NetworkError.serverError(409, NetworkError.serverDetail(from: data))
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(DisbursementDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// The caller's loan-marketplace bank accounts (disbursement destinations).
    /// GET /api/finance/linked-bank-accounts
    func fetchLoanBankAccounts() async throws -> [LoanBankAccountDTO] {
        let endpoint = "/api/finance/linked-bank-accounts"
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
        do { return try JSONDecoder().decode([LoanBankAccountDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Links a MOCK bank account for loan disbursement. Only "XXXX" + the last
    /// 4 digits is sent; the full account number never leaves the device.
    /// POST /api/finance/linked-bank-accounts (409 = already linked).
    func linkLoanBankAccount(bankName: String, last4: String) async throws -> LoanBankAccountDTO {
        let endpoint = "/api/finance/linked-bank-accounts"
        let body = LinkLoanBankAccountRequest(bankName: bankName, maskedAccountNumber: "XXXX" + last4, accountType: "savings")
        let request = try makeJSONPOST(endpoint: endpoint, body: body, idempotencyKey: nil)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        if http.statusCode == 409 || http.statusCode == 422 {
            throw NetworkError.serverError(http.statusCode, NetworkError.serverDetail(from: data))
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(LoanBankAccountDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Polls (mock) disbursement status for a loan application.
    /// GET /api/finance/loan-applications/{id}/disbursement
    func fetchDisbursementStatus(applicationId: Int) async throws -> DisbursementDTO {
        let endpoint = "/api/finance/loan-applications/\(applicationId)/disbursement"
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
        do { return try JSONDecoder().decode(DisbursementDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}

/// Placeholder body type for bodiless money POSTs passed to `makeJSONPOST`.
struct EmptyJSONBody: Encodable {}

extension Error {
    /// User-facing copy for a failed money POST: timeouts must not invite a blind
    /// retry, offline and 4xx/5xx get distinct text, anything else uses `fallback`.
    func moneyActionMessage(fallback: String) -> String {
        if let urlError = self as? URLError {
            switch urlError.code {
            case .timedOut, .networkConnectionLost:
                return "The request timed out and may have gone through. Check its status before retrying."
            case .notConnectedToInternet:
                return "You're offline. Connect and try again."
            default:
                return fallback
            }
        }
        if let networkError = self as? NetworkError, case .fetchFailed(_, let status, _) = networkError {
            if (400...499).contains(status) { return "The request was rejected (code \(status))." }
            if status >= 500 { return "Server error. Please try again shortly." }
        }
        return fallback
    }
}
