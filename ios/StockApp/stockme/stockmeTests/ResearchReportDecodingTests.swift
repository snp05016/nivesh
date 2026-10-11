import XCTest
@testable import stockme

/// Spec 11.3: the `research.v1` contract fixtures decode through
/// `NetworkManager.researchDecoder()`, every block the fixture carries is non-nil,
/// display strings arrive unchanged, unknown enum strings fall back to `.unknown`,
/// and HTTP statuses map to the right `ResearchFetchResult`.
@MainActor
final class ResearchReportDecodingTests: XCTestCase {

    /// docs/research/contract/fixtures, reached from this file: the test directory is
    /// four levels below the repository root (ios/StockApp/stockme/stockmeTests).
    private static let fixturesDir = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // stockmeTests
        .deletingLastPathComponent()   // stockme
        .deletingLastPathComponent()   // StockApp
        .deletingLastPathComponent()   // ios
        .deletingLastPathComponent()   // repository root
        .appendingPathComponent("docs/research/contract/fixtures")

    private func fixtureData(_ name: String) throws -> Data {
        try Data(contentsOf: Self.fixturesDir.appendingPathComponent("\(name).json"))
    }

    private func decode(_ data: Data) throws -> ResearchReport {
        try NetworkManager.researchDecoder().decode(ResearchReport.self, from: data)
    }

    /// Value at a dotted path ("risk.var_1d.0.var_pct.display") of the raw fixture JSON.
    private func raw(_ data: Data, _ path: String) throws -> Any? {
        var node: Any? = try JSONSerialization.jsonObject(with: data)
        for key in path.split(separator: ".").map(String.init) {
            if let index = Int(key), let list = node as? [Any] {
                node = index < list.count ? list[index] : nil
            } else {
                node = (node as? [String: Any])?[key]
            }
        }
        return node
    }

    /// The decoded string equals the fixture's non-null string at `path`.
    private func assertSame(_ decoded: String?, _ data: Data, _ path: String,
                            file: StaticString = #filePath, line: UInt = #line) throws {
        let expected = try XCTUnwrap(try raw(data, path) as? String, "fixture has no string at \(path)",
                                     file: file, line: line)
        XCTAssertEqual(decoded, expected, path, file: file, line: line)
    }

    /// Blocks every report carries, whatever its tier or origin.
    private func assertCoreBlocks(_ r: ResearchReport, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(r.schemaVersion, "research.v1", file: file, line: line)
        XCTAssertNotNil(r.reportId, file: file, line: line)
        XCTAssertNotNil(r.engineVersion, file: file, line: line)
        XCTAssertNotNil(r.origin, file: file, line: line)
        XCTAssertNotNil(r.status, file: file, line: line)
        XCTAssertNotNil(r.companyName, file: file, line: line)
        XCTAssertNotNil(r.asOf.computedAt, file: file, line: line)
        XCTAssertNotNil(r.snapshot?.lastClose, file: file, line: line)
        XCTAssertNotNil(r.snapshot?.marketCapCr, file: file, line: line)
        XCTAssertEqual(r.outlooks?.map(\.horizonDays), [21, 63], file: file, line: line)
        XCTAssertEqual(r.factorProfile?.families?.map(\.family),
                       [.momentum, .reversal, .risk, .liquidity, .trend], file: file, line: line)
        XCTAssertNotNil(r.risk?.volEwmaAnnPct, file: file, line: line)
        XCTAssertNotNil(r.risk?.beta?.raw, file: file, line: line)
        XCTAssertNotNil(r.risk?.varStatus, file: file, line: line)
        XCTAssertNotNil(r.risk?.var1d, file: file, line: line)
        XCTAssertNotNil(r.risk?.drawdown?.max1y, file: file, line: line)
        XCTAssertFalse(r.risk?.drawdownSeries?.points?.isEmpty ?? true, file: file, line: line)
        XCTAssertEqual(r.risk?.returnRanges?.map(\.horizonDays), [21, 63], file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.status, file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.valuation?.peTtm, file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.quality?.roePct, file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.piotroski?.fScore, file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.altmanZEm?.value, file: file, line: line)
        XCTAssertNotNil(r.fundamentals?.beneishM?.value, file: file, line: line)
        XCTAssertNotNil(r.modelCard?.labelDefinition, file: file, line: line)
        XCTAssertFalse(r.modelCard?.limitations?.isEmpty ?? true, file: file, line: line)
        XCTAssertEqual(r.modelCard?.horizons?.count, 2, file: file, line: line)
        XCTAssertNotNil(r.provenance?.dataSnapshotId, file: file, line: line)
        XCTAssertFalse(r.provenance?.sources?.isEmpty ?? true, file: file, line: line)
        XCTAssertEqual(r.pipeline?.count, 7, file: file, line: line)
    }

