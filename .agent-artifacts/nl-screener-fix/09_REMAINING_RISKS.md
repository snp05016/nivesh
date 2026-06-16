# Remaining Risks

## 1. Local Caching Stale Data
In `backend/services/nl_screener.py`, responses are cached in a local in-memory disk cache for 3600 seconds (1 hour). If users experienced the numeric-values bug earlier today on the exact query they typed, the FastAPI server may continue to return the old, non-stringified cached payload until the cache expires or the server is restarted. 
**Mitigation:** The server was successfully restarted via the deployment command, clearing the volatile memory cache.

## 2. SQL Injection / Invalid Parameters
The dynamic SQL query builder heavily parameterizes inputs (e.g. `AND pe <= :pe_max`). However, because `filters` comes directly from an LLM parsed JSON block, unexpected keys or extremely malformed values could hypothetically cause SQLite execution errors if `sqlalchemy.text` binding fails. 
**Mitigation:** The SQL builder logic uses explicit keys (`filters.get("pe_max")`) rather than dynamically injecting columns, effectively preventing direct SQL injection. If execution fails, `db_failed` safely trips to `True` and falls back to default tickers.

## 3. Rate Limiting yfinance 
The backend loops through resulting tickers and executes `yf.Ticker(t).info` concurrently. If a broad query yields 100+ tickers, executing 100 concurrent Yahoo Finance requests might trigger temporary IP bans from Yahoo Finance, resulting in empty or incomplete `company` names and `score` data for the user.
**Mitigation:** The SQL query intentionally appends `ORDER BY market_cap DESC LIMIT 10`, capping the maximum concurrent network requests to exactly 10.

## 4. Unmapped Filter Presentation in iOS
While iOS correctly parses the filters now (`[String: String]`), it doesn't have a sophisticated UI to render "pe_max: 20" into a human-readable filter chip (e.g., "P/E < 20"). The raw keys will be rendered in the UI. 
**Mitigation:** This is an aesthetic limitation rather than a crash risk. A future improvement could map the `parsed_filters` dict into a structured list of localized string labels, similar to the suggested contract from the prompt `{"field": "roe", "operator": ">", "value": 15, "label": "ROE greater than 15%"}`. For now, the existing iOS contract was successfully preserved.
