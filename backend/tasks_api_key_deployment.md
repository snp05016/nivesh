# Deployment & Fix TODO

- [x] Check local git status and commit all changes made to the backend (dashboard, harvesters, main.py).
- [x] Sync the updated `tradingagents-core` directory to the remote server, as it contains critical fixes for the LLM providers but is in `.gitignore`.
- [x] Verify the `.env` file on the remote server to ensure `DEEPSEEK_API_KEY` is present.
- [x] Run `./deploy_update.sh` to push local code and restart the remote service (adjusted server systemd paths as needed).
- [x] Test the `/analyze` endpoint on the live server (`165.22.221.18`) to ensure the "API key not set" error is resolved and fixed Nginx timeouts (120s -> 300s).
- [x] Verify the live dashboard to confirm the new harvester sections and AI health checks are visible.