    private func assertBackendBlocks(_ r: ResearchReport, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertNotNil(r.staleness?.state, file: file, line: line)
        XCTAssertNotNil(r.narrative?.summary, file: file, line: line)
        XCTAssertEqual(r.narrative?.sections?.count, 3, file: file, line: line)
        XCTAssertNotNil(r.liveTrackRecord?.horizons, file: file, line: line)
        XCTAssertNotNil(r.compliance?.disclaimerText, file: file, line: line)
        XCTAssertNotNil(r.compliance?.aiDisclosure, file: file, line: line)
        XCTAssertNotNil(r.outlooks?.first?.tierText, file: file, line: line)
        XCTAssertNotNil(r.modelCard?.horizons?.first?.tierText, file: file, line: line)
    }

    // MARK: - Fixtures

    func testNoEdgeFixtureDecodes() throws {
        let data = try fixtureData("no_edge")
        let r = try decode(data)
        assertCoreBlocks(r)
        assertBackendBlocks(r)

        try assertSame(r.symbol, data, "symbol")
        try assertSame(r.asOf.marketDate, data, "as_of.market_date")
        try assertSame(r.snapshot?.lastClose?.display, data, "snapshot.last_close.display")
        try assertSame(r.snapshot?.marketCapCr?.display, data, "snapshot.market_cap_cr.display")
        try assertSame(r.snapshot?.excess12mVsNifty50Pp?.display, data, "snapshot.excess_12m_vs_nifty50_pp.display")
        try assertSame(r.risk?.drawdown?.max3y?.display, data, "risk.drawdown.max_3y_pct.display")
        try assertSame(r.risk?.drawdown?.daysSincePeak?.display, data, "risk.drawdown.days_since_peak.display")
        try assertSame(r.risk?.var1d?.first?.varPct?.display, data, "risk.var_1d.0.var_pct.display")
        try assertSame(r.risk?.returnRanges?.first?.low?.display, data, "risk.return_ranges.0.low_pct.display")
        try assertSame(r.risk?.returnRanges?.first?.text, data, "risk.return_ranges.0.text")
        try assertSame(r.factorProfile?.families?.first?.pctl?.display, data, "factor_profile.families.0.pctl.display")
        try assertSame(r.factorProfile?.families?.first?.metrics?.first?.value?.display, data,
                       "factor_profile.families.0.metrics.0.value.display")
        try assertSame(r.fundamentals?.valuation?.peTtm?.display, data, "fundamentals.valuation.pe_ttm.display")
        try assertSame(r.fundamentals?.altmanZEm?.value?.display, data, "fundamentals.altman_z_em.value.display")
        try assertSame(r.outlooks?.first?.tierText, data, "outlooks.0.tier_text")
        try assertSame(r.outlooks?.first?.event, data, "outlooks.0.event")
        try assertSame(r.narrative?.summary, data, "narrative.summary")
        try assertSame(r.compliance?.disclaimerText, data, "compliance.disclaimer_text")

        let lastClose = try XCTUnwrap(r.snapshot?.lastClose)
        XCTAssertEqual(lastClose.unit, .inr)
        XCTAssertEqual(lastClose.status, .ok)
        XCTAssertEqual(lastClose.source, .nseBhavcopy)
        XCTAssertEqual(lastClose.value, try raw(data, "snapshot.last_close.value") as? Double)
        XCTAssertEqual(r.outlooks?.map(\.evidenceTier), [.noReliableEdge, .noReliableEdge])
        XCTAssertEqual(r.outlooks?.first?.reasonCodes, ["gate_failed:G1", "gate_failed:G2"])
        XCTAssertNotNil(r.outlooks?.first?.predictionId)
        XCTAssertEqual(r.staleness?.state, .fresh)
        XCTAssertEqual(r.narrative?.status, .llmValidated)
        XCTAssertEqual(r.compliance?.outlookDisplay, .tierOnly)
        XCTAssertEqual(r.risk?.varStatus, .ok)
        XCTAssertEqual(r.risk?.var1d?.count, (try raw(data, "risk.var_1d") as? [Any])?.count)
        XCTAssertEqual(r.risk?.var1d?.first?.method, .historical500d)

        let points = try XCTUnwrap(r.risk?.drawdownSeries?.points)
        let rawPoints = try XCTUnwrap(try raw(data, "risk.drawdown_series.points") as? [[Any]])
        XCTAssertEqual(points.count, rawPoints.count)
        XCTAssertEqual(points.first?.date, rawPoints.first?.first as? String)
        XCTAssertEqual(points.first?.pct, rawPoints.first?.last as? Double)
    }

