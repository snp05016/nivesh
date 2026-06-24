# API Contract Map

> Last generated: 2026-06-24. Source: FastAPI decorators in `backend/main.py` and `backend/routers/*.py`, plus Swift URL call sites under `ios/StockApp/stockme/stockme`.

## Prefix Rules

- Most routers are included without a prefix in `backend/main.py:365-385`.
- `sector_rotation.router` is included with `prefix="/api/v1"`; because the router defines `prefix="/market"`, the effective endpoint is `GET /api/v1/market/sector-rotation`.
- `options_strategy.router`, `anomalies.router`, `copilot.router`, `notifications.router`, and many market endpoints define `/api/v1` directly inside the router.
- Legacy unprefixed routes remain active: `/analyze`, `/portfolio/{user_id}`, `/market-indices`, `/search`, `/quick-info`, `/watchlist/*`, `/alerts/*`.

## Full Route Inventory

| Method | Effective path | Handler | Source |
|---|---|---|---|
| `GET` | `/ping` | `ping` | `backend/main.py:482` |
| `GET` | `/favicon.ico` | `favicon` | `backend/main.py:488` |
| `GET` | `/health` | `health_endpoint` | `backend/main.py:823` |
| `GET` | `/health/live` | `liveness_probe` | `backend/main.py:840` |
| `GET` | `/` | `dashboard_html` | `backend/main.py:2033` |
| `GET` | `/dashboard-data` | `dashboard_data` | `backend/main.py:2038` |
| `GET` | `/dashboard-user-data` | `dashboard_user_data` | `backend/main.py:2233` |
| `POST` | `/alerts/add` | `alerts_add_endpoint` | `backend/routers/alerts.py:11` |
| `DELETE` | `/alerts/remove` | `alerts_remove_endpoint` | `backend/routers/alerts.py:47` |
| `GET` | `/alerts/{user_id}` | `alerts_get_endpoint` | `backend/routers/alerts.py:217` |
| `POST` | `/batch` | `batch_analysis` | `backend/routers/analysis.py:107` |
| `GET` | `/quick-info` | `quick_info_endpoint` | `backend/routers/analysis.py:181` |
| `POST` | `/analyze` | `analyze_endpoint` | `backend/routers/analysis.py:488` |
| `GET` | `/analyze/job/{job_id}` | `get_job_status` | `backend/routers/analysis.py:562` |
| `GET` | `/analyze/active` | `get_active_job` | `backend/routers/analysis.py:575` |
| `POST` | `/analyze/{job_id}/cancel` | `cancel_job_endpoint` | `backend/routers/analysis.py:586` |
| `GET` | `/analyze/cache-status/{ticker}` | `cache_status` | `backend/routers/analysis.py:604` |
| `POST` | `/analyze/cache/{ticker}/invalidate` | `invalidate_cache` | `backend/routers/analysis.py:642` |
| `GET` | `/analyze/slots` | `inspect_analysis_slots` | `backend/routers/analysis.py:668` |
| `DELETE` | `/analyze/slots` | `clear_analysis_slots` | `backend/routers/analysis.py:683` |
| `POST` | `/analyze/batch` | `batch_analyze_endpoint` | `backend/routers/analysis.py:715` |
| `GET` | `/analyze/batch/{batch_id}` | `batch_analyze_status` | `backend/routers/analysis.py:766` |
| `GET` | `/api/v1/technical-signals` | `get_technical_signals` | `backend/routers/analysis.py:805` |
| `GET` | `/api/v1/home-feed` | `get_home_feed` | `backend/routers/analysis.py:832` |
| `GET` | `/screener` | `screener_endpoint` | `backend/routers/analysis.py:983` |
| `GET` | `/daily-action/{user_id}` | `daily_action_endpoint` | `backend/routers/analysis.py:1361` |
| `GET` | `/token-stats` | `token_stats_endpoint` | `backend/routers/analysis.py:1493` |
| `GET` | `/api/v1/market/anomalies` | `read_anomalies` | `backend/routers/anomalies.py:8` |
| `POST` | `/login` | `login_endpoint` | `backend/routers/auth.py:12` |
| `POST` | `/register` | `register_endpoint` | `backend/routers/auth.py:28` |
| `POST` | `/brainstorm` | `brainstorming_endpoint` | `backend/routers/brainstorming.py:21` |
| `POST` | `/api/v1/copilot/chat` | `copilot_chat` | `backend/routers/copilot.py:25` |
| `GET` | `/portfolio/correlation` | `get_portfolio_correlation` | `backend/routers/correlation.py:12` |
| `GET` | `/api/v1/dashboard/ai-engine` | `ai_engine_dashboard` | `backend/routers/dashboard.py:81` |
| `GET` | `/api/v1/dashboard/ai-engine/{job_id}` | `ai_engine_job_detail` | `backend/routers/dashboard.py:93` |
| `GET` | `/api/v1/dashboard/stream` | `dashboard_stream` | `backend/routers/dashboard.py:103` |
| `GET` | `/api/v1/earnings/surprises` | `api_get_earnings_surprises` | `backend/routers/earnings_surprise.py:22` |
| `GET` | `/api/v1/earnings/surprise-history/{ticker}` | `api_get_earnings_surprise_history` | `backend/routers/earnings_surprise.py:30` |
| `GET` | `/harvester/feed` | `get_feed` | `backend/routers/harvester.py:85` |
| `GET` | `/harvester/governance/{ticker}` | `get_governance` | `backend/routers/harvester.py:103` |
| `GET` | `/harvester/sources` | `get_sources` | `backend/routers/harvester.py:114` |
| `GET` | `/harvester/search` | `search` | `backend/routers/harvester.py:122` |
| `POST` | `/harvester/trigger/scrape` | `trigger_scrape` | `backend/routers/harvester.py:143` |
| `GET` | `/harvester/stats` | `stats` | `backend/routers/harvester.py:175` |
| `GET` | `/healthz` | `healthz` | `backend/routers/health.py:16` |
| `GET` | `/market-indices` | `market_indices_endpoint` | `backend/routers/market.py:36` |
| `GET` | `/nifty-history` | `nifty_history_endpoint` | `backend/routers/market.py:41` |
| `GET` | `/dividends/{ticker}` | `dividend_history_endpoint` | `backend/routers/market.py:77` |
| `GET` | `/mf/{scheme_code}` | `mutual_fund_nav_endpoint` | `backend/routers/market.py:143` |
| `GET` | `/block-deals/{ticker}` | `block_deals_endpoint` | `backend/routers/market.py:182` |
| `GET` | `/fii-dii-flow` | `fii_dii_flow_endpoint` | `backend/routers/market.py:207` |
| `GET` | `/quarterly-financials` | `quarterly_financials_endpoint` | `backend/routers/market.py:261` |
| `GET` | `/macro-strip` | `macro_strip_endpoint` | `backend/routers/market.py:324` |
| `GET` | `/macro-context/{ticker}` | `macro_context_endpoint` | `backend/routers/market.py:393` |
| `GET` | `/earnings-calendar` | `earnings_calendar_endpoint` | `backend/routers/market.py:616` |
| `GET` | `/analyst-ratings` | `analyst_ratings_endpoint` | `backend/routers/market.py:670` |
| `GET` | `/ipo-calendar` | `ipo_calendar_endpoint` | `backend/routers/market.py:722` |
| `GET` | `/sector-weekly` | `sector_weekly_endpoint` | `backend/routers/market.py:732` |
| `GET` | `/search` | `search_endpoint` | `backend/routers/market.py:976` |
| `GET` | `/sector-performance` | `sector_performance_endpoint` | `backend/routers/market.py:1019` |
| `GET` | `/api/v1/market/pulse` | `market_pulse_endpoint` | `backend/routers/market.py:1089` |
| `GET` | `/api/v1/market/momentum` | `market_momentum_endpoint` | `backend/routers/market.py:1097` |
| `GET` | `/api/v1/market/macro-alternatives` | `market_macro_alternatives_endpoint` | `backend/routers/market.py:1105` |
| `GET` | `/api/v1/market/institutional-flow` | `market_institutional_flow_endpoint` | `backend/routers/market.py:1113` |
| `GET` | `/api/v1/market/stock-history` | `stock_history_endpoint` | `backend/routers/market.py:1122` |
| `GET` | `/api/v1/stock-profile` | `stock_profile_endpoint` | `backend/routers/market.py:1182` |
| `GET` | `/api/v1/earnings/sync-ratio` | `earnings_sync_ratio_endpoint` | `backend/routers/market.py:1469` |
| `GET` | `/api/v1/earnings/yoy-aggregate` | `yoy_aggregate_endpoint` | `backend/routers/market.py:1497` |
| `GET` | `/api/v1/market/dashboard` | `market_dashboard_endpoint` | `backend/routers/market.py:1584` |
| `GET` | `/api/v1/market/dashboard-pulse` | `dashboard_pulse_endpoint` | `backend/routers/market.py:1606` |
| `GET` | `/api/v1/admin/error-logs` | `admin_error_logs_endpoint` | `backend/routers/market.py:1889` |
| `GET` | `/api/v1/market/institutional-leaderboard` | `institutional_leaderboard_endpoint` | `backend/routers/market.py:1925` |
| `GET` | `/api/v1/earnings/progress` | `earnings_progress_endpoint` | `backend/routers/market.py:2005` |
| `GET` | `/api/v1/earnings/feed` | `earnings_feed_endpoint` | `backend/routers/market.py:2216` |
| `GET` | `/api/v1/earnings/calendar` | `earnings_calendar_day_endpoint` | `backend/routers/market.py:2299` |
| `GET` | `/api/v1/earnings/estimates` | `earnings_estimates_endpoint` | `backend/routers/market.py:2408` |
| `GET` | `/api/v1/earnings/post-result-movers` | `post_result_movers_endpoint` | `backend/routers/market.py:2447` |
| `GET` | `/api/v1/earnings/alerts` | `earnings_alerts_get_endpoint` | `backend/routers/market.py:2499` |
| `POST` | `/api/v1/earnings/alerts` | `earnings_alerts_post_endpoint` | `backend/routers/market.py:2532` |
| `DELETE` | `/api/v1/earnings/alerts/{alert_id}` | `earnings_alerts_delete_endpoint` | `backend/routers/market.py:2580` |
| `GET` | `/api/v1/admin/earnings-errors` | `admin_earnings_errors_endpoint` | `backend/routers/market.py:2603` |
| `GET` | `/api/v1/options/chain/{ticker}` | `get_option_chain_metrics_endpoint` | `backend/routers/market.py:2641` |
| `GET` | `/api/v1/ideas/advisors` | `ideas_advisors_endpoint` | `backend/routers/market.py:2796` |
| `GET` | `/api/v1/ideas/feed` | `ideas_feed_endpoint` | `backend/routers/market.py:2832` |
| `GET` | `/api/v1/admin/ideas-errors` | `admin_ideas_errors_endpoint` | `backend/routers/market.py:2883` |
| `GET` | `/api/v1/market/top-movers` | `top_movers_endpoint` | `backend/routers/market.py:2933` |
| `GET` | `/market/sentiment-trend/{ticker}` | `sentiment_trend` | `backend/routers/market.py:3018` |
| `GET` | `/market/screener` | `run_screener` | `backend/routers/market.py:3029` |
| `POST` | `/api/v1/screener/natural-language` | `natural_language_screener` | `backend/routers/nl_screener.py:24` |
| `POST` | `/api/v1/notifications/register` | `register_device` | `backend/routers/notifications.py:45` |
| `POST` | `/api/v1/dev/push-mock` | `push_mock` | `backend/routers/notifications.py:86` |
| `GET` | `/api/v1/admin/notification-errors` | `get_notification_errors` | `backend/routers/notifications.py:128` |
| `POST` | `/api/v1/options/payoff` | `compute_strategy_payoff` | `backend/routers/options_strategy.py:82` |
| `POST` | `/portfolio/sip-calculator` | `sip_calculator` | `backend/routers/portfolio.py:217` |
| `GET` | `/portfolio/benchmark` | `portfolio_benchmark` | `backend/routers/portfolio.py:255` |
| `GET` | `/portfolio/stress-test` | `portfolio_stress_test` | `backend/routers/portfolio.py:324` |
| `GET` | `/portfolio/signal-warnings` | `portfolio_signal_warnings` | `backend/routers/portfolio.py:492` |
| `GET` | `/portfolio/{user_id}` | `portfolio_endpoint` | `backend/routers/portfolio.py:515` |
| `GET` | `/portfolio/history/{user_id}` | `portfolio_history_endpoint` | `backend/routers/portfolio.py:624` |
| `GET` | `/fundamentals/piotroski/{ticker}` | `piotroski_endpoint` | `backend/routers/portfolio.py:655` |
| `GET` | `/morning-summary/{user_id}` | `morning_summary_endpoint` | `backend/routers/portfolio.py:670` |
| `POST` | `/portfolio` | `portfolio_add_endpoint` | `backend/routers/portfolio.py:909` |
| `POST` | `/portfolio/add` | `portfolio_add_endpoint` | `backend/routers/portfolio.py:909` |
| `DELETE` | `/portfolio/remove` | `portfolio_remove_endpoint` | `backend/routers/portfolio.py:977` |
| `PUT` | `/portfolio/update` | `portfolio_update_endpoint` | `backend/routers/portfolio.py:1003` |
| `PUT` | `/portfolio/note` | `portfolio_note_endpoint` | `backend/routers/portfolio.py:1064` |
| `GET` | `/api/v1/portfolio/advisor-consensus` | `portfolio_advisor_consensus` | `backend/routers/portfolio.py:1372` |
| `GET` | `/portfolio/export/excel/{user_id}` | `export_portfolio_excel` | `backend/routers/portfolio.py:1526` |
| `GET` | `/api/v1/portfolio/valuation-history` | `get_valuation_history` | `backend/routers/portfolio.py:1649` |
| `GET` | `/api/v1/portfolio/charts/{user_id}` | `portfolio_charts_endpoint` | `backend/routers/portfolio.py:1768` |
| `GET` | `/portfolio/risk-analysis/{user_id}` | `portfolio_risk_analysis_endpoint` | `backend/routers/portfolio.py:1877` |
| `GET` | `/portfolio/red-flags/{user_id}` | `portfolio_red_flags_endpoint` | `backend/routers/portfolio.py:2039` |
| `GET` | `/macro-impact/{user_id}` | `macro_impact_endpoint` | `backend/routers/portfolio.py:2195` |
| `GET` | `/portfolio/timeframe-conflicts/{user_id}` | `portfolio_timeframe_conflicts_endpoint` | `backend/routers/portfolio.py:2281` |
| `POST` | `/trade-journal` | `trade_journal_add_endpoint` | `backend/routers/portfolio.py:2361` |
| `GET` | `/trade-journal/{user_id}` | `trade_journal_get_endpoint` | `backend/routers/portfolio.py:2405` |
| `PUT` | `/trade-journal/{entry_id}` | `trade_journal_update_endpoint` | `backend/routers/portfolio.py:2454` |
| `DELETE` | `/trade-journal/{entry_id}` | `trade_journal_delete_endpoint` | `backend/routers/portfolio.py:2504` |
| `GET` | `/trade-journal/{user_id}/stats` | `trade_journal_stats_endpoint` | `backend/routers/portfolio.py:2529` |
| `GET` | `/portfolio/export/pdf/{user_id}` | `export_portfolio_pdf` | `backend/routers/portfolio.py:2620` |
| `GET` | `/api/v1/market/net-worth-ledger/{user_id}` | `net_worth_ledger_endpoint` | `backend/routers/portfolio.py:2793` |
| `GET` | `/attribution/{user_id}` | `portfolio_attribution_endpoint` | `backend/routers/portfolio.py:2838` |
| `GET` | `/signal-accuracy` | `get_signal_accuracy` | `backend/routers/portfolio.py:2907` |
| `GET` | `/api/v1/predictions/performance` | `get_predictions_performance` | `backend/routers/predictions.py:62` |
| `GET` | `/api/v1/market/sector-rotation` | `get_sector_rotation` | `backend/routers/sector_rotation.py:7` |
| `POST` | `/api/v1/analysis/backtest` | `backtest_endpoint` | `backend/routers/strategy.py:15` |
| `POST` | `/api/v1/portfolio/stress-test` | `start_stress_test` | `backend/routers/stress_test.py:44` |
| `GET` | `/api/v1/portfolio/stress-test/{job_id}` | `get_stress_test_result` | `backend/routers/stress_test.py:67` |
| `GET` | `/api/v1/portfolio/stress-test/{job_id}/progress` | `get_stress_test_progress` | `backend/routers/stress_test.py:77` |
| `GET` | `/api/v1/dashboard/stress-test-jobs` | `list_stress_test_jobs` | `backend/routers/stress_test.py:85` |
| `GET` | `/users` | `list_users` | `backend/routers/user.py:52` |
| `POST` | `/watchlist/add` | `watchlist_add_endpoint` | `backend/routers/user.py:69` |
| `DELETE` | `/watchlist/remove` | `watchlist_remove_endpoint` | `backend/routers/user.py:98` |
| `GET` | `/watchlist/{user_id}` | `watchlist_get_endpoint` | `backend/routers/user.py:119` |
| `POST` | `/notifications/register-device` | `notifications_register_device` | `backend/routers/user.py:196` |
| `POST` | `/notifications/test` | `notifications_test` | `backend/routers/user.py:205` |
| `POST` | `/notifications/morning-summary-push` | `notifications_morning_summary_push` | `backend/routers/user.py:242` |
| `GET` | `/api/v1/experts` | `get_experts` | `backend/routers/user.py:280` |
| `GET` | `/api/v1/expert-posts` | `get_expert_posts` | `backend/routers/user.py:326` |
| `GET` | `/api/v1/admin/error-telemetry` | `get_error_telemetry` | `backend/routers/user.py:358` |

