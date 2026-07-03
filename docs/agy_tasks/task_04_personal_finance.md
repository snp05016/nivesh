# AGY Task 04: Personal Finance & Loan Marketplace

**Objective:** Implement Bank Account linking, Loan Marketplace, and Fixed Deposits (Section 13 of the feature stack).

**Execution Strategy:** Dispatch **4 subagents** in parallel.
1. **Frontend Finance Agent:** Builds the Finance Tracker and Loan application UI.
2. **Backend Integrations Agent:** Builds mock API integrations for NBFCs and Credit Bureaus.
3. **Security/KYC Agent:** Implements strict SIM-binding and consent-management logic.
4. **Calculators Agent:** Builds EMI, Gratuity, and Tax calculators in pure Python.

**Prompt to trigger (Paste in AGY):**
`/goal Execute docs/agy_tasks/task_04_personal_finance.md. Dispatch 4 subagents to build the Personal Finance stack. Ensure extreme focus on security and KYC data boundaries. Mark Section 13 as complete in money_control_feature_stack.md when done.`
