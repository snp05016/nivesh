# Nivesh Project Instructions

## Backend Deployment & Management
- **Deployment:** Every time you make a code change to the backend (`backend/`), you MUST follow the deployment procedure in the root `AGENTS.md` §6.5 (Deployment & Remote Verification).
- **Syncing Ignored Files:** When deploying to the server, you MUST ensure that critical files and directories ignored by `.gitignore` (such as `.env`, `tradingagents-core`, etc.) are explicitly synced to the server (e.g., using `rsync` or `scp`).
- **Foreground Processes:** NEVER start anything that has an infinite loop (like `uvicorn` or any other server) in the foreground. If you must run a server, ALWAYS use the `is_background: true` parameter in the `run_shell_command` tool.
- **Command Timeouts:** Make sure that all shell commands have a 10-minute timeout enforced to prevent them from hanging indefinitely.
- **Local Server Management:** When running or restarting the backend server locally for testing, ensure you close any existing processes on the required ports before starting it again.
  - To stop and restart the local server, run: `bash backend/run.sh` from the repository root (this script handles killing existing processes on port 8000 and starting uvicorn).
