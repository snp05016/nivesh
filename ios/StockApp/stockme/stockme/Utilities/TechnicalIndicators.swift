import Foundation

enum TechnicalIndicators {
    /// Wilder RSI, seeded with the simple average of the first `period` changes.
    /// `result[k]` belongs to `closes[period + 1 + k]`. A window with no gains and no
    /// losses is undefined and reads 50 (neutral), not overbought.
    static func rsi(closes: [Double], period: Int = 14) -> [Double] {
        guard period > 0, closes.count > period + 1 else { return [] }
        let changes = zip(closes.dropFirst(), closes).map { $0 - $1 }
        let n = Double(period)
        var avgGain = changes.prefix(period).reduce(0) { $0 + max($1, 0) } / n
        var avgLoss = changes.prefix(period).reduce(0) { $0 + max(-$1, 0) } / n
        return changes.dropFirst(period).map { change in
            avgGain = (avgGain * (n - 1) + max(change, 0)) / n
            avgLoss = (avgLoss * (n - 1) + max(-change, 0)) / n
            if avgLoss == 0 { return avgGain == 0 ? 50 : 100 }
            return 100 - 100 / (1 + avgGain / avgLoss)
        }
    }
}
