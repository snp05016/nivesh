import Foundation

// MARK: - Lab contract (docs/platform/api-contract.md, backend /api/v1/research-lab)
//
// Decoded only with `NetworkManager.labDecoder()` (`.convertFromSnakeCase`), so every
// property is the camel-cased wire key ("chg_1d" -> chg1d, "ic_ci95" -> icCi95).
// Note: that strategy also camel-cases dictionary keys ("base_mom_20" -> "baseMom20");
// views pass such keys through `LabFormat.humanize`.
//
// Tolerant by design: every field is optional, and server string enums are kept as raw
// strings with a typed accessor that falls back to `.unknown`, so additive server
// changes never break a shipped build.

// MARK: - Free-form JSON (evidence, grounded_on, events, availability)

nonisolated enum LabJSON: Decodable, Hashable {
    case string(String), number(Double), bool(Bool), array([LabJSON]), object([String: LabJSON]), null

    nonisolated private struct AnyKey: CodingKey {
        var stringValue: String
        var intValue: Int? { nil }
        init?(stringValue: String) { self.stringValue = stringValue }
        init?(intValue: Int) { nil }
    }

    init(from decoder: Decoder) throws {
        if let obj = try? decoder.container(keyedBy: AnyKey.self) {
            var out: [String: LabJSON] = [:]
            for key in obj.allKeys { out[key.stringValue] = try obj.decode(LabJSON.self, forKey: key) }
            self = .object(out)
            return
        }
        if var arr = try? decoder.unkeyedContainer() {
            var out: [LabJSON] = []
            while !arr.isAtEnd { out.append(try arr.decode(LabJSON.self)) }
            self = .array(out)
            return
        }
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let b = try? c.decode(Bool.self) { self = .bool(b) }
        else if let n = try? c.decode(Double.self) { self = .number(n) }
        else { self = .string(try c.decode(String.self)) }
    }

    /// Short plain-text rendering for evidence rows.
    var display: String {
        switch self {
        case .string(let s): return s
        case .number(let n): return n.rounded() == n && abs(n) < 1e12 ? String(Int(n)) : String(format: "%.4g", n)
        case .bool(let b): return b ? "yes" : "no"
        case .array(let a): return a.map(\.display).joined(separator: ", ")
        case .object(let o): return o.keys.sorted().map { "\($0): \(o[$0]!.display)" }.joined(separator: "; ")
        case .null: return "—"
        }
    }

    var objectValue: [String: LabJSON]? {
        if case .object(let o) = self { return o }
        return nil
    }
}

/// Decodes `[T]`, or an object wrapping the list under a common key, so the ledger
/// endpoints work whether the backend returns a bare array or `{items: [...]}`.
nonisolated struct LabList<T: Decodable>: Decodable {
    let items: [T]
    let total: Int?

    nonisolated private enum Keys: String, CodingKey { case items, sessions, experiments, results, total, trials, count }

    init(from decoder: Decoder) throws {
        if let bare = try? decoder.singleValueContainer().decode([T].self) {
            items = bare
            total = nil
            return
        }
        let c = try decoder.container(keyedBy: Keys.self)
        items = (try? c.decode([T].self, forKey: .items)) ?? (try? c.decode([T].self, forKey: .sessions))
            ?? (try? c.decode([T].self, forKey: .experiments)) ?? (try? c.decode([T].self, forKey: .results)) ?? []
        total = (try? c.decode(Int.self, forKey: .total)) ?? (try? c.decode(Int.self, forKey: .trials))
            ?? (try? c.decode(Int.self, forKey: .count))
    }
}

/// Server ids may be strings or integers; both become a String.
nonisolated struct LabID: Decodable, Hashable {
    let value: String
    init(_ value: String) { self.value = value }
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { value = s }
        else if let i = try? c.decode(Int.self) { value = String(i) }
        else { value = String(try c.decode(Double.self)) }
    }
}

// MARK: - Typed views over raw enum strings

