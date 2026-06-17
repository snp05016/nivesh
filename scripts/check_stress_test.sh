#!/usr/bin/env bash
# Check status of running/recent stress test jobs on the Nivesh server
# Usage:
#   bash scripts/check_stress_test.sh              # show running jobs
#   bash scripts/check_stress_test.sh JOB_ID       # show specific job details
set -euo pipefail

MODE="${1:-running}"

ssh saumyapatel@192.168.1.122 "
cd /home/saumyapatel/Desktop/nivesh/backend
PYTHONPATH=.:../tradingagents-core ../venv/bin/python3 -c \"
import json, sys
sys.path.insert(0, '.')
from routers.stress_test import _jobs as stress_jobs, _lock

with _lock:
    jobs = dict(stress_jobs)
    if not jobs:
        print('No stress test jobs found.')
        sys.exit(0)
    
    mode = '$MODE'
    for jid, job in jobs.items():
        if mode != 'running' and jid != mode and not jid.startswith(mode):
            continue
        status = job.get('status', '?')
        stage = job.get('stage', '-')
        pct = job.get('progress_pct', 0)
        tickers = job.get('ticker_count', '?')
        print(f'Job: {jid}')
        print(f'  Status:   {status}')
        print(f'  Stage:    {stage}')
        print(f'  Progress: {pct}% ({tickers} tickers)')
        if job.get('error'):
            print(f'  Error:    {job[\"error\"]}')
        if job.get('result'):
            results = job['result']
            for r in results:
                scores = r.get('scores', {})
                print(f'  Scenario: {r[\"name\"]}')
                print(f'    Impact:  {r[\"impact_pct\"]}% ({r[\"impact_inr\"]:.0f} INR)')
                for k, v in scores.items():
                    print(f'    {k}: {v}')
        print()
"
