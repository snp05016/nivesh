"""Display the latest successful AI analysis for a ticker."""
import sys, json

sys.path.insert(0, '/root/nivesh/backend')
from database import get_session, AnalysisJob

ticker = sys.argv[1].upper() if len(sys.argv) > 1 else 'RELIANCE'

with get_session() as s:
    job = s.query(AnalysisJob).filter(
        AnalysisJob.ticker == ticker,
        AnalysisJob.status == 'SUCCEEDED'
    ).order_by(AnalysisJob.created_at.desc()).first()

    if not job:
        print(f'No successful analysis found for {ticker}.')
        running = s.query(AnalysisJob).filter(
            AnalysisJob.ticker == ticker, AnalysisJob.status == 'RUNNING'
        ).first()
        if running:
            print(f'Analysis is still RUNNING (stage: {running.stage}, {running.progress_pct}%)')
        sys.exit(1)

    r = json.loads(job.result_json) if isinstance(job.result_json, str) else (job.result_json or {})

    print('=' * 60)
    print(f'  AI ANALYSIS REPORT — {job.ticker}')
    print('=' * 60)
    date_str = r.get("analysis_date") or (job.created_at.strftime("%Y-%m-%d") if job.created_at else "?")
    print(f'  Date:        {date_str}')
    print(f'  Signal:       {r.get("signal", "?")}')
    print(f'  Confidence:   {r.get("confidence_pct", "?")}%')
    print(f'  Scan type:    {job.scan_type or "standard"}')
    print(f'  Tier:         {r.get("analysis_tier", "?")}')
    print()

    # Price & targets
    tp = r.get('target_prices') or {}
    ud = r.get('upside_downside_pct') or {}
    print(f'  Current:      Rs.{r.get("current_price_inr", "?")}')
    print(f'  Target 3m:    Rs.{tp.get("short_term_3m", "?")}  ({ud.get("short_term", "?")}%)')
    print(f'  Target 12m:   Rs.{tp.get("medium_term_12m", "?")}  ({ud.get("medium_term", "?")}%)')
    print(f'  Target 36m:   Rs.{tp.get("long_term_36m", "?")}  ({ud.get("long_term", "?")}%)')
    print()

    # Governance
    print(f'  Gov Score:    {r.get("governance_score", "?")}/100')
    flags = r.get('governance_red_flags') or []
    if flags:
        for f in flags[:5]:
            print(f'    Flag:       {f[:80]}')
    print()

    # Key factors
    kf = r.get('key_factors') or {}
    print('  KEY FACTORS:')
    for k in ['management_quality', 'governance_assessment', 'fundamentals_summary',
               'promoter_fii_dii_activity', 'indian_market_sentiment',
               'turnaround_story', 'global_macro_impact']:
        v = kf.get(k, '')
        if v and v != 'Data not available':
            label = k.replace('_', ' ').title()
            print(f'    {label}: {v[:150]}')
    print()

    # Bull / Bear / Risks
    bull = r.get('bull_case') or []
    bear = r.get('bear_case') or []
    risks = r.get('key_risks') or []
    if bull:
        print('  BULL CASE:')
        for b in bull[:3]: print(f'    + {b[:120]}')
    if bear:
        print('  BEAR CASE:')
        for b in bear[:3]: print(f'    - {b[:120]}')
    if risks:
        print('  KEY RISKS:')
        for rk in risks[:3]: print(f'    ! {rk[:120]}')
    print()

    # Extreme thesis
    et = r.get('extreme_thesis_md') or ''
    if et:
        print(f'  EXTREME THESIS: ({len(et)} chars)')
        print(et[:2000])
    print()

    # What to watch
    wtw = r.get('what_to_watch') or []
    if wtw:
        print('  WHAT TO WATCH:')
        for w in wtw[:5]: print(f'    > {w[:120]}')

    print()
    print('=' * 60)
    print(f'  Generated: {job.created_at}')
    print(f'  Job ID:     {job.job_id}')
    print(f'  Tokens:     {job.tokens_used or "N/A"}')
