import Foundation

extension NetworkManager {

    func fetchMarketPulse() async -> MarketPulseResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/pulse") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(MarketPulseResponse.self, from: data)
    }

    func fetchMomentum() async -> MomentumResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/momentum") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(MomentumResponse.self, from: data)
    }

    func fetchMacroAlternatives() async -> MacroAlternativesResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/macro-alternatives") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(MacroAlternativesResponse.self, from: data)
    }

    func fetchInstitutionalFlow() async -> InstitutionalFlowResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/institutional-flow") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(InstitutionalFlowResponse.self, from: data)
    }

    func fetchMarketDashboard() async -> MarketDashboardResponse? {
        guard let url = URL(string: "\(baseURL)/api/v1/market/dashboard") else { return nil }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return try? JSONDecoder().decode(MarketDashboardResponse.self, from: data)
    }
}
