# Nivesh Project Instructions

## Backend Deployment & Management
- **Deployment:** Every time you make a code change to the backend (located in `/Users/saumya/Desktop/stocks/`), you MUST automatically run the deployment script to push changes to the production server.
  - Command: `bash /Users/saumya/Desktop/stocks/deploy_update.sh "Automated agent update"`
- **Local Server Management:** When running or restarting the backend server locally for testing, ensure you close any existing processes on the required ports before starting it again.
  - To stop and restart the local server, run: `bash /Users/saumya/Desktop/stocks/run.sh` (this script handles killing existing processes on port 8000 and starting uvicorn).
