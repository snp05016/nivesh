"""Display the latest successful AI analysis for a ticker."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from repositories.job_repo import get_latest_successful_monitor_job
from services.ai_engine_monitor import get_ai_engine_job_detail


def _display_latest(ticker: str) -> int:
    latest = get_latest_successful_monitor_job(ticker)
    if not latest:
        print(f"No successful analysis found for {ticker}.")
        return 1

    detail = get_ai_engine_job_detail(str(latest["job_id"]))
    if not detail:
        print(f"No successful analysis found for {ticker}.")
        return 1

    job = detail["job"]
    summary = detail["latest_success_summary"] or {}
    result = job.get("result") or {}

    print("=" * 60)
    print(f"  AI ANALYSIS REPORT - {job.get('ticker')}")
    print("=" * 60)
    print(f"  Date:        {summary.get('analysis_date') or job.get('created_at') or '?'}")
    print(f"  Signal:      {summary.get('signal') or '?'}")
    print(f"  Confidence:  {summary.get('confidence_pct') or '?'}%")
    print(f"  Scan type:   {summary.get('scan_type') or job.get('scan_type') or 'standard'}")
    print(f"  Tier:        {summary.get('analysis_tier') or '?'}")
    print()

    print(f"  Current:     Rs.{summary.get('current_price_inr') or '?'}")
    print(f"  Target 12m:  Rs.{summary.get('target_12m') or '?'}  ({summary.get('upside_12m_pct') or '?'}%)")
    print()

    key_risks = result.get("key_risks") if isinstance(result.get("key_risks"), list) else []
    if key_risks:
        print("  KEY RISKS:")
        for risk in key_risks[:3]:
            print(f"    ! {str(risk)[:120]}")
        print()

    print("=" * 60)
    print(f"  Generated: {job.get('created_at')}")
    print(f"  Job ID:     {job.get('job_id')}")
    print(f"  Tokens:     {job.get('tokens_used') or 'N/A'}")
    return 0


if __name__ == "__main__":
    selected_ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "RELIANCE"
    raise SystemExit(_display_latest(selected_ticker))
