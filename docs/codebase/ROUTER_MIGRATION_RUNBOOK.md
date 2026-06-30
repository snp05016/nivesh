# Router Refactoring Runbook: Migrating Business Logic out of FastAPI Routers

## Objective
Migrate direct database access (`session.query`) and complex business logic from FastAPI routers (specifically `backend/routers/market.py` and `backend/routers/portfolio.py`) into the Controller-Service-Repository pattern without breaking external API contracts.

## Motivation
Currently, `market.py` and `portfolio.py` contain thousands of lines of code where routing, business logic, and data access are tightly coupled. This violates the architectural ordinance of Nivesh (AGENTS.md Pillar II: Backend Architecture) which strictly enforces:

*   **Controller (`routers/`):** HTTP validation, rate limiting, and spawning processes.
*   **Service (`services/`):** All business logic, LLM orchestration, and computations.
*   **Repository (`repositories/`):** `get_session()` context manager and database queries.
*   **ABSOLUTE RULES:** Business logic in routers is FORBIDDEN. DB queries in services are FORBIDDEN.

## Pre-Requisites & Analysis (Mandatory Steps)
Before modifying any router endpoint, you MUST perform the following:

1.  **Analyze with GitNexus:** Run `gitnexus_impact({target: "<function_name>", direction: "upstream"})` to identify all affected execution flows and callers. Do not proceed blindly.
2.  **Review API Contracts:** Inspect the expected Pydantic response models and the exact JSON payload returned by the endpoint. 
3.  **Deconstruct the Logic:** Read the entire endpoint to isolate (a) Data Access (Repository layer), (b) Business Logic (Service layer), and (c) Request/Response Mapping (Controller layer).

---

## Migration Workflow

### Step 1: Extract Data Access to the Repository Layer
Data access must be moved to `backend/repositories/`.

*   Identify all `session.query(...)` calls in the router endpoint.
*   Create or update a corresponding repository file (e.g., `portfolio_repository.py`, `market_repository.py`).
*   Implement methods that use the `get_session()` context manager (or accept a session parameter if participating in an ongoing transaction).
*   **Rule:** Repository methods should only return ORM models, dictionaries, or basic data structures. Never put business logic or data transformation here.

### Step 2: Extract Business Logic to the Service Layer
Business logic must be moved to `backend/services/`.

*   Create or update a corresponding service file (e.g., `portfolio_service.py`, `market_service.py`).
*   Move all data transformation, computation, AI/LLM orchestration, and integration logic here.
*   The Service method should call the Repository methods to fetch necessary data.
*   **Rule:** NO DB queries in services! Always call the Repository layer.

### Step 3: Refactor the Router into a Thin Controller
Update the FastAPI router endpoint to act strictly as a controller.

*   Remove `with get_session() as session:` blocks from the router (unless required to pass a session to a service, though bounding transactions at the repository/service level is preferred).
*   Call the appropriate Service method and pass validated request parameters.
*   Return the exact same JSON structure originally returned by the router.

### Step 4: Verification
1.  Run `gitnexus_detect_changes()` before committing to verify the blast radius.
2.  Ensure the response format perfectly matches the original structure.
3.  Verify that all exceptions previously handled in the router are now handled gracefully in the service or caught appropriately in the router.

---

## Critical Risks & Anti-Patterns to Avoid

### 1. Breaking Swift `Codable` Decoding (CRITICAL RISK)
The iOS app relies on exact JSON keys and types for Swift `Codable` structs.
*   If an endpoint returns `{"warnings": [{"ticker": "AAPL", "is_bearish": true}]}`, you **CANNOT** change it to `{"alerts": [{"symbol": "AAPL", "bearish": true}]}`.
*   Changing a key name, changing a type (e.g., `int` to `string`), or returning `""` instead of `null` (`None`) for an Optional field will silently break decoding, causing immediate crashes or blank screens on iOS. 
*   **Action:** Copy the original return dictionary structure verbatim into the new service response mapping.

### 2. Context Manager Leaks (Detached Instances)
When moving logic out of routers, ensure `get_session()` is properly managed. 
*   Do not return unevaluated queries or ORM objects attached to a closed session (this will throw `DetachedInstanceError`).
*   Fetch and fully serialize data into dictionaries or Pydantic models before the session closes in the repository or service layer.

### 3. Missing Background Process Integrity
If the original router logic spawned a `multiprocessing.Process` (e.g., for heavy AI analysis), ensure the new service continues to do so correctly. Processes must re-import dependencies and `load_dotenv(override=True)` inside the subprocess, as per Nivesh architecture rules.

### 4. Bypassing Global State Locks
If the router previously interacted with global state (like `_running_analyses`), the extracted service must continue using a dedicated `threading.Lock` to prevent race conditions.
