# AGY Task 01: IPO Stack Implementation

**Objective:** Implement the IPO Hub, calendar, and subscription status tracking (Section 5 of the feature stack).

**Execution Strategy:** Dispatch **2 subagents** in parallel.
1. **Frontend IPO Agent:** Responsible for building `IPOHubView.swift`, `IPOCalendarView.swift`, and all related view models in `ios/StockApp/`.
2. **Backend IPO Agent:** Responsible for the `IPOService`, FastAPI routes, and database models in `backend/`.

**Prompt to trigger (Paste in AGY):**
`/goal Execute docs/agy_tasks/task_01_ipo_stack.md. Dispatch 2 subagents (Frontend and Backend) to implement the IPO tracking features. Ensure strict separation of concerns as per AGENTS.md. Mark the IPO section as complete in money_control_feature_stack.md when done.`
