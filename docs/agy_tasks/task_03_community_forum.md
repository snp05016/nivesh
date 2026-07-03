# AGY Task 03: Community and Forum Stack

**Objective:** Implement message boards, polls, and user-generated content features (Section 12 of the feature stack).

**Execution Strategy:** Dispatch **2 subagents** in parallel.
1. **Fullstack Forum Agent:** Builds the SwiftUI forum views and the FastAPI CRUD endpoints for threads/posts.
2. **Moderation Agent:** Implements ML-based spam filtering and sentiment tagging on the backend.

**Prompt to trigger (Paste in AGY):**
`/goal Execute docs/agy_tasks/task_03_community_forum.md. Dispatch 2 subagents to implement the Community Forum and ML moderation tools. Respect the Controller-Service-Repository pattern. Mark Section 12 as complete in money_control_feature_stack.md when done.`
