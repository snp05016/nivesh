# Nivesh API Contract Map

> Last verified: 2026-06-15 from FastAPI decorators and Swift URL call sites. This is a practical bridge map, not an OpenAPI replacement.

## Route Prefix Rules That Matter

Most routers are included without a prefix in `backend/main.py`. Two important exceptions:

| Router | Include behavior | Effective path example |
|---|---|---|
| `sector_rotation.router` | included with `prefix="/api/v1"`; router itself has `prefix="/market"` | `GET /api/v1/market/sector-rotation` |
| `options_strategy.router` | router itself has `prefix="/api/v1"` | `POST /api/v1/options/payoff` |
| `harvester.router` | router itself has `prefix="/harvester"` | `GET /harvester/feed` |
| `anomalies.router` | router itself has `prefix="/api/v1/market"` | `GET /api/v1/market/anomalies` |

Do not assume every current route starts with `/api/v1`.

## Verified Swift to Backend Bridges

| Feature | Swift caller | Effective backend route | Backend source | Status |
|---|---|---|---|---|
| Login | `NetworkManager.login` | `POST /login` | `routers/auth.py` | Match |
| Register | `NetworkManager.register` | `POST /register` | `routers/auth.py` | Match |
| Start analysis | `NetworkManager.analyze`, `startAnalysisJob` | `POST /analyze` | `routers/analysis.py` | Match |
| Active analysis job | `NetworkManager.getActiveJob` | `GET /analyze/active` | `routers/analysis.py` | Match |
| Analysis job status | job polling in analysis flow | `GET /analyze/job/{job_id}` | `routers/analysis.py` | Match |
| Batch analysis | backend batch status flow | `POST /analyze/batch`, `GET /analyze/batch/{batch_id}` | `routers/analysis.py` | Backend exists |
| Quick info | `NetworkManager.quickInfo` | `GET /quick-info` | `routers/analysis.py` | Match |
| Home feed | `HomeFeedService.fetchFeed` | `GET /api/v1/home-feed` | `routers/analysis.py` | Match |
| Technical signals | iOS market/home surfaces | `GET /api/v1/technical-signals` | `routers/analysis.py` | Backend exists |
| Portfolio holdings | `NetworkManager.getPortfolio` | `GET /portfolio/{user_id}` | `routers/portfolio.py` | Match |
| Add holding | `NetworkManager.addHolding` | `POST /portfolio` | `routers/portfolio.py` | Match |
| Remove holding | `NetworkManager.removeHolding` | `DELETE /portfolio/remove` | `routers/portfolio.py` | Match |
| Update holding | `NetworkManager.updateHolding` | `PUT /portfolio/update` | `routers/portfolio.py` | Match |
| Portfolio note | `NetworkManager.saveNote` | `PUT /portfolio/note` | `routers/portfolio.py` | Match |
| Morning summary | `NetworkManager.getMorningSummary` | `GET /morning-summary/{user_id}` | `routers/portfolio.py` | Match, LLM cost |
| Portfolio charts | `NetworkManager.fetchPortfolioCharts` | `GET /api/v1/portfolio/charts/{user_id}` | `routers/portfolio.py` | Match |
| Valuation history | `NetworkManager.fetchValuationHistory`, `HomeFeedService.fetchValuationHistory` | `GET /api/v1/portfolio/valuation-history` | `routers/portfolio.py` | Match |
| Risk analysis | `NetworkManager.fetchRiskAnalysis` | `GET /portfolio/risk-analysis/{user_id}` | `routers/portfolio.py` | Match |
| Red flags | `NetworkManager.fetchRedFlags` | `GET /portfolio/red-flags/{user_id}` | `routers/portfolio.py` | Match, LLM cost |
| Macro impact | `NetworkManager.fetchMacroImpact` | `GET /macro-impact/{user_id}` | `routers/portfolio.py` | Match, LLM cost |
| Timeframe conflicts | `NetworkManager.fetchTimeframeConflicts` | `GET /portfolio/timeframe-conflicts/{user_id}` | `routers/portfolio.py` | Match |
| Trade journal CRUD | `NetworkManager.fetch/add/update/deleteTradeJournal*` | `/trade-journal...` | `routers/portfolio.py` | Match |
| Trade journal stats | `NetworkManager.fetchTradeJournalStats` | `GET /trade-journal/{user_id}/stats` | `routers/portfolio.py` | Match, LLM cost possible |
| Excel export | `NetworkManager.exportPortfolioExcel` | `GET /portfolio/export/excel/{user_id}` | `routers/portfolio.py` | Match |
| PDF export | frontend export flow if wired | `GET /portfolio/export/pdf/{user_id}` | `routers/portfolio.py` | Backend exists, LLM cost |
| Market indices | `NetworkManager.getMarketIndices` | `GET /market-indices` | `routers/market.py` | Match |
| Search stocks | `NetworkManager.searchStocks` | `GET /search` | `routers/market.py` | Match |
| Sector performance | `NetworkManager.getSectorPerformance` | `GET /sector-performance` | `routers/market.py` | Match |
| Stock history | `NetworkManager.fetchStockHistory` | `GET /api/v1/market/stock-history` | `routers/market.py` | Match |
| Stock profile | `NetworkManager.fetchStockProfile` | `GET /api/v1/stock-profile` | `routers/market.py` | Match |
| Piotroski | `NetworkManager.fetchPiotroski` | `GET /fundamentals/piotroski/{ticker}` | `routers/portfolio.py` | Match |
| Market pulse | `NetworkManager.fetchMarketPulse` | `GET /api/v1/market/pulse` | `routers/market.py` | Match |
| Momentum | `NetworkManager.fetchMomentum` | `GET /api/v1/market/momentum` | `routers/market.py` | Match |
| Macro alternatives | `NetworkManager.fetchMacroAlternatives` | `GET /api/v1/market/macro-alternatives` | `routers/market.py` | Match |
| Institutional flow | `NetworkManager.fetchInstitutionalFlow` | `GET /api/v1/market/institutional-flow` | `routers/market.py` | Match |
| Market dashboard | `NetworkManager.fetchMarketDashboard` | `GET /api/v1/market/dashboard` | `routers/market.py` | Match |
| Dashboard pulse | `NetworkManager.fetchExtendedMarketDashboard` | `GET /api/v1/market/dashboard-pulse` | `routers/market.py` | Match |
| Earnings feed | `NetworkManager.fetchEarningsFeed`, sidebar feed | `GET /api/v1/earnings/feed` | `routers/market.py` | Match |
| Earnings calendar | `NetworkManager.fetchEarningsCalendarDay`, sidebar calendar | `GET /api/v1/earnings/calendar` | `routers/market.py` | Match |
| Earnings estimates | `NetworkManager.fetchEarningsEstimates` | `GET /api/v1/earnings/estimates` | `routers/market.py` | Match |
| Earnings alerts | `NetworkManager.setEarningsAlert` | `POST /api/v1/earnings/alerts` | `routers/market.py` | Match |
| Ideas advisors/feed | `NetworkManager.fetchAdvisors`, `fetchIdeasFeed` | `GET /api/v1/ideas/advisors`, `GET /api/v1/ideas/feed` | `routers/market.py` | Match |
| Alerts | `NetworkManager.addAlert/getAlerts/removeAlert` | `POST /alerts/add`, `GET /alerts/{user_id}`, `DELETE /alerts/remove` | `routers/alerts.py` | Match |
| Watchlist | `NetworkManager.add/remove/getWatchlist` | `/watchlist/...` | `routers/user.py` | Match |
| Device notifications | `NetworkManager.registerDeviceToken`, test/push helpers | `/notifications/...` | `routers/user.py` | Match |
| Copilot chat | `CopilotScreen` service path | `POST /api/v1/copilot/chat` | `routers/copilot.py` | Match, LLM cost |
| Natural language screener | `NLScreenerScreen` expected API | `POST /api/v1/screener/natural-language` | `routers/nl_screener.py` | Match if screen uses current helper |
| Stress test | `StressTestScreen` expected API | `POST /api/v1/portfolio/stress-test` | `routers/stress_test.py` | Match if screen uses current helper |
| Sector rotation | sector rotation screen/helper | `GET /api/v1/market/sector-rotation` | `routers/sector_rotation.py` | Match current effective path |
| Correlation | correlation screen/helper | `GET /portfolio/correlation` | `routers/correlation.py` | Match current effective path |
| Options payoff | `NetworkManager.getOptionsPayoff` | `POST /api/v1/options/payoff` | `routers/options_strategy.py` | Match |
| Harvester feed/governance/sources | `NetworkManager.fetchHarvester*` | `GET /harvester/feed`, `/harvester/governance/{ticker}`, `/harvester/sources` | `routers/harvester.py` | Partial Swift coverage |
| Brainstorming | `NetworkManager.brainstorm` | `POST /brainstorm` | `routers/brainstorming.py` | Match |

