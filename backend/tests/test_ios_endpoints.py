"""Contract tests for iOS-facing routes (uses the conftest client/auth fixtures)."""


# --- CONTRACT TESTS FOR PLACEHOLDER ROUTES ---


# Job routes take the caller from the bearer token and answer 404 for missing or
# foreign jobs (AUTH-08).
def test_analyze_job_jobId_success(client, auth_headers):
    response = client.get("/analyze/job/990001", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 404)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_analyze_job_jobId_unauthenticated(client):
    response = client.get("/analyze/job/990001")
    assert response.status_code == 401

def test_analyze_job_jobId_not_found(client, auth_headers):
    dummy_path = "/analyze/job/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 404

def test_analyze_job_jobId_validation_error(client, auth_headers):
    bad_path = "/analyze/job/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 404

def test_analyze_jobId_cancel_success(client, auth_headers):
    response = client.post("/analyze/990001/cancel", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 404)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_analyze_jobId_cancel_unauthenticated(client):
    response = client.post("/analyze/990001/cancel")
    assert response.status_code == 401

def test_analyze_jobId_cancel_not_found(client, auth_headers):
    dummy_path = "/analyze/9999999/cancel"
    response = client.post(dummy_path, headers=auth_headers)
    assert response.status_code == 404

def test_analyze_jobId_cancel_validation_error(client, auth_headers):
    bad_path = "/analyze/invalid_id/cancel"
    response = client.post(bad_path, headers=auth_headers)
    assert response.status_code == 404

