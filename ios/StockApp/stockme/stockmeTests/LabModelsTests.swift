import XCTest
@testable import stockme

/// Lab payloads (docs/platform/api-contract.md) decode with `NetworkManager.labDecoder()`,
/// tolerate unknown enum values, and the pure helpers do the right arithmetic.
@MainActor
final class LabModelsTests: XCTestCase {

    private func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try NetworkManager.labDecoder().decode(T.self, from: Data(json.utf8))
    }

    // MARK: - Session payload

    private let sessionJSON = """
    {"id": 42, "title": "Covid crash", "scenario_id": "covid-2020", "created_at": "2026-10-01T10:00:00Z",
     "state": {"clock": "2020-03-02", "finished": false, "cash": 812345.5, "equity": 990000.1,
       "positions": [{"symbol": "RELIANCE", "qty": 10, "avg_cost": 1300.5, "last": 1290, "value": 12900, "unrealised": -105}],
       "orders": [{"id": "o1", "symbol": "TCS", "side": "BUY", "qty": 5, "order_type": "LIMIT", "limit": 2000,
                   "tif": "GTC", "placed": "2020-02-28", "status": "OPEN", "filled_qty": 0},
                  {"id": "o2", "symbol": "TCS", "side": "SELL", "qty": 5, "order_type": "MARKET", "status": "HALTED_NEW"}],
       "fills": [{"order_id": "o0", "symbol": "RELIANCE", "side": "BUY", "qty": 10, "price": 1300.5, "d": "2020-02-27",
                  "charges": {"brokerage": 3.9, "stt": 13, "exchange_txn": 0.4, "sebi_fee": 0.01, "stamp_duty": 1.95,
                              "gst": 0.77, "total": 20.03, "sources": ["x"]}, "slippage_bps": 4.2, "ref_price": 1299}],
       "trades": [], "equity_curve": [{"d": "2020-02-03", "equity": 1000000, "cash": 1000000, "benchmark": 12000}],
       "events": [{"d": "2020-02-27", "event": "fill", "order_id": "o0"}],
       "assumptions": ["Fills at next close"], "days_total": 103, "day_index": 20},
     "performance": {"start_capital": 1000000, "final_equity": 990000.1, "total_return": -0.01, "max_drawdown": 0.04,
                     "turnover_x": 0.1, "costs_inr": 20.03, "trades": 0, "sessions": 20},
     "watchlist": [{"symbol": "RELIANCE", "listed": true, "date": "2020-03-02", "close": 1290, "volume": 1200000,
                    "chg_1d": -0.012, "chg_20d": null, "stale": false},
                   {"symbol": "NEWCO", "listed": false}],
     "provenance": {"source": "local_csv", "warnings": ["Development dataset"], "rows": 1000, "window": ["2020-01-01", "2020-06-30"]},
     "benchmark": "^NSEI",
     "news": [{"date": "2020-03-01", "symbol": null, "title": "Markets fall", "source": "BS", "url": "https://example.com/a"}],
     "future_field": {"anything": [1, 2]}}
    """

    func testSessionPayloadDecodes() throws {
        let s = try decode(LabSession.self, sessionJSON)
        XCTAssertEqual(s.id?.value, "42")
        XCTAssertEqual(s.scenarioId, "covid-2020")
        XCTAssertEqual(s.state?.clock, "2020-03-02")
        XCTAssertEqual(s.state?.dayIndex, 20)
        XCTAssertEqual(s.state?.daysTotal, 103)
        XCTAssertEqual(s.state?.positions?.first?.avgCost, 1300.5)
        XCTAssertEqual(s.state?.fills?.first?.charges?.exchangeTxn, 0.4)
        XCTAssertEqual(s.performance?.turnoverX, 0.1)
        XCTAssertEqual(s.watchlist?.first?.chg1d, -0.012)
        XCTAssertNil(s.watchlist?.first?.chg20d)
        XCTAssertEqual(s.watchlist?.last?.listed, false)
        XCTAssertEqual(s.provenance?.warnings, ["Development dataset"])
        XCTAssertEqual(s.news?.first?.title, "Markets fall")
        XCTAssertNil(s.news?.first?.symbol)
    }

    func testUnknownOrderStatusFallsBack() throws {
        let orders = try XCTUnwrap(try decode(LabSession.self, sessionJSON).state?.orders)
        XCTAssertEqual(orders[0].statusKind, .open)
        XCTAssertTrue(orders[0].statusKind.isWorking)
        XCTAssertEqual(orders[1].statusKind, .unknown)
        XCTAssertFalse(orders[1].statusKind.isWorking)
    }

    func testSessionWithoutNewsStillDecodes() throws {
        let s = try decode(LabSession.self, #"{"id": "abc", "state": {"clock": "2020-01-02"}}"#)
        XCTAssertEqual(s.id?.value, "abc")
        XCTAssertNil(s.news)
        XCTAssertNil(s.watchlist)
    }

    func testTolerantEnums() {
        XCTAssertEqual(LabQuadrant(raw: "bad_break"), .badBreak)
        XCTAssertEqual(LabQuadrant(raw: "brilliant"), .unknown)
        XCTAssertEqual(LabSkepticStatus(raw: nil), .unknown)
        XCTAssertEqual(LabVerdictLabel(raw: "not_supported"), .notSupported)
        XCTAssertEqual(LabMentorMode(raw: "llm"), .llm)
        XCTAssertEqual(LabSectionKind(raw: "video"), .unknown)
        XCTAssertEqual(LabEventKind(raw: "corporate_action"), .corporateAction)
        XCTAssertEqual(LabEventKind(raw: "rumour"), .unknown)
        XCTAssertEqual(LabSeverity(raw: "HIGH"), .unknown)
    }

    // MARK: - Lists, ids, verdicts

    func testListDecodesBareArrayAndWrappedObject() throws {
        let bare = try decode(LabList<LabSessionSummary>.self,
                              #"[{"id": 7, "title": "A", "clock": "2020-01-02", "equity": 1000, "finished": true}]"#)
        XCTAssertEqual(bare.items.first?.id, "7")
        XCTAssertNil(bare.total)
        let wrapped = try decode(LabList<LabExperimentSummary>.self,
                                 #"{"experiments": [{"id": "e1", "verdict": "fragile"}], "trials": 9}"#)
        XCTAssertEqual(wrapped.items.first?.id, "e1")
        XCTAssertEqual(wrapped.items.first?.verdict?.kind, .fragile)
        XCTAssertEqual(wrapped.total, 9)
    }

    func testVerdictDecodesFromObjectOrString() throws {
        let obj = try decode(LabVerdict.self, #"{"label": "supported", "text": "ok", "failed_checks": []}"#)
        XCTAssertEqual(obj.kind, .supported)
        XCTAssertEqual(obj.text, "ok")
        XCTAssertEqual(try decode(LabVerdict.self, #""weird""#).kind, .unknown)
    }

    // MARK: - Experiment report

    private let reportJSON = """
    {"status": "ok", "fingerprint": "abc", "lineage": ["px_idx"], "warmup_bars": 252,
     "research_window": ["2015-01-01", "2024-10-01"], "holdout_window": ["2024-10-01", "2025-10-01"],
     "costs": {"round_trip": 0.0032, "slippage_bps_per_side": 10, "note": "n"},
     "result": {"periods": 120, "mean_names": 48.5, "mean_ic": 0.021, "ic_hac_t": 2.4, "ic_ci95": [0.004, 0.038],
                "ic_positive_share": 0.58, "top_excess_net_per_period": 0.0012, "avg_turnover": 0.4,
                "net_sharpe_ann": 0.7, "net_sharpe_ci95": [null, 1.2]},
     "series": [{"date": "2015-02-02", "ic": 0.03, "top_net": 0.001}],
     "permutation_p": 0.01,
     "baselines": {"base_mom_20": {"mean_ic": 0.01, "top_excess_net_per_period": 0.0, "ic_diff_mean": 0.011, "ic_diff_t": 1.9}},
     "ic_by_year": {"2015": 0.02, "2016": -0.01},
     "deflated_sharpe": {"value": 0.81, "trials": 4, "note": "n"},
     "skeptics": [{"agent": "Statistical Skeptic", "status": "pass", "finding": "f", "evidence": {"p": 0.01}, "critical": true},
                  {"agent": "New Skeptic", "status": "maybe", "finding": "g"}],
     "verdict": {"label": "supported", "text": "t", "failed_checks": []},
     "provenance": {"source": "store", "warnings": []}}
    """

    func testExperimentRecordDecodesInlineOrNested() throws {
        let inline = try decode(LabExperimentRecord.self, reportJSON)
        XCTAssertEqual(inline.report.result?.meanIc, 0.021)
        XCTAssertEqual(inline.report.result?.icCi95?.last ?? nil, 0.038)
        XCTAssertNil(inline.report.result?.netSharpeCi95?.first ?? nil)
        XCTAssertEqual(inline.report.baselines?["baseMom20"]?.icDiffT, 1.9)  // dictionary keys are camel-cased
        XCTAssertEqual(inline.report.icByYear?["2016"], -0.01)
        XCTAssertEqual(inline.report.deflatedSharpe?.trials, 4)
        XCTAssertEqual(inline.report.skeptics?.map(\.statusKind), [.pass, .unknown])
        XCTAssertEqual(inline.report.verdict?.kind, .supported)

        let nested = try decode(LabExperimentRecord.self, #"{"id": 3, "created_at": "2026-10-19", "report": \#(reportJSON)}"#)
        XCTAssertEqual(nested.id?.value, "3")
        XCTAssertEqual(nested.report.series?.first?.topNet, 0.001)
    }

    // MARK: - Autopsy, mentor, school, events

    func testAutopsyDecodes() throws {
        let json = """
        {"clock": "2020-04-01",
         "trades": [{"symbol": "SBIN", "qty": 100, "entry_order_id": "o1", "exit_order_id": "o4", "thesis": "t",
           "knowable": {"asof": "2020-02-27", "bars_available": 300, "ret_5d": -0.05, "ret_5d_z": -1.8,
                        "dist_from_52w_high": -0.2, "volume_vs_20d_avg": 1.6, "vol_20d_ann": 0.3,
                        "news_visible": [{"title": "x"}], "base_rate": {"horizon": 20, "windows": 50, "beat_benchmark_share": 0.46}},
           "process": {"score": 62, "checks": [{"id": "thesis", "passed": true, "text": "Wrote a thesis"}]},
           "hindsight": {"return_net": -0.08, "pnl_net": -2400, "sessions_held": 12, "max_adverse_excursion": -0.15},
           "verdict": {"quadrant": "bad_break", "text": "Reasonable decision, bad outcome."}}],
         "counterfactuals": [{"variant": "half_size", "final_equity": 991000, "delta_vs_actual": 1200, "valid": true},
                             {"variant": "with_stop", "valid": false, "reason": "no planned stop"}],
         "counterfactual_note": "Hindsight comparison.",
         "behaviour": [{"id": "overtrading", "severity": "medium", "evidence": {"trades_per_week": 6.5}, "text": "Many trades."}]}
        """
        let r = try decode(LabAutopsyReport.self, json)
        let a = try XCTUnwrap(r.trades?.first)
        XCTAssertEqual(a.knowable?.ret5dZ, -1.8)
        XCTAssertEqual(a.knowable?.distFrom52wHigh, -0.2)
        XCTAssertEqual(a.knowable?.baseRate?.beatBenchmarkShare, 0.46)
        XCTAssertEqual(a.process?.score, 62)
        XCTAssertEqual(a.verdict?.kind, .badBreak)
        XCTAssertEqual(a.hindsight?.sessionsHeld, 12)
        XCTAssertEqual(r.counterfactuals?.count, 2)
        XCTAssertEqual(r.behaviour?.first?.severityKind, .medium)
        XCTAssertEqual(r.behaviour?.first?.evidence?["tradesPerWeek"]?.display, "6.5")
    }

    func testMentorReplyDecodes() throws {
        let r = try decode(LabMentorReply.self, #"{"answer": "**Size** mattered.", "grounded_on": {"position_weight": 0.4, "symbol": "SBIN"}, "mode": "rules", "disclaimer": "Educational only."}"#)
        XCTAssertEqual(r.modeKind, .rules)
        XCTAssertEqual(r.groundedOn?["symbol"]?.display, "SBIN")
        XCTAssertEqual(r.groundedOn?["positionWeight"]?.display, "0.4")
    }

    func testLessonAndGradeDecode() throws {
        let lesson = try decode(LabLesson.self, """
        {"id": "f-1", "track": "foundation", "title": "Shares", "minutes": 10, "concepts": ["equity_ownership"],
         "body": [{"kind": "text", "md": "A **share**"}, {"kind": "formula", "latex": "x", "md": "m"},
                  {"kind": "interactive", "md": "", "widget": "cost_calculator"}, {"kind": "video"}],
         "quiz": [{"id": "q1", "q": "Who?", "choices": ["a", "b"]}]}
        """)
        XCTAssertEqual(lesson.body?.map(\.kindValue), [.text, .formula, .interactive, .unknown])
        XCTAssertEqual(lesson.body?[2].widget, "cost_calculator")
        XCTAssertEqual(lesson.quiz?.first?.choices?.count, 2)

        let grade = try decode(LabGrade.self, #"{"lesson_id": "f-1", "score": 0.5, "passed": false, "per_question": [{"id": "q1", "correct": false, "answer": 1, "explain": "b"}], "state": {}}"#)
        XCTAssertEqual(grade.perQuestion?.first?.answer, 1)
        XCTAssertEqual(grade.passed, false)

        let next = try decode(LabNextLessons.self, #"{"lessons": [{"lesson_id": "f-2", "title": "T", "track": "foundation", "concepts": [], "reason": "weakness"}]}"#)
        XCTAssertEqual(next.lessons?.first?.lessonId, "f-2")
        XCTAssertEqual(next.lessons?.first?.reason, "weakness")
    }

    func testEventTimelineDecodes() throws {
        let t = try decode(LabEventTimeline.self, """
        {"symbol": "RELIANCE", "start": "2020-01-01", "end": "2020-06-30",
         "bars": [{"d": "2020-01-02", "c": 1500.5, "v": 100}],
         "items": [{"date": "2020-03-23", "kind": "price_anomaly", "evidence": "prices", "text": "-13% day", "z": -5.1},
                   {"date": "2020-04-22", "kind": "sourced_event", "evidence": "source", "text": "Jio deal", "source_url": "https://example.com"}],
         "note": "Anomalies are statistical.", "provenance": {"warnings": []}}
        """)
        XCTAssertEqual(t.bars?.first?.c, 1500.5)
        XCTAssertEqual(t.items?.map(\.kindValue), [.priceAnomaly, .sourcedEvent])
        XCTAssertEqual(t.items?.last?.sourceUrl, "https://example.com")
        XCTAssertNotNil(t.items?.first?.day)
    }

    // MARK: - Requests and helpers

    func testActionJSON() {
        let draft = LabOrderDraft(symbol: "TCS", side: "BUY", qty: 5, orderType: "LIMIT", limit: 2000, stop: 1900,
                                  tif: "GTC", thesis: "Earnings momentum", plannedStop: 1800, plannedExit: nil,
                                  horizonDays: nil, conviction: 0.6)
        let o = LabAction.order(draft).json
        XCTAssertEqual(o["type"] as? String, "order")
        XCTAssertEqual(o["order_type"] as? String, "LIMIT")
        XCTAssertEqual(o["limit"] as? Double, 2000)
        XCTAssertNil(o["stop"], "stop is only sent for STOP orders")
        XCTAssertEqual(o["planned_stop"] as? Double, 1800)
        XCTAssertNil(o["planned_exit"])
        XCTAssertEqual(o["conviction"] as? Double, 0.6)
        XCTAssertEqual(LabAction.cancel(orderId: "o3").json["order_id"] as? String, "o3")
        XCTAssertEqual(LabAction.advance(days: 5).json["days"] as? Int, 5)
    }

    func testOrderDraftRequiresThesisAndPrices() {
        var d = LabOrderDraft(symbol: "TCS", side: "BUY", qty: 1, orderType: "MARKET", limit: nil, stop: nil,
                              tif: "DAY", thesis: "short", plannedStop: nil, plannedExit: nil, horizonDays: nil, conviction: nil)
        XCTAssertNotNil(d.problem)
        d.thesis = "A considered thesis"
        XCTAssertNil(d.problem)
        d.orderType = "LIMIT"
        XCTAssertNotNil(d.problem)
        d.limit = 100
        XCTAssertNil(d.problem)
        d.qty = 0
        XCTAssertNotNil(d.problem)
    }

    func testSimConfigJSONUsesWireKeys() {
        let c = LabSimConfig(start: "2020-02-03", end: "2020-06-30", universe: ["SBIN"], capital: 500_000, hideIdentity: true)
        XCTAssertEqual(c.json["hide_identity"] as? Bool, true)
        XCTAssertEqual(c.json["capital"] as? Double, 500_000)
        XCTAssertNil(LabSimConfig().json["start"])
    }

    func testLabRouteHashing() {
        let routes: Set<LabRoute> = [.session(id: "1"), .session(id: "1"), .session(id: "2"),
                                     .mentor(sessionId: "1", orderId: nil), .mentor(sessionId: "1", orderId: "o1"),
                                     .autopsy(sessionId: "1", orderId: "o1"), .lesson(id: "f-1"), .eventExplorer]
        XCTAssertEqual(routes.count, 7)
        XCTAssertNotEqual(LabRoute.chart(sessionId: "1", symbol: "A"), .chart(sessionId: "1", symbol: "B"))
        XCTAssertEqual(LabRoute.experiment(id: "e").hashValue, LabRoute.experiment(id: "e").hashValue)
    }

    func testDeliveryChargesEstimate() {
        let buy = LabCostEstimate.charges(value: 1_00_000, buy: true)
        XCTAssertEqual(buy.brokerage, 20, accuracy: 1e-9)        // min(20, 30)
        XCTAssertEqual(buy.stt, 100, accuracy: 1e-9)
        XCTAssertEqual(buy.stamp, 15, accuracy: 1e-9)
        XCTAssertEqual(buy.gst, 0.18 * (20 + 3.07 + 0.1), accuracy: 1e-9)
        XCTAssertEqual(buy.total, 20 + 100 + 3.07 + 0.1 + 15 + 0.18 * 23.17, accuracy: 1e-9)
        let sell = LabCostEstimate.charges(value: 10_000, buy: false)
        XCTAssertEqual(sell.brokerage, 3, accuracy: 1e-9)          // 0.03% below the flat cap
        XCTAssertEqual(sell.stamp, 0)
        XCTAssertEqual(LabCostEstimate.charges(value: 0, buy: true).total, 0)
    }

    func testCompounding() {
        let path = LabCostEstimate.compound(principal: 100, rate: 0.1, years: 2)
        XCTAssertEqual(path.count, 3)
        XCTAssertEqual(path[2], 121, accuracy: 1e-9)
    }

    func testFormattingHelpers() {
        XCTAssertEqual(LabFormat.humanize("tradesPerWeek"), "trades per week")
        XCTAssertEqual(LabFormat.humanize("max_drawdown"), "max drawdown")
        XCTAssertEqual(LabFormat.baselineName("baseRev5"), "5-day reversal")
        XCTAssertEqual(LabFormat.plainFormula(#"\text{spread} = \frac{a - b}{m} \times 10{,}000"#), "spread = (a - b) / (m) × 10,000")
        XCTAssertEqual(LabFormat.day("2020-03-02"), "02 Mar 2020")
        XCTAssertEqual(LabFormat.pct(nil), "—")
        XCTAssertFalse(LabFormat.money(2_50_00_000).lowercased().contains("million"))
    }
}