    func testValidatedCohortFixtureDecodesWithBackendBlocksNil() throws {
        let data = try fixtureData("validated_cohort")
        let r = try decode(data)
        assertCoreBlocks(r)

        XCTAssertNil(r.staleness)
        XCTAssertNil(r.narrative)
        XCTAssertNil(r.liveTrackRecord)
        XCTAssertNil(r.compliance)
        XCTAssertEqual(r.outlooks?.map(\.evidenceTier), [.validatedEdge, .weakEvidence])
        XCTAssertEqual(r.outlooks?.compactMap(\.tierText), [])
        XCTAssertEqual(r.outlooks?.compactMap(\.predictionId), [])
        XCTAssertEqual(r.modelCard?.horizons?.compactMap(\.tierText), [])

        // Financial company: Altman Z'' is not applicable and carries no number.
        XCTAssertEqual(r.fundamentals?.isFinancial, true)
        let altman = try XCTUnwrap(r.fundamentals?.altmanZEm)
        XCTAssertEqual(altman.applicable, false)
        XCTAssertEqual(altman.value?.status, .unavailable)
        XCTAssertEqual(altman.value?.reason, .notApplicableFinancials)
        XCTAssertNil(altman.value?.display)
        XCTAssertNil(altman.value?.value)

        try assertSame(r.snapshot?.lastClose?.display, data, "snapshot.last_close.display")
        try assertSame(r.risk?.drawdown?.max3y?.display, data, "risk.drawdown.max_3y_pct.display")
    }

    func testOutOfUniverseDegradedFixtureDecodes() throws {
        let data = try fixtureData("out_of_universe_degraded")
        let r = try decode(data)
        assertCoreBlocks(r)
        assertBackendBlocks(r)

        XCTAssertEqual(r.status, .degraded)
        XCTAssertEqual(r.origin, .onDemand)
        XCTAssertEqual(r.degradedReasons, try raw(data, "degraded_reasons") as? [String])
        XCTAssertNil(r.sector)
        XCTAssertEqual(r.outlooks?.map(\.evidenceTier), [.outOfUniverse, .outOfUniverse])
        XCTAssertEqual(r.staleness?.state, .stale)
        XCTAssertEqual(r.staleness?.sessionsOld, 1)

        XCTAssertEqual(r.risk?.varStatus, .backtestFailed)
        XCTAssertEqual(r.risk?.var1d?.count, 0)

        let range63 = try XCTUnwrap(r.risk?.returnRanges?.last)
        XCTAssertEqual(range63.low?.status, .unavailable)
        XCTAssertEqual(range63.low?.reason, .insufficientHistory)
        XCTAssertNil(range63.low?.display)
        XCTAssertNil(range63.text)
        try assertSame(r.risk?.returnRanges?.first?.text, data, "risk.return_ranges.0.text")
        try assertSame(r.risk?.returnRanges?.first?.high?.display, data, "risk.return_ranges.0.high_pct.display")

        XCTAssertEqual(r.fundamentals?.status, .unavailable)
        XCTAssertEqual(r.fundamentals?.reason, .sourceUnavailable)
        XCTAssertNil(r.fundamentals?.valuation?.peTtm?.display)
        XCTAssertEqual(r.provenance?.sources?.map(\.status), [.ok, .failed])
        XCTAssertEqual(r.pipeline?.first(where: { $0.stage == .fundamentals })?.status, .failed)

        try assertSame(r.snapshot?.lastClose?.display, data, "snapshot.last_close.display")
        try assertSame(r.outlooks?.first?.tierText, data, "outlooks.0.tier_text")
    }

