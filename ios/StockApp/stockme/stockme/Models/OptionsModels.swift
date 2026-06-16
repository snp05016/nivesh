// Models/OptionsModels.swift
// Domain: Options strategy builder — payoff computation, legs, request/response contracts

import SwiftUI

// MARK: - Options Strategy Builder

struct OptionLeg: Codable {
    let type: String            // CALL or PUT
    let position: String        // LONG or SHORT
    let strike: Double
    let premium: Double

    enum CodingKeys: String, CodingKey {
        case type, position, strike, premium
    }
}

struct PayoffPoint: Codable, Identifiable {
    var id: Double { underlyingPrice }
    let underlyingPrice: Double
    let pnl: Double

    enum CodingKeys: String, CodingKey {
        case underlyingPrice = "underlying_price"
        case pnl
    }
}

struct OptionsPayoffResponse: Codable {
    let spotPrice: Double
    let payoffVector: [PayoffPoint]
    let maxProfit: Double?
    let maxProfitUnlimited: Bool
    let maxProfitFormatted: String
    let maxLoss: Double?
    let maxLossUnlimited: Bool
    let maxLossFormatted: String
    let breakevens: [Double]
    let netPremium: Double
    let netPremiumFormatted: String
    let numLegs: Int
    let strategyType: String

    enum CodingKeys: String, CodingKey {
        case spotPrice = "spot_price"
        case payoffVector = "payoff_vector"
        case maxProfit = "max_profit"
        case maxProfitUnlimited = "max_profit_unlimited"
        case maxProfitFormatted = "max_profit_formatted"
        case maxLoss = "max_loss"
        case maxLossUnlimited = "max_loss_unlimited"
        case maxLossFormatted = "max_loss_formatted"
        case breakevens
        case netPremium = "net_premium"
        case netPremiumFormatted = "net_premium_formatted"
        case numLegs = "num_legs"
        case strategyType = "strategy_type"
    }
}

struct OptionsPayoffRequest: Codable {
    let spotPrice: Double
    let legs: [OptionLeg]

    enum CodingKeys: String, CodingKey {
        case spotPrice = "spot_price"
        case legs
    }
}