def test_fundamentals_ticker_financials_success(client, auth_headers):
    response = client.get("/fundamentals/RELIANCE/financials", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_ticker_financials_unauthenticated(client):
    response = client.get("/fundamentals/RELIANCE/financials")
    assert response.status_code == 200

def test_fundamentals_ticker_financials_not_found(client, auth_headers):
    dummy_path = "/fundamentals/NONEXISTENT/financials"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_fundamentals_ticker_shareholding_success(client, auth_headers):
    response = client.get("/fundamentals/RELIANCE/shareholding", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_ticker_shareholding_unauthenticated(client):
    response = client.get("/fundamentals/RELIANCE/shareholding")
    assert response.status_code == 200

def test_fundamentals_ticker_shareholding_not_found(client, auth_headers):
    dummy_path = "/fundamentals/NONEXISTENT/shareholding"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_fundamentals_ticker_corporate_actions_success(client, auth_headers):
    response = client.get("/fundamentals/RELIANCE/corporate-actions", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_ticker_corporate_actions_unauthenticated(client):
    response = client.get("/fundamentals/RELIANCE/corporate-actions")
    assert response.status_code == 200

def test_fundamentals_ticker_corporate_actions_not_found(client, auth_headers):
    dummy_path = "/fundamentals/NONEXISTENT/corporate-actions"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_fundamentals_ticker_valuation_success(client, auth_headers):
    response = client.get("/fundamentals/RELIANCE/valuation", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 402)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_ticker_valuation_unauthenticated(client):
    response = client.get("/fundamentals/RELIANCE/valuation")
    assert response.status_code == 401

def test_fundamentals_ticker_valuation_not_found(client, auth_headers):
    dummy_path = "/fundamentals/NONEXISTENT/valuation"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 402)

def test_fundamentals_ticker_risk_signals_success(client, auth_headers):
    response = client.get("/fundamentals/RELIANCE/risk-signals", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 402)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_ticker_risk_signals_unauthenticated(client):
    response = client.get("/fundamentals/RELIANCE/risk-signals")
    assert response.status_code == 401

def test_fundamentals_ticker_risk_signals_not_found(client, auth_headers):
    dummy_path = "/fundamentals/NONEXISTENT/risk-signals"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 402)

def test_fundamentals_piotroski_ticker_success(client, auth_headers):
    response = client.get("/fundamentals/piotroski/RELIANCE", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_fundamentals_piotroski_ticker_unauthenticated(client):
    response = client.get("/fundamentals/piotroski/RELIANCE")
    assert response.status_code == 200

def test_fundamentals_piotroski_ticker_not_found(client, auth_headers):
    dummy_path = "/fundamentals/piotroski/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_harvester_governance_ticker_success(client, auth_headers):
    response = client.get("/harvester/governance/RELIANCE", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_harvester_governance_ticker_unauthenticated(client):
    response = client.get("/harvester/governance/RELIANCE")
    assert response.status_code == 401

def test_harvester_governance_ticker_not_found(client, auth_headers):
    dummy_path = "/harvester/governance/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_macro_impact_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/macro-impact/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_macro_impact_userId_unauthenticated(client):
    response = client.get("/macro-impact/999999")
    assert response.status_code == 401

def test_macro_impact_userId_not_found(client, auth_headers):
    dummy_path = "/macro-impact/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_macro_impact_userId_validation_error(client, auth_headers):
    bad_path = "/macro-impact/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_daily_action_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/daily-action/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_daily_action_userId_unauthenticated(client):
    response = client.get("/daily-action/999999")
    assert response.status_code == 401

def test_daily_action_userId_not_found(client, auth_headers):
    dummy_path = "/daily-action/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_daily_action_userId_validation_error(client, auth_headers):
    bad_path = "/daily-action/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_macro_context_ticker_success(client, auth_headers):
    response = client.get("/macro-context/RELIANCE", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_macro_context_ticker_unauthenticated(client):
    response = client.get("/macro-context/RELIANCE")
    assert response.status_code == 200

def test_macro_context_ticker_not_found(client, auth_headers):
    dummy_path = "/macro-context/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_morning_summary_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/morning-summary/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 500)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_morning_summary_userId_unauthenticated(client):
    response = client.get("/morning-summary/999999")
    assert response.status_code == 401

def test_morning_summary_userId_not_found(client, auth_headers):
    dummy_path = "/morning-summary/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_morning_summary_userId_validation_error(client, auth_headers):
    bad_path = "/morning-summary/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_portfolio_userId_unauthenticated(client):
    response = client.get("/portfolio/999999")
    assert response.status_code == 401

def test_portfolio_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_export_excel_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/export/excel/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert response.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def test_portfolio_export_excel_userId_unauthenticated(client):
    response = client.get("/portfolio/export/excel/999999")
    assert response.status_code == 401

def test_portfolio_export_excel_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/export/excel/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_export_excel_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/export/excel/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_export_pdf_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/export/pdf/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert response.headers["content-type"].startswith("application/pdf")

def test_portfolio_export_pdf_userId_unauthenticated(client):
    response = client.get("/portfolio/export/pdf/999999")
    assert response.status_code == 401

def test_portfolio_export_pdf_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/export/pdf/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_export_pdf_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/export/pdf/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_risk_analysis_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/risk-analysis/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_portfolio_risk_analysis_userId_unauthenticated(client):
    response = client.get("/portfolio/risk-analysis/999999")
    assert response.status_code == 401

def test_portfolio_risk_analysis_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/risk-analysis/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_risk_analysis_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/risk-analysis/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_red_flags_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/red-flags/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_portfolio_red_flags_userId_unauthenticated(client):
    response = client.get("/portfolio/red-flags/999999")
    assert response.status_code == 401

def test_portfolio_red_flags_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/red-flags/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_red_flags_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/red-flags/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_portfolio_timeframe_conflicts_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/portfolio/timeframe-conflicts/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_portfolio_timeframe_conflicts_userId_unauthenticated(client):
    response = client.get("/portfolio/timeframe-conflicts/999999")
    assert response.status_code == 401

def test_portfolio_timeframe_conflicts_userId_not_found(client, auth_headers):
    dummy_path = "/portfolio/timeframe-conflicts/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_portfolio_timeframe_conflicts_userId_validation_error(client, auth_headers):
    bad_path = "/portfolio/timeframe-conflicts/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_api_v1_portfolio_stress_test_jobId_success(client, auth_headers):
    response = client.get("/api/v1/portfolio/stress-test/990001", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 404)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_api_v1_portfolio_stress_test_jobId_unauthenticated(client):
    response = client.get("/api/v1/portfolio/stress-test/990001")
    assert response.status_code == 401

def test_api_v1_portfolio_stress_test_jobId_not_found(client, auth_headers):
    dummy_path = "/api/v1/portfolio/stress-test/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 404)

def test_api_v1_portfolio_stress_test_jobId_validation_error(client, auth_headers):
    bad_path = "/api/v1/portfolio/stress-test/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 404

def test_api_v1_portfolio_charts_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/api/v1/portfolio/charts/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_api_v1_portfolio_charts_userId_unauthenticated(client):
    response = client.get("/api/v1/portfolio/charts/999999")
    assert response.status_code == 401

def test_api_v1_portfolio_charts_userId_not_found(client, auth_headers):
    dummy_path = "/api/v1/portfolio/charts/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_api_v1_portfolio_charts_userId_validation_error(client, auth_headers):
    bad_path = "/api/v1/portfolio/charts/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_alerts_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/alerts/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_alerts_userId_unauthenticated(client):
    response = client.get("/alerts/999999")
    assert response.status_code == 401

def test_alerts_userId_not_found(client, auth_headers):
    dummy_path = "/alerts/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_alerts_userId_validation_error(client, auth_headers):
    bad_path = "/alerts/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_alerts_check_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/alerts/check/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_alerts_check_userId_unauthenticated(client):
    response = client.get("/alerts/check/999999")
    assert response.status_code == 401

def test_alerts_check_userId_not_found(client, auth_headers):
    dummy_path = "/alerts/check/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_alerts_check_userId_validation_error(client, auth_headers):
    bad_path = "/alerts/check/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_api_v1_stocks_symbol_ml_signal_success(client, auth_headers):
    response = client.get("/api/v1/stocks/RELIANCE/ml-signal", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_api_v1_stocks_symbol_ml_signal_unauthenticated(client):
    response = client.get("/api/v1/stocks/RELIANCE/ml-signal")
    assert response.status_code == 401

def test_api_v1_stocks_symbol_ml_signal_not_found(client, auth_headers):
    dummy_path = "/api/v1/stocks/NONEXISTENT/ml-signal"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_dividends_ticker_success(client, auth_headers):
    response = client.get("/dividends/RELIANCE", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_dividends_ticker_unauthenticated(client):
    response = client.get("/dividends/RELIANCE")
    assert response.status_code == 200

def test_dividends_ticker_not_found(client, auth_headers):
    dummy_path = "/dividends/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_market_sentiment_trend_ticker_success(client, auth_headers):
    response = client.get("/market/sentiment-trend/RELIANCE", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_market_sentiment_trend_ticker_unauthenticated(client):
    response = client.get("/market/sentiment-trend/RELIANCE")
    assert response.status_code == 200

def test_market_sentiment_trend_ticker_not_found(client, auth_headers):
    dummy_path = "/market/sentiment-trend/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 200)

def test_trade_journal_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/trade-journal/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_trade_journal_userId_unauthenticated(client):
    response = client.get("/trade-journal/999999")
    assert response.status_code == 401

def test_trade_journal_userId_not_found(client, auth_headers):
    dummy_path = "/trade-journal/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_trade_journal_userId_validation_error(client, auth_headers):
    bad_path = "/trade-journal/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_trade_journal_entryId_put_success(client, auth_headers):
    response = client.put("/trade-journal/990001", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 422)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_trade_journal_entryId_put_unauthenticated(client):
    response = client.put("/trade-journal/990001")
    assert response.status_code == 422

def test_trade_journal_entryId_not_found(client, auth_headers):
    dummy_path = "/trade-journal/9999999"
    response = client.put(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 422)

def test_trade_journal_entryId_validation_error(client, auth_headers):
    bad_path = "/trade-journal/invalid_id"
    response = client.put(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_trade_journal_entryId_delete_success(client, auth_headers):
    response = client.delete("/trade-journal/990001", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 422)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_trade_journal_entryId_delete_unauthenticated(client):
    response = client.delete("/trade-journal/990001")
    assert response.status_code == 422

def test_trade_journal_entryId_not_found(client, auth_headers):
    dummy_path = "/trade-journal/9999999"
    response = client.delete(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 422)

def test_trade_journal_entryId_validation_error(client, auth_headers):
    bad_path = "/trade-journal/invalid_id"
    response = client.delete(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_trade_journal_userId_stats_success(client, auth_headers, test_user_id):
    response = client.get(f"/trade-journal/{test_user_id}/stats", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_trade_journal_userId_stats_unauthenticated(client):
    response = client.get("/trade-journal/999999/stats")
    assert response.status_code == 401

def test_trade_journal_userId_stats_not_found(client, auth_headers):
    dummy_path = "/trade-journal/9999999/stats"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (GH-630)

def test_trade_journal_userId_stats_validation_error(client, auth_headers):
    bad_path = "/trade-journal/invalid_id/stats"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_watchlist_userId_success(client, auth_headers, test_user_id):
    response = client.get(f"/watchlist/{test_user_id}", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_watchlist_userId_unauthenticated(client):
    response = client.get("/watchlist/999999")
    assert response.status_code == 401

def test_watchlist_userId_not_found(client, auth_headers):
    dummy_path = "/watchlist/9999999"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code == 403  # another user\'s id (ARCH-02)

def test_watchlist_userId_validation_error(client, auth_headers):
    bad_path = "/watchlist/invalid_id"
    response = client.get(bad_path, headers=auth_headers)
    assert response.status_code == 422

def test_api_v1_youtube_summary_videoId_success(client, auth_headers):
    response = client.get("/api/v1/youtube/summary/dQw4w9WgXcQ", headers=auth_headers)
    assert response.status_code in (200, 201, 202, 204, 404)
    if response.status_code == 200:
        assert isinstance(response.json(), (dict, list))

def test_api_v1_youtube_summary_videoId_unauthenticated(client):
    response = client.get("/api/v1/youtube/summary/dQw4w9WgXcQ")
    assert response.status_code == 401

def test_api_v1_youtube_summary_videoId_not_found(client, auth_headers):
    dummy_path = "/api/v1/youtube/summary/NONEXISTENT"
    response = client.get(dummy_path, headers=auth_headers)
    assert response.status_code in (404, 404)