## Backend Routes Without Obvious Primary Swift Wrapper

These may be admin, diagnostics, legacy, or screen-local calls. Verify before deleting:

- `GET /ping`, `/health`, `/health/live`, `/healthz`
- `GET /dashboard-data`, `/dashboard-user-data`, `GET /api/v1/dashboard/stream`
- Analysis cache/admin routes: `/analyze/cache-status/{ticker}`, `/analyze/cache/{ticker}/invalidate`, `/analyze/slots`, `/token-stats`
- Market data routes: `/dividends/{ticker}`, `/mf/{scheme_code}`, `/block-deals/{ticker}`, `/fii-dii-flow`, `/macro-context/{ticker}`, `/ipo-calendar`, `/sector-weekly`, `/api/v1/options/chain/{ticker}`
- Admin diagnostics: `/api/v1/admin/error-logs`, `/api/v1/admin/earnings-errors`, `/api/v1/admin/ideas-errors`, `/api/v1/admin/notification-errors`, `/api/v1/admin/error-telemetry`
- Harvester admin/search: `/harvester/search`, `/harvester/trigger/scrape`, `/harvester/stats`
- Legacy/alternate endpoints: `/batch`, `/portfolio/add`, `/portfolio/history/{user_id}`, `/portfolio/stress-test`, `/market/screener`, `/market/sentiment-trend/{ticker}`