nonisolated enum LabOrderStatus: String {
    case open = "OPEN", partial = "PARTIAL", filled = "FILLED", cancelled = "CANCELLED"
    case expired = "EXPIRED", partialExpired = "PARTIAL_EXPIRED", rejected = "REJECTED", unknown
    init(raw: String?) { self = LabOrderStatus(rawValue: raw ?? "") ?? .unknown }
    var isWorking: Bool { self == .open || self == .partial }
}

nonisolated enum LabQuadrant: String {
    case earned, badBreak = "bad_break", lucky, predictableLoss = "predictable_loss", unknown
    init(raw: String?) { self = LabQuadrant(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabSeverity: String {
    case low, medium, high, unknown
    init(raw: String?) { self = LabSeverity(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabSkepticStatus: String {
    case pass, warn, fail, unknown
    init(raw: String?) { self = LabSkepticStatus(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabVerdictLabel: String {
    case supported, fragile, notSupported = "not_supported", insufficientData = "insufficient_data", unknown
    init(raw: String?) { self = LabVerdictLabel(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabMentorMode: String {
    case llm, rules, unknown
    init(raw: String?) { self = LabMentorMode(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabEventKind: String {
    case priceAnomaly = "price_anomaly", volumeAnomaly = "volume_anomaly"
    case corporateAction = "corporate_action", sourcedEvent = "sourced_event", unknown
    init(raw: String?) { self = LabEventKind(rawValue: raw ?? "") ?? .unknown }
}

nonisolated enum LabSectionKind: String {
    case text, example, formula, interactive, unknown
    init(raw: String?) { self = LabSectionKind(rawValue: raw ?? "") ?? .unknown }
}

// MARK: - Scenarios / universe

nonisolated struct LabScenarioCatalog: Decodable {
    let version: LabJSON?
    let scenarios: [LabScenario]?
    let dataWindow: [String?]?
}

nonisolated struct LabScenario: Decodable, Identifiable, Hashable {
    let id: String
    let title: String?
    let category: String?
    let start: String?
    let end: String?
    let difficulty: String?
    let universeHint: [String]?
    let briefing: String?
    /// Hindsight. Only rendered once a session on this scenario has finished.
    let debrief: String?
    let timeline: [LabTimelineEvent]?
    let learningGoals: [String]?
    let relatedConcepts: [String]?
    let dataAvailable: Bool?
}

nonisolated struct LabTimelineEvent: Decodable, Hashable {
    let date: String?
    let event: String?
}

nonisolated struct LabUniverse: Decodable {
    let asof: String?
    let symbols: [String]?
    let provenance: LabProvenance?
}

// MARK: - Session payload

nonisolated struct LabSimConfig: Decodable, Hashable {
    var start: String?
    var end: String?
    var universe: [String]?
    var capital: Double?
    var hideIdentity: Bool?

    /// Request body; server defaults apply to costs and participation.
    var json: [String: Any] {
        var out: [String: Any] = [:]
        if let start { out["start"] = start }
        if let end { out["end"] = end }
        if let universe { out["universe"] = universe }
        if let capital { out["capital"] = capital }
        if let hideIdentity { out["hide_identity"] = hideIdentity }
        return out
    }
}

nonisolated struct LabSession: Decodable {
    let id: LabID?
    let title: String?
    let scenarioId: String?
    let createdAt: String?
    let config: LabSimConfig?
    let state: LabSimState?
    let performance: LabPerformance?
    let watchlist: [LabWatchRow]?
    let provenance: LabProvenance?
    let benchmark: String?
    /// Sourced headlines dated on or before the clock, newest first.
    let news: [LabNewsItem]?
}

nonisolated struct LabNewsItem: Decodable, Hashable {
    let date: String?
    let symbol: String?
    let title: String?
    let source: String?
    let url: String?
}

nonisolated struct LabSessionSummary: Decodable, Identifiable, Hashable {
    let sessionId: LabID?
    let title: String?
    let scenarioId: String?
    let clock: String?
    let equity: Double?
    let finished: Bool?
    let updatedAt: String?
    var id: String { sessionId?.value ?? "" }

    nonisolated private enum CodingKeys: String, CodingKey { case id, title, scenarioId, clock, equity, finished, updatedAt }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        sessionId = try? c.decode(LabID.self, forKey: .id)
        title = try? c.decode(String.self, forKey: .title)
        scenarioId = try? c.decode(String.self, forKey: .scenarioId)
        clock = try? c.decode(String.self, forKey: .clock)
        equity = try? c.decode(Double.self, forKey: .equity)
        finished = try? c.decode(Bool.self, forKey: .finished)
        updatedAt = try? c.decode(String.self, forKey: .updatedAt)
    }
}

nonisolated struct LabSimState: Decodable {
    let clock: String?
    let finished: Bool?
    let cash: Double?
    let equity: Double?
    let positions: [LabPosition]?
    let orders: [LabOrder]?
    let fills: [LabFill]?
    let trades: [LabTrade]?
    let equityCurve: [LabEquityPoint]?
    let assumptions: [String]?
    let daysTotal: Int?
    let dayIndex: Int?
}

nonisolated struct LabPosition: Decodable, Hashable {
    let symbol: String?
    let qty: Double?
    let avgCost: Double?
    let last: Double?
    let value: Double?
    let unrealised: Double?
}

nonisolated struct LabOrder: Decodable, Identifiable, Hashable {
    let id: String
    let symbol: String?
    let side: String?
    let qty: Double?
    let orderType: String?
    let limit: Double?
    let stop: Double?
    let tif: String?
    let placed: String?
    let status: String?
    let filledQty: Double?
    let avgPrice: Double?
    let reason: String?
    let thesis: String?
    let conviction: Double?
    var statusKind: LabOrderStatus { LabOrderStatus(raw: status) }
}

nonisolated struct LabCharges: Decodable, Hashable {
    let brokerage: Double?
    let stt: Double?
    let exchangeTxn: Double?
    let sebiFee: Double?
    let stampDuty: Double?
    let gst: Double?
    let total: Double?
}

nonisolated struct LabFill: Decodable, Hashable {
    let orderId: String?
    let symbol: String?
    let side: String?
    let qty: Double?
    let price: Double?
    let d: String?
    let charges: LabCharges?
    let slippageBps: Double?
}

nonisolated struct LabTrade: Decodable, Hashable {
    let symbol: String?
    let qty: Double?
    let entryDate: String?
    let exitDate: String?
    let entryOrderId: String?
    let exitOrderId: String?
    let pnl: Double?
    let ret: Double?
}

nonisolated struct LabEquityPoint: Decodable, Hashable {
    let d: String?
    let equity: Double?
    let cash: Double?
    let benchmark: Double?
}

nonisolated struct LabPerformance: Decodable, Hashable {
    let startCapital: Double?
    let finalEquity: Double?
    let totalReturn: Double?
    let cagr: Double?
    let annVol: Double?
    let sharpe: Double?
    let sortino: Double?
    let maxDrawdown: Double?
    let benchmarkReturn: Double?
    let excessReturn: Double?
    let turnoverX: Double?
    let costsInr: Double?
    let costDrag: Double?
    let trades: Int?
    let hitRate: Double?
    let profitFactor: Double?
    let avgHoldDays: Double?
    let sessions: Int?
    let score: Double?
}

nonisolated struct LabWatchRow: Decodable, Identifiable, Hashable {
    let symbol: String
    let listed: Bool?
    let date: String?
    let close: Double?
    let volume: Double?
    let chg1d: Double?
    let chg20d: Double?
    let stale: Bool?
    var id: String { symbol }
}

nonisolated struct LabProvenance: Decodable, Hashable {
    let source: String?
    let warnings: [String]?
    let benchmark: String?
    let rows: Int?
    let window: LabJSON?
}

// MARK: - History, autopsy, mentor

nonisolated struct LabHistory: Decodable {
    let symbol: String?
    let asof: String?
    let bars: [LabBar]?
}

nonisolated struct LabBar: Decodable, Identifiable, Hashable {
    let d: String
    let o: Double
    let h: Double
    let l: Double
    let c: Double
    let v: Double?
    var id: String { d }
    var date: Date { WireDate.dayFormatter.date(from: d) ?? .distantPast }
}

nonisolated struct LabAutopsyReport: Decodable {
    let clock: String?
    let trades: [LabAutopsy]?
    let counterfactuals: [LabCounterfactual]?
    let counterfactualNote: String?
    let behaviour: [LabFlag]?
    let performance: LabPerformance?
    let provenance: LabProvenance?
}

nonisolated struct LabAutopsy: Decodable, Hashable {
    let symbol: String?
    let qty: Double?
    let entryOrderId: String?
    let exitOrderId: String?
    let thesis: String?
    let plannedStop: Double?
    let plannedExit: Double?
    let conviction: Double?
    let knowable: LabKnowable?
    let process: LabProcess?
    let hindsight: LabHindsight?
    let verdict: LabQuadrantVerdict?
}

nonisolated struct LabKnowable: Decodable, Hashable {
    let asof: String?
    let barsAvailable: Int?
    let ret5d: Double?
    let ret20d: Double?
    let ret60d: Double?
    let vol20dAnn: Double?
    let ret5dZ: Double?
    let distFrom52wHigh: Double?
    let volumeVs20dAvg: Double?
    let benchmarkRet20d: Double?
    let newsVisible: [LabJSON]?
    let positionWeight: Double?
    let riskPerTrade: Double?
    let baseRate: LabBaseRate?
}

nonisolated struct LabBaseRate: Decodable, Hashable {
    let horizon: Int?
    let windows: Int?
    let beatBenchmarkShare: Double?
}

nonisolated struct LabProcess: Decodable, Hashable {
    let score: Double?
    let checks: [LabCheck]?
}

nonisolated struct LabCheck: Decodable, Hashable {
    let id: String?
    let passed: Bool?
    let text: String?
}

nonisolated struct LabHindsight: Decodable, Hashable {
    let entryDate: String?
    let exitDate: String?
    let sessionsHeld: Int?
    let returnNet: Double?
    let pnlNet: Double?
    let benchmarkReturn: Double?
    let excessReturn: Double?
    let maxAdverseExcursion: Double?
    let maxFavourableExcursion: Double?
    let feesInr: Double?
    let feesShareOfGross: Double?
    let moveInSigmas: Double?
}

nonisolated struct LabQuadrantVerdict: Decodable, Hashable {
    let quadrant: String?
    let text: String?
    var kind: LabQuadrant { LabQuadrant(raw: quadrant) }
}

nonisolated struct LabCounterfactual: Decodable, Hashable {
    let variant: String?
    let finalEquity: Double?
    let deltaVsActual: Double?
    let valid: Bool?
    let reason: String?
}

nonisolated struct LabFlag: Decodable, Hashable {
    let id: String?
    let severity: String?
    let evidence: [String: LabJSON]?
    let text: String?
    var severityKind: LabSeverity { LabSeverity(raw: severity) }
}

nonisolated struct LabMentorReply: Decodable, Hashable {
    let answer: String?
    let groundedOn: [String: LabJSON]?
    let mode: String?
    let disclaimer: String?
    var modeKind: LabMentorMode { LabMentorMode(raw: mode) }
}

// MARK: - Event explorer (POST /events/timeline)

nonisolated struct LabEventTimeline: Decodable {
    let symbol: String?
    let start: String?
    let end: String?
    let bars: [LabCloseBar]?
    let items: [LabEventItem]?
    let note: String?
    let provenance: LabProvenance?
}

nonisolated struct LabCloseBar: Decodable, Hashable {
    let d: String
    let c: Double
    let v: Double?
    var date: Date { WireDate.dayFormatter.date(from: d) ?? .distantPast }
}

nonisolated struct LabEventItem: Decodable, Hashable {
    let date: String?
    let kind: String?
    /// prices | exchange | source: what the item rests on.
    let evidence: String?
    let text: String?
    let sourceUrl: String?
    var kindValue: LabEventKind { LabEventKind(raw: kind) }
    var day: Date? { date.flatMap { WireDate.dayFormatter.date(from: $0) } }
}

// MARK: - Actions (append-only log)

nonisolated struct LabOrderDraft: Hashable {
    var symbol: String
    var side: String            // BUY | SELL
    var qty: Int
    var orderType: String       // MARKET | LIMIT | STOP
    var limit: Double?
    var stop: Double?
    var tif: String             // DAY | GTC
    var thesis: String
    var plannedStop: Double?
    var plannedExit: Double?
    var horizonDays: Int?
    var conviction: Double?     // 0...1

    /// Empty when the ticket can be sent; otherwise the first problem, in plain words.
    var problem: String? {
        if qty <= 0 { return "Enter a quantity above zero." }
        if thesis.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 { return "Write your thesis (at least 10 characters)." }
        if orderType == "LIMIT", (limit ?? 0) <= 0 { return "Enter a limit price." }
        if orderType == "STOP", (stop ?? 0) <= 0 { return "Enter a stop trigger price." }
        return nil
    }
}

nonisolated enum LabAction: Hashable {
    case order(LabOrderDraft)
    case cancel(orderId: String)
    case advance(days: Int)
    case note(String)

    var json: [String: Any] {
        switch self {
        case .order(let o):
            var out: [String: Any] = ["type": "order", "symbol": o.symbol, "side": o.side, "qty": o.qty,
                                      "order_type": o.orderType, "tif": o.tif, "thesis": o.thesis]
            if o.orderType == "LIMIT", let v = o.limit { out["limit"] = v }
            if o.orderType == "STOP", let v = o.stop { out["stop"] = v }
            if let v = o.plannedStop { out["planned_stop"] = v }
            if let v = o.plannedExit { out["planned_exit"] = v }
            if let v = o.horizonDays { out["horizon_days"] = v }
            if let v = o.conviction { out["conviction"] = v }
            return out
        case .cancel(let id): return ["type": "cancel", "order_id": id]
        case .advance(let days): return ["type": "advance", "days": days]
        case .note(let text): return ["type": "note", "text": text]
        }
    }
}

// MARK: - Hypothesis lab

nonisolated struct LabTemplates: Decodable {
    let templates: [LabTemplate]?
    let unavailableFieldsNote: String?
}

nonisolated struct LabTemplate: Decodable, Identifiable, Hashable {
    let id: String
    let title: String?
    let score: String?
    let horizon: Int?
    let program: String?
    let reference: String?
}

nonisolated struct LabCompileResult: Decodable, Hashable {
    let ok: Bool?
    let fingerprint: String?
    let nodes: Int?
    let outputs: [LabCompileOutput]?
    let error: String?
    let line: Int?
    let col: Int?
}

nonisolated struct LabCompileOutput: Decodable, Hashable {
    let name: String?
    let lineage: [String]?
    let warmupBars: Int?
    let availability: LabJSON?
}

nonisolated struct LabSpec: Decodable, Hashable {
    var question: String?
    var program: String?
    var score: String?
    var start: String?
    var end: String?
    var horizon: Int?
    var direction: Int?
    var universeN: Int?
    var useHoldout: Bool?
}

nonisolated struct LabTranslation: Decodable, Hashable {
    let spec: LabSpec?
    let explanation: String?
    let missingData: [String]?
    let mode: String?
}

nonisolated struct LabVerdict: Decodable, Hashable {
    let label: String?
    let text: String?
    let failedChecks: [String]?
    var kind: LabVerdictLabel { LabVerdictLabel(raw: label) }

    nonisolated private enum CodingKeys: String, CodingKey { case label, text, failedChecks }
    /// The ledger may send just the label string.
    init(from decoder: Decoder) throws {
        if let raw = try? decoder.singleValueContainer().decode(String.self) {
            label = raw
            text = nil
            failedChecks = nil
            return
        }
        let c = try decoder.container(keyedBy: CodingKeys.self)
        label = try? c.decode(String.self, forKey: .label)
        text = try? c.decode(String.self, forKey: .text)
        failedChecks = try? c.decode([String].self, forKey: .failedChecks)
    }
}

nonisolated struct LabExperimentResult: Decodable, Hashable {
    let periods: Int?
    let meanNames: Double?
    let meanIc: Double?
    let icHacT: Double?
    let icCi95: [Double?]?
    let icPositiveShare: Double?
    let topExcessGrossPerPeriod: Double?
    let topExcessNetPerPeriod: Double?
    let topMinusBottomPerPeriod: Double?
    let avgTurnover: Double?
    let netSharpeAnn: Double?
    let netSharpeCi95: [Double?]?
}

nonisolated struct LabSeriesPoint: Decodable, Hashable {
    let date: String
    let ic: Double?
    let topNet: Double?
    var day: Date { WireDate.dayFormatter.date(from: date) ?? .distantPast }
}

nonisolated struct LabBaseline: Decodable, Hashable {
    let meanIc: Double?
    let topExcessNetPerPeriod: Double?
    let icDiffMean: Double?
    let icDiffT: Double?
}

nonisolated struct LabDeflatedSharpe: Decodable, Hashable {
    let value: Double?
    let trials: Int?
    let note: String?
}

nonisolated struct LabSkeptic: Decodable, Hashable {
    let agent: String?
    let status: String?
    let finding: String?
    let evidence: [String: LabJSON]?
    let critical: Bool?
    var statusKind: LabSkepticStatus { LabSkepticStatus(raw: status) }
}

nonisolated struct LabCosts: Decodable, Hashable {
    let roundTrip: Double?
    let slippageBpsPerSide: Double?
    let note: String?
}

nonisolated struct LabHoldout: Decodable, Hashable {
    let result: LabExperimentResult?
    let note: String?
}

nonisolated struct LabExperimentReport: Decodable {
    let status: String?
    let error: String?
    let spec: LabSpec?
    let fingerprint: String?
    let lineage: [String]?
    let warmupBars: Int?
    let researchWindow: [String?]?
    let holdoutWindow: [String?]?
    let costs: LabCosts?
    let result: LabExperimentResult?
    let series: [LabSeriesPoint]?
    let permutationP: Double?
    let baselines: [String: LabBaseline]?
    let icByYear: [String: Double]?
    let deflatedSharpe: LabDeflatedSharpe?
    let skeptics: [LabSkeptic]?
    let verdict: LabVerdict?
    let holdout: LabHoldout?
    let provenance: LabProvenance?
}

/// A stored experiment: `{id, created_at, report: {...}}` or the report fields inline.
nonisolated struct LabExperimentRecord: Decodable {
    let id: LabID?
    let createdAt: String?
    let question: String?
    let trialsSoFar: Int?
    let report: LabExperimentReport

    nonisolated private enum CodingKeys: String, CodingKey { case id, createdAt, question, trialsSoFar, report }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try? c.decode(LabID.self, forKey: .id)
        createdAt = try? c.decode(String.self, forKey: .createdAt)
        question = try? c.decode(String.self, forKey: .question)
        trialsSoFar = try? c.decode(Int.self, forKey: .trialsSoFar)
        report = try (try? c.decode(LabExperimentReport.self, forKey: .report)) ?? LabExperimentReport(from: decoder)
    }
}

nonisolated struct LabExperimentSummary: Decodable, Identifiable, Hashable {
    let experimentId: LabID?
    let question: String?
    let score: String?
    let createdAt: String?
    let status: String?
    let verdict: LabVerdict?
    let meanIc: Double?
    var id: String { experimentId?.value ?? "" }

    nonisolated private enum CodingKeys: String, CodingKey { case id, question, score, createdAt, status, verdict, meanIc }
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        experimentId = try? c.decode(LabID.self, forKey: .id)
        question = try? c.decode(String.self, forKey: .question)
        score = try? c.decode(String.self, forKey: .score)
        createdAt = try? c.decode(String.self, forKey: .createdAt)
        status = try? c.decode(String.self, forKey: .status)
        verdict = try? c.decode(LabVerdict.self, forKey: .verdict)
        meanIc = try? c.decode(Double.self, forKey: .meanIc)
    }
}

// MARK: - Trader school

nonisolated struct LabCurriculum: Decodable {
    let tracks: [String]?
    let lessons: [LabLessonSummary]?
}

nonisolated struct LabLessonSummary: Decodable, Identifiable, Hashable {
    let id: String
    let track: String?
    let title: String?
    let minutes: Int?
    let prereqs: [String]?
    let concepts: [String]?
    let summary: String?
}

nonisolated struct LabLesson: Decodable, Identifiable {
    let id: String
    let track: String?
    let title: String?
    let minutes: Int?
    let concepts: [String]?
    let summary: String?
    let body: [LabLessonSection]?
    let quiz: [LabQuizQuestion]?
}

nonisolated struct LabLessonSection: Decodable, Hashable {
    let kind: String?
    let md: String?
    let latex: String?
    let widget: String?
    var kindValue: LabSectionKind { LabSectionKind(raw: kind) }
}

nonisolated struct LabQuizQuestion: Decodable, Identifiable, Hashable {
    let id: String
    let q: String?
    let choices: [String]?
}

nonisolated struct LabGrade: Decodable, Hashable {
    let score: Double?
    let passed: Bool?
    let perQuestion: [LabGradedQuestion]?
}

nonisolated struct LabGradedQuestion: Decodable, Hashable {
    let id: String?
    let correct: Bool?
    let answer: Int?
    let explain: String?
}

nonisolated struct LabProgress: Decodable {
    let mastered: [String]?
    let completed: [String]?
}

nonisolated struct LabNextLessons: Decodable {
    let lessons: [LabRecommendation]?
}

nonisolated struct LabRecommendation: Decodable, Hashable, Identifiable {
    let lessonId: String?
    let title: String?
    let track: String?
    let reason: String?
    var id: String { lessonId ?? title ?? "" }
}

// MARK: - School widgets (pure math, unit-tested)

/// Delivery-equity charges with fixed NSE rates (schedule effective 01-Mar-2026), an
/// approximation for teaching: the simulator itself uses the dated schedule per fill.
nonisolated enum LabCostEstimate {
    static let sttRate = 0.001             // each side, delivery
    static let exchangeRate = 0.0000307    // NSE transaction charge
    static let sebiPerCrore = 10.0
    static let stampBuyRate = 0.00015      // buy side only
    static let gstRate = 0.18              // on brokerage + exchange + SEBI
    static let brokerageFlat = 20.0
    static let brokeragePct = 0.0003       // min(flat, pct * value)

    nonisolated struct Breakdown: Equatable {
        var brokerage = 0.0, stt = 0.0, exchange = 0.0, sebi = 0.0, stamp = 0.0, gst = 0.0
        var total: Double { brokerage + stt + exchange + sebi + stamp + gst }
    }

    static func charges(value: Double, buy: Bool) -> Breakdown {
        guard value > 0 else { return Breakdown() }
        var b = Breakdown()
        b.brokerage = min(brokerageFlat, brokeragePct * value)
        b.stt = value * sttRate
        b.exchange = value * exchangeRate
        b.sebi = value / 1e7 * sebiPerCrore
        b.stamp = buy ? value * stampBuyRate : 0
        b.gst = gstRate * (b.brokerage + b.exchange + b.sebi)
        return b
    }

    /// Future value of `principal` compounding annually at `rate` for `years`.
    static func compound(principal: Double, rate: Double, years: Int) -> [Double] {
        (0...max(years, 0)).map { principal * pow(1 + rate, Double($0)) }
    }
}