## Swift-to-Backend Bridge

| Swift caller/source | Path fragment | Contract status |
|---|---|---|
| `ios/StockApp/stockme/stockme/Views/AnalysisScreen.swift:164` | `/analyze` | Backend decorator exists or dynamic match likely |
| `ios/StockApp/stockme/stockme/Views/StrategyLabScreen.swift:143` | `http://127.0.0.1:8000/api/v1/analysis/backtest` | Verify dynamic construction |


## Verified Swift Client Paths By Area

| Area | Client paths | Source | Backend match |
|---|---|---|---|
| Auth | `POST /login`, `POST /register` | `ios/StockApp/stockme/stockme/NetworkManager.swift:191`, `:213` | `backend/routers/auth.py:11`, `:27` |
| Analysis job model | `POST /analyze`, `GET /analyze/job/{job_id}`, `POST /analyze/{job_id}/cancel`, `GET /analyze/active` | `NetworkManager.swift:336`, `:354`, `:379`, `:392` | `backend/routers/analysis.py:487`, `:561`, `:585`, `:574` |
| Portfolio/watchlist/alerts | `/portfolio/{user_id}`, `POST /portfolio`, `PUT /portfolio/note`, `DELETE /portfolio/remove`, `PUT /portfolio/update`, `/watchlist/*`, `/alerts/*` | `NetworkManager.swift:426`, `:461`, `:486`, `:536`, `:600` | `backend/routers/portfolio.py`, `backend/routers/user.py`, `backend/routers/alerts.py` |
| Market/profile | `/market-indices`, `/sector-performance`, `/nifty-history`, `/quarterly-financials`, `/macro-strip`, `/analyst-ratings`, `/quick-info`, `/search`, `/api/v1/stock-profile`, `/api/v1/market/stock-history` | `NetworkManager.swift:523`, `:643`, `:670`, `:682`, `:758`, `:804` | `backend/routers/market.py`, `backend/routers/analysis.py:180` |
| Sidebar/earnings/ideas | `/api/v1/market/pulse`, `/momentum`, `/macro-alternatives`, `/institutional-flow`, `/dashboard`, `/dashboard-pulse`, `/api/v1/earnings/*`, `/api/v1/ideas/*`, admin error logs | `NetworkManager+Sidebar.swift:61`, `:186`, `:242`, `:273`, `:331` | `backend/routers/market.py` |
| Home feed | `/api/v1/home-feed`, `/api/v1/portfolio/valuation-history` | `HomeFeedService.swift:8`, `:35` | `backend/routers/analysis.py:831`, `backend/routers/portfolio.py:1648` |
| Direct view calls | `POST /api/v1/screener/natural-language`, `POST /api/v1/copilot/chat`, `POST/GET /api/v1/portfolio/stress-test`, `GET /portfolio/correlation`, `GET /api/v1/home-feed` | `NLScreenerScreen.swift:35`, `CopilotScreen.swift:441`, `StressTestScreen.swift:209`, `CorrelationMatrixScreen.swift:138`, `NewsMultimediaView.swift:276` | Matching decorators found in focused routers. |