## Known Stale Names To Avoid

These names appeared in older docs but do not match the current mounted routes:

| Stale path/name | Current path or note |
|---|---|
| `POST /api/v1/analyze` | Use `POST /analyze` |
| `GET /api/v1/analysis/history/{user_id}` | No matching current route found in decorators; verify `AnalysisEngineManager` before referencing |
| `GET /api/v1/market/search` | Use `GET /search` for current Swift `searchStocks` |
| `GET /api/v1/market/quick-info/{ticker}` | Use `GET /quick-info?ticker=...&exchange=...` |
| `GET /api/v1/market/movers` | Current backend has `GET /api/v1/market/top-movers`; verify Swift caller before use |
| `POST /api/v1/nl-screener` | Use `POST /api/v1/screener/natural-language` |
| `POST /api/v1/stress-test` | Use `POST /api/v1/portfolio/stress-test` |
| `GET /api/v1/sector-rotation` | Use `GET /api/v1/market/sector-rotation` |
| `GET /api/v1/correlation` | Use `GET /portfolio/correlation` |
| `GET /api/v1/earnings-surprise` | Current router exposes `/api/v1/earnings/surprises` and `/api/v1/earnings/surprise-history/{ticker}` |
| `POST /api/v1/rag/upload` | No mounted route found in current `backend/main.py` includes |
| `GET /api/v1/pkscreener/run` or `POST /api/v1/pkscreener/run` | No mounted router found; PKScreener currently appears as service/deep-scan integration |
| `GET /api/v1/piotroski/breakdown/{ticker}` | Use `GET /fundamentals/piotroski/{ticker}` |
| `GET /api/v1/strategy/mock-trades` | No matching current route found; strategy router exposes `POST /api/v1/analysis/backtest` |

## Regeneration Hints

Use source extraction rather than manual guesses:

```bash
python3 - <<'PY'
import ast, pathlib
root=pathlib.Path('backend')
for f in [root/'main.py'] + sorted((root/'routers').glob('*.py')):
    try: tree=ast.parse(f.read_text())
    except Exception: continue
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {'get','post','put','delete','patch'}:
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        print(f'{f}:{node.lineno}:{dec.func.attr.upper()} {dec.args[0].value} -> {node.name}')
PY
```
