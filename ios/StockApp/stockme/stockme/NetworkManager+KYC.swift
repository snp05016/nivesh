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
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(DeviceBindingDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
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
}
