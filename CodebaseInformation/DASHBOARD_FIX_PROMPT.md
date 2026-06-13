# DASHBOARD FIX — Show Live Analysis Status

Paste into Claude Code. Execute without asking questions.

## PROBLEM

The admin dashboard at `/dashboard` (port 8000) shows active analyses but is missing critical fields: scan type (extreme/deep/standard), progress %, checkpoint timeline, and running duration. The AnalysisJob DB table stores all this data — it's just not surfaced.

## FIX: 3 changes in backend/main.py

### CHANGE 1: Pass scan_type to _dash_start_job

Find `def _dash_start_job` (around line 178). The function signature is:
```python
def _dash_start_job(job_id: str, ticker: str, exchange: str, user_id) -> None:
```

Add `scan_type` parameter:
```python
def _dash_start_job(job_id: str, ticker: str, exchange: str, user_id, scan_type: str = "standard") -> None:
```

And add it to the dict:
```python
    with _dash_lock:
        _active_analyses[job_id] = {
            "job_id": job_id,
            "ticker": ticker.upper(),
            "exchange": exchange,
            "user_id": user_id,
            "scan_type": scan_type,                              # <-- ADD
            "start_ts": datetime.now().isoformat(),
            "stage": "AI agents initializing...",
            "progress_pct": 0,                                   # <-- ADD
        }
```

Then find EVERY call site of `_dash_start_job` in the file (grep for it) and add the `scan_type` argument. Likely call sites are in the `/analyze` endpoint handler.

### CHANGE 2: Update active analyses to pull progress from AnalysisJob DB

Find `def get_dashboard_snapshot()` or the route that returns `/dashboard-data`. Around line 63-68 there's a merge:
```python
merged = {**dict(_active_analyses), **db_jobs}
```

Ensure the `db_jobs` dict includes `progress_pct`, `scan_type`, and `stage` from the AnalysisJob table. Check the `_job_to_dict` or `get_job` function in `database.py` to confirm these fields are returned.

If `db_jobs` is built from a DB query, add the missing columns. If it's built from `_job_to_dict`, ensure that function returns `scan_type`, `stage`, `progress_pct`.

### CHANGE 3: Update the admin HTML to render scan_type, progress %, and elapsed time

Find the active analyses rendering block around line 1736-1742:

```javascript
const active=d.active_analyses||[];
document.getElementById('ac').textContent=active.length+' running';
document.getElementById('ab').innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>`<div class="analysis-item active"><div style="display:flex;justify-content:space-between;align-items:center"><span class="a-ticker">${a.ticker}</span><span class="ts">${ts(a.start_ts)}</span></div><div class="a-meta">${a.exchange||'NSE'} &bull; User ${a.user_id||'N/A'} &bull; running ${ela(a.start_ts)}</div><div class="a-stage"><span class="s-dot"></span>${a.stage||'Processing...'}</div></div>`).join('');
```

Replace with:

```javascript
const active=d.active_analyses||[];
document.getElementById('ac').textContent=active.length+' running';
document.getElementById('ab').innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>{
  const scanLabel = a.scan_type==='extreme'?'EXTREME':a.scan_type==='deep'?'DEEP':'STANDARD';
  const scanColor = a.scan_type==='extreme'?'#ff6b6b':a.scan_type==='deep'?'#f0a040':'#6e7681';
  const pct = a.progress_pct||0;
  const pctColor = pct>=80?'#3fb950':pct>=40?'#d29922':'#6e7681';
  const elapsed = ela(a.start_ts);
  return `<div class="analysis-item active" style="border-left:3px solid ${scanColor}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <span class="a-ticker">${a.ticker||'?'}</span>
      <div style="display:flex;gap:8px;align-items:center">
        <span style="font-size:10px;color:${scanColor};font-weight:700;background:${scanColor}18;padding:2px 8px;border-radius:10px">${scanLabel}</span>
        <span class="ts">${elapsed}</span>
      </div>
    </div>
    <div style="margin-bottom:6px">
      <div style="font-size:10px;color:#6e7681;margin-bottom:3px">${a.exchange||'NSE'} &bull; User ${a.user_id||'N/A'}</div>
      <div style="display:flex;align-items:center;gap:8px">
        <div style="flex:1;height:3px;background:#21262d;border-radius:2px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:${pctColor};border-radius:2px;transition:width 0.5s"></div>
        </div>
        <span style="font-size:10px;color:${pctColor};font-weight:600">${pct}%</span>
      </div>
    </div>
    <div class="a-stage"><span class="s-dot"></span>${a.stage||'Processing...'}</div>
  </div>`;
}).join('');
```

Also add this CSS style in the `<style>` block (search for `.analysis-item` in the CSS around line 928):

```css
.s-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#d29922;margin-right:6px;animation:pulse-dot 1.5s infinite}
@keyframes pulse-dot{0%,100%{opacity:1}50%{opacity:0.3}}
```

## VERIFY

1. Trigger an analysis from the iOS app (any stock)
2. Open `http://your-server:8000/dashboard` in browser
3. Active analyses section should show:
   - Ticker name (RELIANCE)
   - Scan type badge (STANDARD / DEEP / EXTREME) with color-coded left border
   - Elapsed time ("running 12s")
   - Progress bar (e.g., 35% filled)
   - Current stage ("Market Analyst running...")
4. After analysis completes, it moves to recent analyses table

## DO NOT
- Don't change `_dash_end_job` — it already stores the result correctly
- Don't change the dashboard authentication (already admin-only)
- Don't change the SSE endpoint or iOS progress view
- Don't add new files — all changes in `backend/main.py` and possibly `backend/database.py` if `_job_to_dict` is missing fields