## Major Request Contracts

### Analysis job

- Request: `POST /analyze` with `AnalyzeRequest` (`ticker`, `exchange`, optional `user_id`, `scan_type`, `deep_scan`, language/debate/risk fields).
- Cache-hit response: complete normalized analysis JSON with `_cache_type = CACHE HIT`.
- Async response: `202` body `{job_id, status: QUEUED, ticker, scan_type}`.
- Conflict response: `409` body with `error_code=ALREADY_RUNNING` and active `job_id`.
- Polling: `GET /analyze/job/{job_id}?user_id=...` returns job state, progress/checkpoints, and `result` when succeeded.

### Portfolio stress test

- Request: `POST /api/v1/portfolio/stress-test` with user/group/scenario inputs from `StressTestRequest`.
- Response: job envelope from `stress_test_jobs.start_job`; polling through `GET /api/v1/portfolio/stress-test/{job_id}` and progress route.
- Dashboard: `GET /api/v1/dashboard/stress-test-jobs` lists durable stress-test jobs.

### Home feed

- Request: `GET /api/v1/home-feed?user_id=...&ticker=...` with optional bearer token.
- Behavior: invalid token degrades to anonymous feed for public content rather than hard failing when `user_id` is not authorized.
- Response: recent `news_articles`/`youtube_videos`, with fallback widening when recent rows are absent.

### Market dashboard

- Request: `GET /api/v1/market/dashboard` and `GET /api/v1/market/dashboard-pulse`.
- Response: aggregate market cards for iOS sidebar/earnings/technical momentum surfaces.
- Failure behavior: returns endpoint-specific fallback/error payloads and may log to admin error tables.

## Known Stale or Risky Names

- Do not document `POST /api/v1/analyze` as current; current analysis start route is `POST /analyze`.
- Do not document `POST /api/v1/nl-screener`; current natural-language screener is `POST /api/v1/screener/natural-language`.
- Do not document `GET /api/v1/sector-rotation`; current route is `GET /api/v1/market/sector-rotation`.
- `StrategyLabScreen.swift` contains a hardcoded `http://127.0.0.1:8000/api/v1/analysis/backtest` call; this differs from the shared `NetworkManager.baseURL` pattern.
