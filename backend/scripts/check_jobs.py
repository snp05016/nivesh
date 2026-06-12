"""Check analysis job status. Usage: python3 check_jobs.py [running|--all|--stuck|TICKER]"""
import sys, json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/root/nivesh/backend')
from database import get_session, AnalysisJob

mode = sys.argv[1] if len(sys.argv) > 1 else 'running'

with get_session() as s:
    if mode == 'running':
        jobs = s.query(AnalysisJob).filter(AnalysisJob.status == 'RUNNING').order_by(AnalysisJob.created_at.desc()).all()
    elif mode == 'stuck' or mode == '--stuck':
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        jobs = s.query(AnalysisJob).filter(
            AnalysisJob.status == 'RUNNING', AnalysisJob.created_at < cutoff
        ).order_by(AnalysisJob.created_at.desc()).all()
    elif mode == '--all':
        jobs = s.query(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(20).all()
    else:
        t = mode.upper()
        jobs = s.query(AnalysisJob).filter(AnalysisJob.ticker == t).order_by(AnalysisJob.created_at.desc()).limit(5).all()

    if not jobs:
        print('No jobs found.')
        sys.exit(0)

    now = datetime.now(timezone.utc)
    print(f"{'TICKER':<12} {'STATUS':<12} {'STAGE':<18} {'PROG':>4}  {'AGE':>7}  {'SCAN':<8}  {'JOB ID'}")
    print('-' * 95)
    for j in jobs:
        ct = j.created_at
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=timezone.utc)
        age = (now - ct).total_seconds()
        m, s = divmod(int(age), 60)
        age_s = f'{m}m{s}s'
        name  = (j.ticker or '').ljust(12)
        stat  = (j.status or '').ljust(12)
        stage = (j.stage or '-').ljust(18)
        pct   = f'{j.progress_pct or 0}%'.rjust(4)
        scan  = (j.scan_type or 'standard').ljust(8)
        print(f'{name} {stat} {stage} {pct}  {age_s:>7}  {scan}  {j.job_id}')
        if j.error:
            print(f'  Error: {str(j.error)[:200]}')
