import Foundation

// MARK: - Lab (backend /api/v1/research-lab, docs/platform/api-contract.md)
//
// Every call goes through `_send` (authRequest: Bearer + correlation headers) and
// `NetworkError.ensureOK`, so a 422 replay rejection reaches the user as the server's
// plain-text `detail` ("action 3: not enough cash"). Transport failures become
// `.connectionFailed`; cancellation propagates unchanged.

extension NetworkManager {

    nonisolated static let labBase = "/api/v1/research-lab"

    /// The only decoder for Lab payloads: models are named after camel-cased wire keys.
    nonisolated static func labDecoder() -> JSONDecoder {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        return d
    }

    private func labData(_ path: String, method: String = "GET", json: [String: Any]? = nil,
                         timeout: TimeInterval = 30) async throws -> Data {
        let data: Data, http: HTTPURLResponse
        do {
            (data, http) = try await labSend(Self.labBase + path, method: method, json: json, timeout: timeout)
        } catch let error as URLError where error.code != .cancelled {
            throw NetworkError.connectionFailed
        }
        try NetworkError.ensureOK(data: data, response: http)
        return data
    }

    /// DEBUG builds only: `-LabDevURL http://127.0.0.1:8899` (a launch argument) sends Lab
    /// calls to a local development gateway; every other call keeps the normal server.
    nonisolated static var labDevURL: String? {
        #if DEBUG
        return UserDefaults.standard.string(forKey: "LabDevURL")
        #else
        return nil
        #endif
    }

    private func labSend(_ path: String, method: String, json: [String: Any]?,
                         timeout: TimeInterval) async throws -> (Data, HTTPURLResponse) {
        guard let dev = Self.labDevURL else {
            return try await _send(path, method: method, json: json, timeout: timeout)
        }
        guard let url = URL(string: dev + path) else { throw NetworkError.invalidURL }
        var req = authRequest(url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        if let json {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONSerialization.data(withJSONObject: json)
        }
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw NetworkError.invalidResponse }
        return (data, http)
    }

    private func lab<T: Decodable>(_ type: T.Type, _ path: String, method: String = "GET",
                                   json: [String: Any]? = nil, timeout: TimeInterval = 30) async throws -> T {
        let data = try await labData(path, method: method, json: json, timeout: timeout)
        do { return try Self.labDecoder().decode(T.self, from: data) }
        catch { throw NetworkError.decodingError(String(describing: error)) }
    }

    // MARK: Time machine

    func labScenarios() async throws -> LabScenarioCatalog {
        try await lab(LabScenarioCatalog.self, "/scenarios")
    }

    func labUniverse(start: String, n: Int = 20) async throws -> LabUniverse {
        try await lab(LabUniverse.self, "/universe?start=\(start.urlQueryValue)&n=\(n)")
    }

    func labCreateSession(title: String?, scenarioId: String?, config: LabSimConfig) async throws -> LabSession {
        var body: [String: Any] = ["config": config.json]
        if let title { body["title"] = title }
        if let scenarioId { body["scenario_id"] = scenarioId }
        return try await lab(LabSession.self, "/sessions", method: "POST", json: body, timeout: 60)
    }

    func labSessions() async throws -> LabList<LabSessionSummary> {
        try await lab(LabList<LabSessionSummary>.self, "/sessions")
    }

    func labSession(id: String) async throws -> LabSession {
        try await lab(LabSession.self, "/sessions/\(id.urlQueryValue)", timeout: 60)
    }

    /// Appends one action. Returns the replayed session when the backend sends it back,
    /// nil when it only acknowledges (the caller then re-reads the session).
    func labPostAction(sessionId: String, action: LabAction, clientActionId: String) async throws -> LabSession? {
        let data = try await labData("/sessions/\(sessionId.urlQueryValue)/actions", method: "POST",
                                     json: ["action": action.json, "client_action_id": clientActionId], timeout: 60)
        guard let session = try? Self.labDecoder().decode(LabSession.self, from: data), session.state != nil else { return nil }
        return session
    }

    func labHistory(sessionId: String, symbol: String, bars: Int = 120) async throws -> LabHistory {
        try await lab(LabHistory.self, "/sessions/\(sessionId.urlQueryValue)/history", method: "POST",
                      json: ["symbol": symbol, "bars": bars])
    }

    func labAutopsy(sessionId: String, orderId: String?) async throws -> LabAutopsyReport {
        let query = orderId.map { "?order_id=\($0.urlQueryValue)" } ?? ""
        return try await lab(LabAutopsyReport.self, "/sessions/\(sessionId.urlQueryValue)/autopsy\(query)", timeout: 60)
    }

    func labMentor(sessionId: String, question: String, orderId: String?) async throws -> LabMentorReply {
        var body: [String: Any] = ["question": question]
        if let orderId { body["order_id"] = orderId }
        return try await lab(LabMentorReply.self, "/sessions/\(sessionId.urlQueryValue)/mentor", method: "POST",
                             json: body, timeout: 60)
    }

    func labDeleteSession(id: String) async throws {
        _ = try await labData("/sessions/\(id.urlQueryValue)", method: "DELETE")
    }

    func labEventTimeline(symbol: String, start: String, end: String) async throws -> LabEventTimeline {
        try await lab(LabEventTimeline.self, "/events/timeline", method: "POST",
                      json: ["symbol": symbol, "start": start, "end": end], timeout: 60)
    }

    // MARK: Hypothesis lab

    func labTemplates() async throws -> LabTemplates {
        try await lab(LabTemplates.self, "/research/templates")
    }

    func labCompile(program: String) async throws -> LabCompileResult {
        try await lab(LabCompileResult.self, "/research/compile", method: "POST", json: ["program": program])
    }

    func labTranslate(question: String) async throws -> LabTranslation {
        try await lab(LabTranslation.self, "/research/translate", method: "POST", json: ["question": question], timeout: 60)
    }

    /// The server fills `trials_so_far` from the user's ledger. Permutation tests are slow.
    func labRunExperiment(spec: [String: Any]) async throws -> LabExperimentRecord {
        try await lab(LabExperimentRecord.self, "/research/experiments", method: "POST", json: spec, timeout: 180)
    }

    func labExperiments() async throws -> LabList<LabExperimentSummary> {
        try await lab(LabList<LabExperimentSummary>.self, "/research/experiments")
    }

    func labExperiment(id: String) async throws -> LabExperimentRecord {
        try await lab(LabExperimentRecord.self, "/research/experiments/\(id.urlQueryValue)")
    }

    // MARK: Trader school

    func labCurriculum() async throws -> LabCurriculum {
        try await lab(LabCurriculum.self, "/school/curriculum")
    }

    func labLesson(id: String) async throws -> LabLesson {
        try await lab(LabLesson.self, "/school/lessons/\(id.urlQueryValue)")
    }

    func labGrade(lessonId: String, answers: [Int]) async throws -> LabGrade {
        try await lab(LabGrade.self, "/school/lessons/\(lessonId.urlQueryValue)/grade", method: "POST",
                      json: ["answers": answers])
    }

    func labProgress() async throws -> LabProgress {
        try await lab(LabProgress.self, "/school/progress")
    }

    func labNextLessons() async throws -> LabNextLessons {
        try await lab(LabNextLessons.self, "/school/next")
    }
}
