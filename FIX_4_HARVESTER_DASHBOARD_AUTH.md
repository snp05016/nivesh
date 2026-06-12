# FIX #4: Auth on Dashboard & Harvester Endpoints

Paste into Claude Code. Execute without asking questions.

## PROBLEM

7 endpoints have zero authentication — anyone can access them:
- `GET /api/v1/dashboard/stream` — streams live analysis progress
- `GET /harvester/feed` — all harvested expert cards
- `GET /harvester/governance/{ticker}` — governance intelligence
- `GET /harvester/sources` — source health (OK to be public, skip this one)
- `GET /harvester/search` — full-text search across cards
- `POST /harvester/trigger/scrape` — triggers scraping (admin-only)
- `GET /harvester/stats` — harvester statistics (admin-only)

## FIX: Add auth to 5 endpoints, leave /sources public

### FILE 1: backend/routers/dashboard.py

**Current state:** The SSE endpoint has no auth. Anyone can stream analysis progress.

**Fix:** Add token validation. If no valid token, return 401 before opening the SSE stream.

The endpoint already accepts `user_id` as a query param. Validate it matches the token.

```python
from helpers import verify_access_token

@router.get("/api/v1/dashboard/stream")
async def dashboard_stream(request: Request, user_id: int = None, authorization: str = Header(None)):
    # Validate auth
    if authorization:
        try:
            token_user_id = verify_access_token(authorization)
            if user_id and token_user_id != user_id:
                raise HTTPException(status_code=403, detail="user_id does not match token")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    else:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    # ... existing SSE streaming logic ...
```

### FILE 2: backend/routers/harvester.py

**Current state:** All 6 endpoints are public.

**Fix:** Add `verify_access_token` to data-serving endpoints. Add `require_admin` to admin endpoints.

```python
from helpers import verify_access_token, require_admin
from fastapi import Header, HTTPException

# ── Data endpoints: require valid user token ──

@router.get("/harvester/feed")
def harvester_feed(limit: int = 20, ticker: str = None, authorization: str = Header(None)):
    verify_access_token(authorization)
    # ... existing logic ...

@router.get("/harvester/governance/{ticker}")
def harvester_governance(ticker: str, authorization: str = Header(None)):
    verify_access_token(authorization)
    # ... existing logic ...

@router.get("/harvester/search")
def harvester_search(q: str, limit: int = 20, authorization: str = Header(None)):
    verify_access_token(authorization)
    # ... existing logic ...

# ── Admin endpoints: require admin token ──

@router.post("/harvester/trigger/scrape")
def harvester_trigger_scrape(source: str = "all", limit: int = 20, authorization: str = Header(None)):
    require_admin(authorization)
    # ... existing logic ...

@router.get("/harvester/stats")
def harvester_stats(authorization: str = Header(None)):
    require_admin(authorization)
    # ... existing logic ...

# ── Public endpoint: leave as-is ──

@router.get("/harvester/sources")
def harvester_sources():
    # No auth needed — health check endpoint
    # ... existing logic ...
```

### FILE 3: iOS NetworkManager — Pass auth token to harvester calls

**Path:** `ios/StockApp/stockme/stockme/NetworkManager.swift`

The harvester fetch functions in NetworkManager (around line 1225) need to include the auth token in the request header.

Find the `harvesterBaseURL` section and ensure every harvester request includes:

```swift
var request = URLRequest(url: url)
request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
```

If the harvester functions use `async let data = URLSession.shared.data(for: request)` without setting the header, they'll get 401s after this change.

Pattern to follow (copy from existing authenticated endpoints):

```swift
func fetchHarvesterFeed(limit: Int = 20, ticker: String? = nil) async throws -> [HarvestedCard] {
    var urlStr = "\(harvesterBaseURL)/harvester/feed?limit=\(limit)"
    if let ticker = ticker { urlStr += "&ticker=\(ticker)" }
    guard let url = URL(string: urlStr) else { throw NetworkError.invalidURL }
    
    var request = URLRequest(url: url)
    request.timeoutInterval = 15
    if let token = authToken {
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
    }
    
    let (data, response) = try await URLSession.shared.data(for: request)
    // ... decode ...
}
```

Do this for all 3 data endpoints: `fetchHarvesterFeed`, `fetchGovernanceCards`, `fetchHarvesterSources` (actually skip sources — it stays public).

## VERIFY

```bash
# 1. Unauthenticated requests should return 401
curl -i http://localhost:8001/harvester/feed?limit=5
# Expected: HTTP/1.1 401 Unauthorized

# 2. Authenticated requests should work
curl -H "Authorization: Bearer $(cat /root/nivesh/backend/.env | grep AUTH_TOKEN | cut -d= -f2)" \
     http://localhost:8001/harvester/feed?limit=5
# Expected: 200 with JSON array

# 3. Public endpoint still works without auth
curl http://localhost:8001/harvester/sources
# Expected: 200

# 4. Admin endpoints reject non-admin tokens
curl -X POST "http://localhost:8001/harvester/trigger/scrape?source=sebi"
# Expected: 401 or 403

# 5. iOS app still loads harvester data (test on device after changes)
```

## DO NOT
- Don't change the endpoint paths or response format
- Don't add auth to `/harvester/sources` — it's a health check
- Don't change the SSE event format — iOS `AgentStreamClient` depends on it
- Don't remove any existing functionality
- If `verify_access_token` or `require_admin` signature differs from assumed, read `helpers.py` and adapt