    // MARK: - Leniency

    func testUnknownEnumStringsDecodeToUnknown() throws {
        var text = try XCTUnwrap(String(data: try fixtureData("no_edge"), encoding: .utf8))
        let mutations = [
            (#""evidence_tier": "no_reliable_edge""#, #""evidence_tier": "some_future_tier""#),
            (#""var_status": "ok""#, #""var_status": "partially_ok""#),
            (#""unit": "inr""#, #""unit": "usd""#),
            (#""state": "fresh""#, #""state": "ancient""#),
            (#""source": "nse_bhavcopy""#, #""source": "bse_bhavcopy""#),
            (#""id": "nse_bhavcopy""#, #""id": "bse_bhavcopy""#),
            (#""outlook_display": "tier_only""#, #""outlook_display": "something_new""#),
            (#""family": "momentum""#, #""family": "value""#),
            (#""status": "llm_validated""#, #""status": "human_written""#),
        ]
        for (from, to) in mutations {
            XCTAssertNotNil(text.range(of: from), "fixture no longer contains \(from)")
            text = text.replacingOccurrences(of: from, with: to)
        }

        let r = try decode(Data(text.utf8))
        XCTAssertEqual(r.outlooks?.first?.evidenceTier, .unknown)
        XCTAssertEqual(r.risk?.varStatus, .unknown)
        XCTAssertEqual(r.snapshot?.lastClose?.unit, .unknown)
        XCTAssertEqual(r.snapshot?.lastClose?.source, .unknown)
        XCTAssertEqual(r.staleness?.state, .unknown)
        XCTAssertEqual(r.compliance?.outlookDisplay, .unknown)
        XCTAssertEqual(r.factorProfile?.families?.first?.family, .unknown)
        XCTAssertEqual(r.narrative?.status, .unknown)
        XCTAssertEqual(r.provenance?.sources?.first?.id, .unknown)
        // Untouched values still decode normally.
        XCTAssertEqual(r.snapshot?.marketCapCr?.unit, .inrCrore)
    }

    func testOnlySchemaVersionSymbolAndAsOfAreRequired() throws {
        let minimal = #"{"schema_version":"research.v1","symbol":"TCS","as_of":{"market_date":"2026-10-09"}}"#
        let r = try decode(Data(minimal.utf8))
        XCTAssertEqual(r.symbol, "TCS")
        XCTAssertEqual(r.asOf.marketDate, "2026-10-09")
        XCTAssertNil(r.snapshot)
        XCTAssertNil(r.outlooks)
        XCTAssertNil(r.risk)

        let noSymbol = #"{"schema_version":"research.v1","as_of":{"market_date":"2026-10-09"}}"#
        XCTAssertThrowsError(try decode(Data(noSymbol.utf8)))
    }

    // MARK: - HTTP status mapping (stubbed; nothing reaches the network)

    func testFetchMapsStatusesToResults() async throws {
        let nm = NetworkManager.shared
        let savedToken = nm.authToken
        let savedSession = nm.session
        defer { nm.authToken = savedToken; nm.session = savedSession }
        nm.authToken = "a.b.c"
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [ResearchStubProtocol.self]
        nm.session = AuthAwareSession(base: URLSession(configuration: config))

        let base = "/api/v1/research/stocks/"
        ResearchStubProtocol.reset(routes: [
            base + "DEMOIND": (200, try fixtureData("no_edge")),
            base + "NEWCO": (404, Data(#"{"code":"NOT_COVERED","compute_available":true}"#.utf8)),
            base + "NEWCO/compute": (200, try fixtureData("out_of_universe_degraded")),
            base + "NOPE": (404, Data(#"{"detail":{"code":"UNKNOWN_SYMBOL"}}"#.utf8)),
            base + "OFF": (404, Data(#"{"code":"RESEARCH_DISABLED"}"#.utf8)),
            base + "SHADOW": (403, Data("{}".utf8)),
            base + "AUTH": (401, Data("{}".utf8)),
            base + "BOOM": (500, Data("{}".utf8)),
        ])

        guard case .report(let report) = try await nm.fetchResearchReport(symbol: "demoind.ns") else {
            return XCTFail("200 should decode a report")
        }
        XCTAssertEqual(report.symbol, "DEMOIND")

        guard case .notCovered(let computeAvailable) = try await nm.fetchResearchReport(symbol: "NEWCO") else {
            return XCTFail("404 NOT_COVERED should map to notCovered")
        }
        XCTAssertTrue(computeAvailable)

        guard case .report(let computed) = try await nm.computeResearchReport(symbol: "NEWCO") else {
            return XCTFail("compute 200 should decode a report")
        }
        XCTAssertEqual(computed.origin, .onDemand)

        guard case .unknownSymbol = try await nm.fetchResearchReport(symbol: "NOPE") else {
            return XCTFail("404 UNKNOWN_SYMBOL should map to unknownSymbol")
        }
        guard case .disabled = try await nm.fetchResearchReport(symbol: "OFF") else {
            return XCTFail("404 RESEARCH_DISABLED should map to disabled")
        }
        guard case .disabled = try await nm.fetchResearchReport(symbol: "SHADOW") else {
            return XCTFail("403 should map to disabled")
        }
        guard case .signedOut = try await nm.fetchResearchReport(symbol: "AUTH") else {
            return XCTFail("401 should map to signedOut")
        }
        do {
            _ = try await nm.fetchResearchReport(symbol: "BOOM")
            XCTFail("500 should throw")
        } catch {}

        let calls = ResearchStubProtocol.requests.filter { ($0.url?.path ?? "").contains(base) }
        XCTAssertFalse(calls.isEmpty)
        for req in calls {
            let url = req.url?.absoluteString ?? "?"
            XCTAssertEqual(req.value(forHTTPHeaderField: "Authorization"), "Bearer a.b.c", url)
            XCTAssertTrue((req.value(forHTTPHeaderField: "X-Nivesh-Client") ?? "").hasPrefix("ios/"), url)
        }
        XCTAssertEqual(calls.first(where: { $0.url?.path.hasSuffix("/compute") == true })?.httpMethod, "POST")
    }
}

/// Answers research paths from a route table and everything else with 200 `{}`.
private final class ResearchStubProtocol: URLProtocol {
    private static let lock = NSLock()
    private static var routes: [String: (Int, Data)] = [:]
    private static var captured: [URLRequest] = []

    static var requests: [URLRequest] {
        lock.lock(); defer { lock.unlock() }
        return captured
    }

    static func reset(routes newRoutes: [String: (Int, Data)]) {
        lock.lock(); defer { lock.unlock() }
        routes = newRoutes
        captured = []
    }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        Self.lock.lock()
        Self.captured.append(request)
        let path = request.url?.path ?? ""
        let route = Self.routes.first(where: { path.hasSuffix($0.key) })?.value
        Self.lock.unlock()
        let (status, body) = route ?? (200, Data("{}".utf8))
        let response = HTTPURLResponse(url: request.url!, statusCode: status, httpVersion: nil,
                                       headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}
