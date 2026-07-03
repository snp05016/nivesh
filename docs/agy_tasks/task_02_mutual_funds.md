# AGY Task 02: Mutual Funds Stack Implementation

**Objective:** Implement Mutual Fund discovery, comparison, tracking, and SIP calculations (Section 6 of the feature stack).

**Execution Strategy:** Dispatch **4 subagents** in parallel.
1. **Frontend MF Agent:** Builds `MutualFundDiscoveryView.swift` and `FundDetailView.swift`.
2. **Backend MF Router Agent:** Builds the API endpoints and `MutualFund` database schema.
3. **MF Harvester Agent:** Builds `amfi_nav_harvester.py` to scrape daily NAVs.
4. **MF Math Agent:** Builds SIP, SWP, STP, and rolling return calculation engines.

**Prompt to trigger (Paste in AGY):**
`/goal Execute docs/agy_tasks/task_02_mutual_funds.md. Dispatch 4 subagents to build the full-stack Mutual Funds feature. Enforce strict boundaries (harvesters in services, UI in iOS). Mark Section 6 as complete in money_control_feature_stack.md when done.`
