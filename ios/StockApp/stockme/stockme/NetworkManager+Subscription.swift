import Foundation

// MARK: - Subscription / Paywall
//
// MOCK DATA - simulated for demo purposes, not a real integration. Every
// endpoint below talks to the mock backend surface at
// backend/routers/subscription.py (prefix /api/v1/subscription): no real
// StoreKit purchase completion, no App Store receipt validation, no real
// payment processor wired. All calls follow the auth + error-handling shape
// already used by the Loan Marketplace extension (see
// NetworkManager+Finance.swift) — GET requests attach the bearer token via
// `authRequest(_:)` when logged in, decode failures surface as
// NetworkError.decodingError, and non-2xx responses surface as
// NetworkError.fetchFailed with the endpoint + status + raw body prefix for
// diagnostics.
//
// NOTE: there is no plan/pricing-catalog endpoint on the backend (only
// user_subscriptions, the *current* plan) — the paywall's tier comparison
// is sourced from the client-side SubscriptionPlanCatalog in
// SubscriptionModels.swift instead.

extension NetworkManager {

    /// Fetches the signed-in user's current plan/tier row, lazily created
    /// server-side on first access. GET /api/v1/subscription
    func fetchCurrentSubscription() async throws -> CurrentSubscriptionDTO {
        let endpoint = "/api/v1/subscription"
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
        do { return try JSONDecoder().decode(CurrentSubscriptionDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    // Debug-only (ReleaseGate, App Review 3.1.1): paid tiers must go through
    // StoreKit in-app purchase, so the mock upgrade/cancel never ships.
    #if DEBUG
    /// "Upgrade"/"Downgrade" action from the paywall or management screen.
    /// MOCK - simulated for demo purposes: asks the mock backend to flip the
    /// user's plan row. No real StoreKit purchase sheet is presented, no
    /// receipt is generated. POST /api/v1/subscription/upgrade
    func mockUpgradeSubscription(tier: String, billingCycle: String) async throws -> CurrentSubscriptionDTO {
        let endpoint = "/api/v1/subscription/upgrade"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 15
        request.httpBody = try? JSONEncoder().encode(SubscriptionUpgradeRequest(tier: tier, billingCycle: billingCycle))
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(CurrentSubscriptionDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }

    /// "Cancel Plan" action from the management screen. MOCK - simulated for
    /// demo purposes: marks the mock plan row `is_active = false` (access
    /// continues until `renews_at`, matching real-world App Store cancel
    /// semantics) — no real StoreKit refund/cancellation call is made. The
    /// backend endpoint takes no request body (no `reason` field exists
    /// server-side), so any cancellation reason stays purely client-side UX
    /// copy. POST /api/v1/subscription/cancel
    func mockCancelSubscription() async throws -> CurrentSubscriptionDTO {
        let endpoint = "/api/v1/subscription/cancel"
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Invalid URL")
        }
        var request = authRequest(url)
        request.httpMethod = "POST"
        request.timeoutInterval = 15
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw NetworkError.fetchFailed(endpoint: endpoint, status: 0, body: "Not HTTP")
        }
        guard (200...299).contains(http.statusCode) else {
            let bodyStr = String(data: data, encoding: .utf8)?.prefix(300) ?? "<binary>"
            throw NetworkError.fetchFailed(endpoint: endpoint, status: http.statusCode, body: String(bodyStr))
        }
        do { return try JSONDecoder().decode(CurrentSubscriptionDTO.self, from: data) }
        catch { throw NetworkError.decodingError(error.localizedDescription) }
    }
    #endif
}
