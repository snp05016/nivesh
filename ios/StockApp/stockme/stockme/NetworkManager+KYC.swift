import Foundation

// MARK: - KYC Consent + Device-Binding ("SIM-binding")
//
// MOCK DATA - simulated for demo purposes, not a real integration. Talks to
// the REAL, already-merged /api/kyc/... surface (backend/routers/kyc.py +
// backend/services/kyc_consent_service.py): there is no real telecom
// SIM-swap-detection API and no real credit-bureau / government ID
// verification anywhere behind these endpoints. All calls follow the auth +
// error-handling shape already used by the Loan Marketplace extension (see
// NetworkManager+Finance.swift) — GET/POST requests attach the bearer token
// via `authRequest(_:)` when logged in, decode failures surface as
// NetworkError.decodingError, and non-2xx responses surface as
// NetworkError.fetchFailed with the endpoint + status + raw body prefix for
// diagnostics.

extension NetworkManager {

    /// Fetches every currently-active (granted, not revoked) KYC consent for
    /// the signed-in user. GET /api/kyc/consents
    func fetchActiveConsents() async throws -> [ConsentDTO] {
        let endpoint = "/api/kyc/consents"
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
        do { return try JSONDecoder().decode([ConsentDTO].self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Records a new consent grant/withdrawal for `type` (e.g. "credit_check",
    /// "sim_binding", "data_sharing") — each call inserts a new audit-trail
    /// row server-side rather than mutating an existing one.
    /// POST /api/kyc/consents
    func grantConsent(type: String, granted: Bool) async throws -> ConsentDTO {
        let endpoint = "/api/kyc/consents"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        request.httpBody = try? JSONEncoder().encode(RecordConsentRequest(consentType: type, granted: granted))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(ConsentDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// "Bind This Device" action — registers `deviceId` (typically
    /// UIDevice.current.identifierForVendor?.uuidString, the same source
    /// LoanViewModel.submit() uses) as a mock SIM/device binding for the
    /// signed-in user. POST /api/kyc/device-binding
    func bindDevice(deviceId: String, isPrimary: Bool = true) async throws -> DeviceBindingDTO {
        let endpoint = "/api/kyc/device-binding"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        request.httpBody = try? JSONEncoder().encode(BindDeviceRequest(deviceId: deviceId, isPrimary: isPrimary))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        // 409: a mock fraud heuristic rejected the bind;
        // body is {"detail": {"bound": false, "reason", "fraud_signal"}}.
        if http.statusCode == 409 {
            throw NetworkError.serverError(409, Self.deviceBindRejectionMessage(from: data))
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(DeviceBindingDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Friendly copy for a 409 device-bind rejection
    /// (`{"detail": {"reason", "fraud_signal"}}`). The backend `reason` is
    /// diagnostic mock text, so only `fraud_signal` drives the message.
    nonisolated static func deviceBindRejectionMessage(from data: Data) -> String {
        let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        let detail = obj?["detail"] as? [String: Any]
        switch detail?["fraud_signal"] as? String {
        case "cross_user_device_reuse":
            return "This device is already registered to another account."
        case "rebind_rate_limit_exceeded":
            return "Too many device bind attempts in the last 24 hours. Please try again later."
        default:
            return "This device couldn't be bound right now."
        }
    }

    /// Checks whether `deviceId` matches the signed-in user's registered
    /// primary device — the same MOCK check the loan/FD KYC gate uses
    /// server-side. GET /api/kyc/device-binding/verify?device_id=
    func verifyDeviceBinding(deviceId: String) async throws -> DeviceBindingVerifyDTO {
        var components = URLComponents(string: "\(baseURL)/api/kyc/device-binding/verify")
        components?.queryItems = [URLQueryItem(name: "device_id", value: deviceId)]

        let endpoint = "/api/kyc/device-binding/verify"
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
        do { return try JSONDecoder().decode(DeviceBindingVerifyDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// Fetches the (mock) aggregate fraud-signal counters for the signed-in
    /// user's device-binding activity. MOCK DATA - simulated for demo
    /// purposes, not a real fraud-detection engine. Best-effort against the
    /// concurrent fraud-signals backend work's contract:
    /// GET /api/kyc/fraud-signals ->
    /// {total_bind_attempts_24h, cross_user_rejections_total,
    ///  rate_limit_hits_24h, is_flagged}
    func fetchFraudSignals() async throws -> FraudSignalsDTO {
        let endpoint = "/api/kyc/fraud-signals"
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
        do { return try JSONDecoder().decode(FraudSignalsDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
}
