// ─── Admin auth ──────────────────────────────────────────────
// Admin JWT kept for this tab only: prompted once, cleared on 401/403 so the next refresh re-prompts.
function authHeaders(){
  let t=sessionStorage.getItem('nivesh_admin_jwt');
  if(!t){t=(prompt('Admin JWT (Bearer token):')||'').trim();if(t)sessionStorage.setItem('nivesh_admin_jwt',t);}
  return {'Authorization':'Bearer '+t};
}
async function adminFetch(url,opts){
  const r=await fetch(url,{...(opts||{}),headers:{...((opts&&opts.headers)||{}),...authHeaders()}});
  if(r.status===401||r.status===403)sessionStorage.removeItem('nivesh_admin_jwt');
  return r;
}

// ─── Charts ─────────────────────────────────────────────────
let chartAlloc=null, chartSigs=null, chartVal=null, chartPnl=null, chartNw=null;

function destroyChart(c){if(c){c.destroy();return null;}return null;}

const expandedIds=new Set();
const activeTabs2={};
let currentUserData=null;
let currentUserTab='portfolio';

// ─── Formatting ──────────────────────────────────────────────
// Every server-supplied string (request paths, usernames, scraped titles, LLM text) goes through esc() before innerHTML.
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function fmt(n){if(n==null)return'-';if(n>=1e9)return(n/1e9).toFixed(2)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'K';return''+n}
function fmtINR(n){if(n==null||isNaN(n))return'-';const abs=Math.abs(n);let s;if(abs>=1e7)s=(n/1e7).toFixed(2)+' Cr';else if(abs>=1e5)s=(n/1e5).toFixed(2)+' L';else s=n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g,',');return(n<0?'-₹':'₹')+s.replace('-','')}
function fmtCost(c){if(c==null)return'$-.--';return'$'+c.toFixed(4)}
function ts(iso){if(!iso)return'-';return new Date(iso).toLocaleTimeString('en-IN',{hour12:false})}
function dts(iso){if(!iso)return'-';const d=new Date(iso);return d.toLocaleDateString('en-IN')+' '+d.toLocaleTimeString('en-IN',{hour12:false})}
function ela(iso){if(!iso)return'';const s=Math.floor((Date.now()-new Date(iso))/1000);if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m '+s%60+'s';return Math.floor(s/3600)+'h'}
function sig(s){if(!s)return'-';const u=s.toUpperCase();if(u.includes('BUY')||u==='STRONG_BUY'||u==='BULL')return`<span class="badge bull">${esc(s)}</span>`;if(u.includes('SELL')||u==='STRONG_SELL'||u==='BEAR')return`<span class="badge bear">${esc(s)}</span>`;return`<span class="badge hold">${esc(s)}</span>`}
function ctype(t){if(!t)return'-';const u=(t||'').toUpperCase();if(u==='CACHE HIT')return`<span class="badge cache">CACHE</span>`;if(u==='SMART CACHE')return`<span class="badge smart">SMART</span>`;if(u==='FULL AI')return`<span class="badge full">FULL AI</span>`;return`<span class="badge hold">${esc(t)}</span>`}
function stbadge(s){if(!s)return'-';const l=s.toLowerCase();if(l==='completed')return`<span class="badge ok">&#x2713; done</span>`;if(l==='error')return`<span class="badge err">&#x2717; error</span>`;return`<span class="badge hold">${esc(s)}</span>`}
function mbadge(m){return`<span class="badge m${esc(m||'GET')}">${esc(m)}</span>`}
function hbadge(c){if(!c)return'-';const cls=c<300?'ok':c<400?'cache':'err';return`<span class="badge ${cls}">${esc(c)}</span>`}
function fmtParams(p){if(!p||!Object.keys(p).length)return'';const s=JSON.stringify(p).replace(/[{}"]/g,'');return esc(s.length>40?s.slice(0,40)+'...':s)}
function pct(a,b){if(!b)return'0%';return Math.round(a/b*100)+'%'}
function pnlClass(v){return v>=0?'pnl-pos':'pnl-neg'}
function actionClass(a){const m={'BUY':'journal-action-buy','SELL':'journal-action-sell','HOLD':'journal-action-hold','WATCH':'journal-action-watch'};return m[a]||'';}

// ─── Navigation ──────────────────────────────────────────────
function showPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  document.querySelectorAll('.nav-tab').forEach(t=>{if(t.dataset.arg===name)t.classList.add('active');});
  const loaders={flags:loadFlags,jobs:loadJobs,audit:()=>loadAudit(false),usage:loadUsage};
  if(loaders[name])loaders[name]();
}
function showUserTab(name){
  currentUserTab=name;
  document.querySelectorAll('[id^="utab-content-"]').forEach(el=>el.style.display='none');
  document.querySelectorAll('[id^="utab-"]').forEach(btn=>{if(btn.tagName==='BUTTON')btn.classList.remove('active');});
  document.getElementById('utab-content-'+name).style.display='';
  document.getElementById('utab-'+name).classList.add('active');
  if(currentUserData) renderUserTab(currentUserData, name);
}

// ─── Feature errors ──────────────────────────────────────────
function renderFeatureErrors(featureErrors){
  const grid=document.getElementById('feature-error-grid');
  if(!featureErrors||!Object.keys(featureErrors).length){grid.innerHTML='<div class="empty" style="grid-column:1/-1">No data</div>';return;}
  const icons={'News Feed':'&#x1F4F0;','Tech Momentum':'&#x1F4C8;','Screener':'&#x1F50D;','Alerts':'&#x1F514;','Portfolio Calendar':'&#x1F4C5;','Earnings Dashboard':'&#x1F4B0;','Analysis Engine':'&#x1F9E0;','YouTube Harvester':'&#x1F3A5;','Advisor Harvester':'&#x1F4BC;','Macro Impact':'&#x1F30D;','Sector Performance':'&#x1F3D7;'};
  grid.innerHTML=Object.entries(featureErrors).map(([name,errs])=>{
    const hasErrs=errs&&errs.length>0;
    const icon=icons[name]||'&#x1F534;';
    const body=hasErrs?errs.map(e=>`<div class="feat-err-item"><div class="feat-err-path">${esc(e.path||'-')}</div><div class="feat-err-meta">${hbadge(e.status)} &bull; ${ts(e.ts)}</div></div>`).join(''):`<div class="feat-clean-msg">&#x2714; No errors</div>`;
    return`<div class="feature-card ${hasErrs?'has-errors':'clean'}"><div class="feature-header"><span class="feature-name">${icon} ${esc(name)}</span><div class="feat-status-dot"></div></div><div class="feature-body">${body}</div></div>`;
  }).join('');
}

// ─── Harvest ─────────────────────────────────────────────────
function renderHarvestStatus(harvests){
  const grid=document.getElementById('harvest-status-grid');
  if(!harvests){grid.innerHTML='<div class="empty">No data</div>';return;}
  grid.innerHTML=Object.entries(harvests).map(([name,h])=>{
    let color='val-dim',val=h.status||'idle';
    if(h.status==='running'){color='val-blue';val='RUNNING...';}
    else if(h.status==='error'){color='val-red';val='ERROR';}
    else if(h.status==='idle'&&h.last_run){color='val-green';val='IDLE';}
    return`<div class="stat-tile tile-dark"><div class="val ${color}">${esc(val)}</div><div class="lbl">${esc(name.toUpperCase())}</div><div class="ts" style="margin-top:4px">${h.last_run?ts(h.last_run):'Never'}</div></div>`;
  }).join('');
  const map={youtube:'btn-yt-harvest',advisor:'btn-adv-harvest',news:'btn-news-harvest'};
  Object.entries(map).forEach(([key,id])=>{
    const btn=document.getElementById(id);if(!btn)return;
    const h=harvests[key];
    if(h&&h.status==='running'){btn.textContent=key+' Running...';btn.disabled=true;btn.style.opacity='.5';}
    else{btn.textContent=['youtube','advisor','news'].includes(key)?{youtube:'&#x1F3A5; YouTube',advisor:'&#x1F4BC; Advisor',news:'&#x1F4F0; News'}[key]:key;btn.disabled=false;btn.style.opacity='1';}
  });
}

async function triggerHarvest(type){
  const ep={youtube:'harvest-youtube',advisor:'harvest-advisors',news:'harvest-news'};
  const r=await adminFetch('/api/v1/admin/'+ep[type],{method:'POST'});
  if(r.ok)refreshAll();else alert('Failed: '+r.status);
}

function toggleDetails(id){
  const el=document.getElementById('details-'+id);
  if(expandedIds.has(id)){expandedIds.delete(id);el.style.display='none';}
  else{expandedIds.add(id);el.style.display='table-row';loadAnalysisJson(id);}
}

// raw_output/full_json are not in /dashboard-data; fetch one row on expand.
async function loadAnalysisJson(id){
  const box=document.getElementById('json-'+id);
  if(!box||box.textContent)return;
  box.textContent='Loading...';
  try{
    const r=await adminFetch('/dashboard-data/analysis/'+id);
    if(!r.ok){box.textContent='Failed: '+r.status;return;}
    const d=await r.json();
    let fp='';try{fp=JSON.stringify(JSON.parse(d.full_json),null,2);}catch(e){fp=d.full_json||d.raw_output||'';}
    box.textContent=fp||'(empty)';
  }catch(e){box.textContent='Failed to load';}
}

// ─── User selector population ────────────────────────────────
function populateUserList(db_stats_users, analyses){
  // We'll populate from /users endpoint via dashboard-data users list
}

// ─── Load per-user data ──────────────────────────────────────
async function loadUser(userId){
  if(!userId){document.getElementById('user-stat-chips').innerHTML='';currentUserData=null;return;}
  document.getElementById('user-stat-chips').innerHTML='<span style="color:#484f58;font-size:11px">Loading...</span>';
  try{
    const r=await adminFetch('/dashboard-user-data?user_id='+userId);
    if(!r.ok){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">HTTP '+r.status+' '+esc(r.statusText)+'</span>';return;}
    const d=await r.json();
    currentUserData=d;
    // Stat chips
    const u=d.user||{};
    const ps=d.portfolio_summary||{};
    const acc=d.accuracy||{};
    document.getElementById('user-stat-chips').innerHTML=`
      <div class="user-stat-chip">&#x1F464; <span class="chip-val">${esc(u.display_name||u.username)}</span></div>
      <div class="user-stat-chip">Holdings: <span class="chip-val">${ps.holdings_count||0}</span></div>
      <div class="user-stat-chip">Invested: <span class="chip-val">${fmtINR(ps.total_invested||0)}</span></div>
      <div class="user-stat-chip">Analyses: <span class="chip-val">${(d.analyses||[]).length}</span></div>
      <div class="user-stat-chip">Accuracy: <span class="chip-val">${acc.accuracy_pct!=null?acc.accuracy_pct+'%':'N/A'}</span></div>
      <div class="user-stat-chip">Joined: <span class="chip-val">${esc(u.created_at?u.created_at.slice(0,10):'-')}</span></div>
    `;
    renderUserTab(d, currentUserTab);
  }catch(e){document.getElementById('user-stat-chips').innerHTML='<span class="badge err">Error: '+esc(e.message)+'</span>';}
}

function renderUserTab(d, tab){
  if(tab==='portfolio') renderPortfolio(d);
  else if(tab==='analyses') renderAnalyses(d);
  else if(tab==='valuation') renderValuation(d);
  else if(tab==='alerts') renderAlerts(d);
  else if(tab==='journal') renderJournal(d);
  else if(tab==='networth') renderNetWorth(d);
}

// ─── Portfolio ───────────────────────────────────────────────
function renderPortfolio(d){
  const rows=d.portfolio||[];
  const ps=d.portfolio_summary||{};
  document.getElementById('p-holdings').textContent=ps.holdings_count||0;
  document.getElementById('p-invested').textContent=fmtINR(ps.total_invested||0);
  const groups=[...new Set(rows.map(r=>r.group_name||'watchlist'))];
  document.getElementById('p-groups').textContent=groups.length;

  document.getElementById('portfolio-table').innerHTML=rows.length===0?'<tr><td colspan="9" class="empty">No holdings</td></tr>':rows.map((r,i)=>`<tr>
    <td class="ts">${i+1}</td>
    <td style="font-weight:700;color:#f0f6fc">${esc(r.ticker)}</td>
    <td style="color:#8b949e;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.company_name)}</td>
    <td>${esc(r.shares)}</td>
    <td>₹${r.buy_price.toLocaleString('en-IN',{minimumFractionDigits:2})}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(r.invested)}</td>
    <td><span class="badge hold">${esc(r.group_name)}</span></td>
    <td style="color:#6e7681;font-size:10px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.notes||'—')}</td>
    <td class="ts">${esc(r.created_at?r.created_at.slice(0,10):'-')}</td>
  </tr>`).join('');

  // Allocation donut
  chartAlloc=destroyChart(chartAlloc);
  if(rows.length>0){
    const groupMap={};
    rows.forEach(r=>{const g=r.group_name||'watchlist';groupMap[g]=(groupMap[g]||0)+r.invested;});
    const labels=Object.keys(groupMap),vals=Object.values(groupMap);
    const colors=['#c9a84c','#3fb950','#58a6ff','#bc8cff','#f85149','#d29922'];
    chartAlloc=new Chart(document.getElementById('chart-allocation'),{type:'doughnut',data:{labels,datasets:[{data:vals,backgroundColor:colors.slice(0,labels.length),borderColor:'#0a0a0a',borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:11}}}}}});
  }

  // Signal distribution pie
  chartSigs=destroyChart(chartSigs);
  const sd=d.signal_distribution||{};
  if(Object.keys(sd).length>0){
    const slabels=Object.keys(sd),svals=Object.values(sd);
    const scolors=slabels.map(l=>{const u=l.toUpperCase();if(u.includes('BUY')||u.includes('BULL'))return'#3fb950';if(u.includes('SELL')||u.includes('BEAR'))return'#f85149';return'#d29922';});
    chartSigs=new Chart(document.getElementById('chart-signals'),{type:'bar',data:{labels:slabels,datasets:[{data:svals,backgroundColor:scolors,borderColor:'#0a0a0a',borderWidth:1}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6e7681',font:{size:10}},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10}},grid:{color:'#161b22'}}}}});
  }
}

// ─── AI Analysis Reports ─────────────────────────────────────
function renderAnalyses(d){
  const analyses=d.analyses||[];
  const acc=d.accuracy||{};
  document.getElementById('a-total').textContent=analyses.length;
  document.getElementById('a-correct').textContent=acc.correct??'-';
  document.getElementById('a-incorrect').textContent=acc.incorrect??'-';
  document.getElementById('a-accuracy').textContent=acc.accuracy_pct!=null?acc.accuracy_pct+'%':'N/A';

  const container=document.getElementById('analyses-list');
  if(analyses.length===0){container.innerHTML='<div class="empty">No analyses for this user</div>';return;}

  container.innerHTML=analyses.map(a=>{
    const bull=(a.bull_case||[]).slice(0,3);
    const bear=(a.bear_case||[]).slice(0,3);
    const risks=(a.key_risks||[]).slice(0,3);
    const kf=a.key_factors||{};
    const up=a.upside_downside_pct||{};
    const correctBadge=a.was_correct===true?'<span class="badge ok">&#x2713; Correct</span>':a.was_correct===false?'<span class="badge err">&#x2717; Wrong</span>':'<span class="badge hold">Unverified</span>';
    return`<div class="analysis-report">
      <div class="report-header">
        <div>
          <div class="report-ticker">${esc(a.ticker)} ${sig(a.signal)}</div>
          <div class="report-company">${esc(a.company_name)}</div>
        </div>
        <div class="report-meta">
          ${correctBadge}<br>
          Conf: <span style="color:#c9a84c">${a.confidence_pct!=null?a.confidence_pct+'%':'-'}</span><br>
          Price: <span style="color:#f0f6fc">${a.current_price_inr!=null?fmtINR(a.current_price_inr):'-'}</span><br>
          <span class="ts">${esc(a.created_at?a.created_at.slice(0,10):'-')}</span>
        </div>
      </div>
      <div class="target-prices">
        <div class="target-chip"><div class="tv">${a.target_short!=null?fmtINR(a.target_short):'-'}</div><div class="tl">3M Target ${up.short_term!=null?'('+up.short_term.toFixed(1)+'%)':''}</div></div>
        <div class="target-chip"><div class="tv">${a.target_medium!=null?fmtINR(a.target_medium):'-'}</div><div class="tl">12M Target ${up.medium_term!=null?'('+up.medium_term.toFixed(1)+'%)':''}</div></div>
        <div class="target-chip"><div class="tv">${a.target_long!=null?fmtINR(a.target_long):'-'}</div><div class="tl">36M Target ${up.long_term!=null?'('+up.long_term.toFixed(1)+'%)':''}</div></div>
      </div>
      <div class="report-body">
        <div class="report-col">
          <h4>&#x1F7E2; Bull Case</h4>
          <ul class="report-list">${bull.length?bull.map(b=>`<li>${esc(b)}</li>`).join(''):'<li style="color:#484f58">No bull case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F514; Key Risks</h4>
          <ul class="report-list">${risks.length?risks.map(r=>`<li>${esc(r)}</li>`).join(''):'<li style="color:#484f58">No risks</li>'}</ul>
        </div>
        <div class="report-col">
          <h4>&#x1F534; Bear Case</h4>
          <ul class="report-list">${bear.length?bear.map(b=>`<li>${esc(b)}</li>`).join(''):'<li style="color:#484f58">No bear case</li>'}</ul>
          <h4 style="margin-top:10px">&#x1F4CA; Key Factors</h4>
          <div class="key-factors">
            ${Object.entries(kf).slice(0,6).map(([k,v])=>`<div class="kf-item"><div class="kf-label">${esc(k.replace(/_/g,' '))}</div><div class="kf-val">${esc(String(v||'').slice(0,60))}</div></div>`).join('')}
          </div>
        </div>
      </div>
      ${a.outcome_delta_pct!=null?`<div style="margin-top:8px;font-size:11px;color:#6e7681">Price moved <span class="${a.outcome_delta_pct>=0?'pnl-pos':'pnl-neg'}">${a.outcome_delta_pct>=0?'+':''}${a.outcome_delta_pct.toFixed(2)}%</span> since analysis</div>`:''}
    </div>`;
  }).join('');
}

// ─── Valuation Chart ─────────────────────────────────────────
function renderValuation(d){
  const hist=d.valuation_history||[];
  chartVal=destroyChart(chartVal);
  chartPnl=destroyChart(chartPnl);

  const table=document.getElementById('valuation-table');
  table.innerHTML=hist.length===0?'<tr><td colspan="6" class="empty">No valuation history</td></tr>':hist.map(v=>`<tr>
    <td class="ts">${esc(v.snapshot_date)}</td>
    <td style="color:#c9a84c">${fmtINR(v.total_value)}</td>
    <td>${fmtINR(v.total_invested)}</td>
    <td class="${pnlClass(v.total_pnl)}">${fmtINR(v.total_pnl)}</td>
    <td class="${pnlClass(v.pnl_percent)}">${v.pnl_percent!=null?v.pnl_percent.toFixed(2)+'%':'-'}</td>
    <td class="ts">${v.nifty_close!=null?v.nifty_close.toFixed(0):'-'}</td>
  </tr>`).join('');

  if(hist.length===0)return;
  const labels=hist.map(v=>v.snapshot_date);
  const vals=hist.map(v=>v.total_value);
  const invested=hist.map(v=>v.total_invested);
  const pnlPct=hist.map(v=>v.pnl_percent);

  // Normalised Nifty (to compare trend)
  const niftyRaw=hist.map(v=>v.nifty_close);
  const niftyBase=niftyRaw.find(x=>x!=null);
  const valBase=vals[0]||1;
  const niftyNorm=niftyRaw.map(x=>x!=null?(x/niftyBase)*valBase:null);

  chartVal=new Chart(document.getElementById('chart-valuation'),{type:'line',data:{labels,datasets:[
    {label:'Portfolio Value',data:vals,borderColor:'#c9a84c',backgroundColor:'rgba(201,168,76,.08)',tension:.3,pointRadius:2,fill:true},
    {label:'Cost Basis',data:invested,borderColor:'#58a6ff',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[4,4]},
    {label:'Nifty (norm)',data:niftyNorm,borderColor:'#6e7681',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[2,4]},
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:10}}}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>fmtINR(v)},grid:{color:'#161b22'}}}}});

  chartPnl=new Chart(document.getElementById('chart-pnl-pct'),{type:'bar',data:{labels,datasets:[{label:'P&L %',data:pnlPct,backgroundColor:pnlPct.map(v=>v>=0?'rgba(63,185,80,.6)':'rgba(248,81,73,.6)'),borderColor:pnlPct.map(v=>v>=0?'#3fb950':'#f85149'),borderWidth:1}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>v+'%'},grid:{color:'#161b22'}}}}});
}

// ─── Alerts ──────────────────────────────────────────────────
function renderAlerts(d){
  const alerts=d.alerts||[];
  const container=document.getElementById('alerts-list');
  if(alerts.length===0){container.innerHTML='<div class="empty">No price alerts</div>';return;}
  container.innerHTML=alerts.map(a=>`<div class="alert-item ${a.triggered?'alert-triggered':''}">
    <div>
      <span style="font-weight:700;color:#f0f6fc">${esc(a.ticker)}</span>
      <span class="ts" style="margin-left:8px">${esc(a.created_at?a.created_at.slice(0,10):'-')}</span>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <span style="color:#c9a84c">₹${a.target_price.toLocaleString('en-IN')}</span>
      <span class="badge ${a.direction==='above'?'bull':'bear'}">${esc(a.direction?.toUpperCase())}</span>
      ${a.triggered?'<span class="badge ok">TRIGGERED</span>':'<span class="badge hold">ACTIVE</span>'}
    </div>
  </div>`).join('');
}

// ─── Trade Journal ───────────────────────────────────────────
function renderJournal(d){
  const journal=d.trade_journal||[];
  const container=document.getElementById('journal-list');
  if(journal.length===0){container.innerHTML='<div class="empty">No journal entries</div>';return;}
  container.innerHTML=journal.map(j=>`<div class="journal-entry ${actionClass(j.action)}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
      <div>
        <span style="font-weight:700;color:#f0f6fc">${esc(j.ticker)}</span>
        ${j.company_name?`<span class="ts" style="margin-left:6px">${esc(j.company_name)}</span>`:''}
        <span class="badge ${j.action==='BUY'?'bull':j.action==='SELL'?'bear':'hold'}" style="margin-left:8px">${esc(j.action)}</span>
        ${j.mood?`<span class="badge hold" style="margin-left:4px">${esc(j.mood)}</span>`:''}
      </div>
      <div class="ts">${esc(j.created_at?j.created_at.slice(0,10):'-')}</div>
    </div>
    <div style="font-size:11px;color:#8b949e;margin-bottom:4px">&#x1F4B0; Price at time: <span style="color:#c9a84c">₹${j.price_at_time.toLocaleString('en-IN')}</span></div>
    <div style="font-size:11px;color:#8b949e"><strong style="color:#6e7681">Reason:</strong> ${esc(j.reason_text||'—')}</div>
    ${j.outcome_text?`<div style="font-size:11px;color:#6e7681;margin-top:4px;padding-top:4px;border-top:1px solid #21262d"><strong>Outcome:</strong> ${esc(j.outcome_text)}</div>`:''}
  </div>`).join('');
}

// ─── Net Worth ───────────────────────────────────────────────
function renderNetWorth(d){
  const ledger=d.net_worth_ledger||[];
  chartNw=destroyChart(chartNw);
  const table=document.getElementById('networth-table');
  table.innerHTML=ledger.length===0?'<tr><td colspan="7" class="empty">No net worth data</td></tr>':ledger.map(n=>`<tr>
    <td class="ts">${esc(n.snapshot_date)}</td>
    <td style="color:#c9a84c;font-weight:700">${fmtINR(n.total_value_inr)}</td>
    <td class="${pnlClass(n.daily_delta_inr||0)}">${n.daily_delta_inr!=null?fmtINR(n.daily_delta_inr):'-'}</td>
    <td class="${pnlClass(n.daily_delta_pct||0)}">${n.daily_delta_pct!=null?n.daily_delta_pct.toFixed(2)+'%':'-'}</td>
    <td style="color:#6e7681">${n.peak_value_inr!=null?fmtINR(n.peak_value_inr):'-'}</td>
    <td>${n.top_gainer_ticker?`<span class="pnl-pos">${esc(n.top_gainer_ticker)} +${n.top_gainer_pct?.toFixed(1)}%</span>`:'-'}</td>
    <td>${n.top_loser_ticker?`<span class="pnl-neg">${esc(n.top_loser_ticker)} ${n.top_loser_pct?.toFixed(1)}%</span>`:'-'}</td>
  </tr>`).join('');

  if(ledger.length===0)return;
  const labels=ledger.map(n=>n.snapshot_date);
  const vals=ledger.map(n=>n.total_value_inr);
  const peaks=ledger.map(n=>n.peak_value_inr);
  chartNw=new Chart(document.getElementById('chart-networth'),{type:'line',data:{labels,datasets:[
    {label:'Net Worth',data:vals,borderColor:'#c9a84c',backgroundColor:'rgba(201,168,76,.08)',tension:.3,pointRadius:2,fill:true},
    {label:'Peak',data:peaks,borderColor:'#3fb950',backgroundColor:'transparent',tension:.3,pointRadius:1,borderDash:[3,3]},
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b949e',font:{size:10}}}},scales:{x:{ticks:{color:'#6e7681',font:{size:9},maxRotation:45},grid:{color:'#161b22'}},y:{ticks:{color:'#6e7681',font:{size:10},callback:v=>fmtINR(v)},grid:{color:'#161b22'}}}}});
}

// ─── Main refresh ────────────────────────────────────────────
async function refreshAll(){
  try{
    const r=await adminFetch('/dashboard-data');
    if(!r.ok){document.getElementById('lu').textContent='Auth error '+r.status;return;}
    const d=await r.json();

    document.getElementById('lu').textContent='Updated '+new Date().toLocaleTimeString('en-IN',{hour12:false});
    if(d.uptime_s!=null){
      const h=Math.floor(d.uptime_s/3600),m=Math.floor((d.uptime_s%3600)/60),s=Math.floor(d.uptime_s%60);
      document.getElementById('uptime').textContent=`Up ${h}h ${m}m ${s}s`;
    }

    // Overview stats
    if(d.db_stats){
      document.getElementById('db_u').textContent=d.db_stats.users??0;
      document.getElementById('db_h').textContent=d.db_stats.holdings??0;
      document.getElementById('db_a').textContent=d.db_stats.analyses??0;
      document.getElementById('db_s').textContent=d.db_stats.signal_events??0;
      document.getElementById('db_tj').textContent=d.db_stats.trade_journals??0;
      document.getElementById('db_news').textContent=d.db_stats.news_articles??0;
      document.getElementById('db_yt').textContent=d.db_stats.youtube_videos??0;
    }
    if(d.cache_stats){document.getElementById('c_q').textContent=d.cache_stats.quick_info??0;}

    if(d.ai_health){
      const ok='<span class="val-green">READY</span>',no='<span class="val-red">MISSING</span>';
      document.getElementById('h_ant').innerHTML=d.ai_health.anthropic?ok:no;
      document.getElementById('h_ds').innerHTML=d.ai_health.deepseek?ok:no;
      document.getElementById('h_goog').innerHTML=d.ai_health.google?ok:no;
    }

    renderFeatureErrors(d.feature_errors||{});

    // Active analyses
    const active=d.active_analyses||[];
    document.getElementById('ac').textContent=active.length+' running';
    document.getElementById('ab').innerHTML=active.length===0?'<div class="empty">No active analyses</div>':active.map(a=>`<div class="analysis-item active"><div style="display:flex;justify-content:space-between;align-items:center"><span class="a-ticker">${esc(a.ticker)}</span><span class="ts">${ts(a.start_ts)}</span></div><div class="a-meta">${esc(a.exchange||'NSE')} &bull; User ${esc(a.user_id||'N/A')} &bull; running ${ela(a.start_ts)}</div><div class="a-stage"><span class="s-dot"></span>${esc(a.stage||'Processing...')}</div></div>`).join('');

    // Recent analyses
    const an=d.recent_analyses||[];
    document.getElementById('anc').textContent=an.length+' shown';
    document.getElementById('at').innerHTML=an.length===0?'<tr><td colspan="6" class="empty">No activity</td></tr>':an.slice(0,15).map(a=>`<tr><td class="ts">${ts(a.start_ts||a.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(a.ticker)}</td><td>${ctype(a.cache_type)}</td><td>${sig(a.signal)}</td><td class="ts">${a.duration_s!=null?a.duration_s+'s':'-'}</td><td>${stbadge(a.status)}</td></tr>`).join('');

    // News / videos (overview & harvesters tabs)
    const lnews=d.latest_news||[];
    document.getElementById('lnc').textContent=lnews.length+' recent';
    const newsHtml=lnews.length===0?'<tr><td colspan="4" class="empty">No news</td></tr>':lnews.map(n=>`<tr><td class="ts">${ts(n.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(n.ticker||'—')}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${n.red_flag?'<span class="badge err">&#x1F6A9;</span> ':''}${esc(n.headline)}</td><td>${n.sentiment?`<span class="badge ${esc(n.sentiment.toLowerCase())}">${esc(n.sentiment)}</span>`:'—'}</td></tr>`).join('');
    document.getElementById('lnt').innerHTML=newsHtml;
    document.getElementById('lnt2').innerHTML=newsHtml;

    const lvideos=d.latest_videos||[];
    document.getElementById('lvc').textContent=lvideos.length+' recent';
    const vidHtml=lvideos.length===0?'<tr><td colspan="4" class="empty">No videos</td></tr>':lvideos.map(v=>`<tr><td class="ts">${ts(v.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(v.ticker||'—')}</td><td style="color:#bc8cff">${esc(v.channel)}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(v.title)}</td></tr>`).join('');
    document.getElementById('lvt').innerHTML=vidHtml;
    document.getElementById('lvt2').innerHTML=vidHtml;

    // Harvesters
    renderHarvestStatus(d.harvest_status);
    const hlogs=d.harvest_logs||[];
    document.getElementById('hrc').textContent=hlogs.length+' logged';
    document.getElementById('hrt').innerHTML=hlogs.length===0?'<tr><td colspan="3" class="empty">No logs</td></tr>':hlogs.map(l=>`<tr><td class="ts">${ts(l.ts)}</td><td style="font-weight:700;color:#c9a84c">${esc(l.key.toUpperCase())}</td><td style="font-size:10px;color:#8b949e;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(JSON.stringify(l.result))}</td></tr>`).join('');

    // AI stats
    const cl=d.claude_stats||{},ds=d.deepseek_stats||{},tok=d.token_stats||{};
    document.getElementById('cl_calls').textContent=fmt(cl.calls||0);
    document.getElementById('cl_in').textContent=fmt(cl.input_tokens||0);
    document.getElementById('cl_out').textContent=fmt(cl.output_tokens||0);
    document.getElementById('cl_cost').textContent=fmtCost(cl.cost_usd||0);
    const totalIn=tok.total_input||0,cacheRead=tok.total_cache_read||0;
    document.getElementById('cl_cache_hit').textContent=totalIn>0?pct(cacheRead,totalIn+cacheRead):'0%';
    document.getElementById('ds_calls').textContent=fmt(ds.calls||0);
    document.getElementById('ds_in').textContent=fmt(ds.input_tokens||0);
    document.getElementById('ds_out').textContent=fmt(ds.output_tokens||0);
    document.getElementById('ds_cost').textContent=fmtCost(ds.cost_usd||0);
    const totalCalls=(cl.calls||0)+(ds.calls||0);
    document.getElementById('ds_ratio').textContent=totalCalls>0?pct(ds.calls||0,totalCalls)+' of calls':'0%';
    document.getElementById('ti').textContent=fmt(tok.total_input||0);
    document.getElementById('to').textContent=fmt(tok.total_output||0);
    document.getElementById('tr').textContent=fmt(tok.total_cache_read||0);
    document.getElementById('tw').textContent=fmt(tok.total_cache_write||0);
    const un=d.unknown_stats||{};
    document.getElementById('tc').textContent=(tok.total_calls||0)+' calls this session'+(un.calls?' | '+fmt(un.calls)+' logged calls unpriced (no model)':'');
    const cl2=tok.recent||[];
    document.getElementById('clc').textContent=cl2.length+' recent';
    document.getElementById('ct').innerHTML=cl2.length===0?'<tr><td colspan="6" class="empty">No AI calls</td></tr>':cl2.map(c=>`<tr><td class="ts">${ts(c.ts)}</td><td style="color:#bc8cff;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.endpoint||'-')}</td><td style="color:#f85149">${fmt(c.input)}</td><td style="color:#3fb950">${fmt(c.output)}</td><td style="color:#58a6ff">${fmt(c.cache_read)}</td><td style="color:#d29922">${fmt(c.cache_write)}</td></tr>`).join('');
    if(d.cache_stats){
      const sg=document.getElementById('scraper_status_grid');
      const sdata=d.cache_stats.scraper||{};
      const skeys=Object.keys(sdata);
      sg.innerHTML=skeys.length===0?'<div class="empty" style="grid-column:1/-1">No scraper cache</div>':skeys.map((k,i)=>{const colors=['val-red','val-green','val-blue','val-gold'];return`<div class="stat-tile tile-dark"><div class="val ${colors[i%4]}">${esc(sdata[k].age_s)}s</div><div class="lbl">${esc(k)}</div></div>`;}).join('');
    }

    // Requests
    const reqs=(d.request_log||[]).slice(0,50);
    document.getElementById('rc').textContent=reqs.length+' shown';
    document.getElementById('rt').innerHTML=reqs.length===0?'<tr><td colspan="6" class="empty">No requests</td></tr>':reqs.map(r=>`<tr><td class="ts">${ts(r.ts)}</td><td>${mbadge(r.method)}</td><td class="path" title="${esc(r.path)}">${esc(r.path)}</td><td class="ts">${fmtParams(r.params)}</td><td>${hbadge(r.status)}</td><td class="ts">${r.duration_ms!=null?esc(r.duration_ms)+'ms':'-'}</td></tr>`).join('');

    // Archive
    const hist=d.historical_analyses||[];
    document.getElementById('hnc').textContent=hist.length+' records';
    document.getElementById('ht').innerHTML=hist.length===0?'<tr><td colspan="8" class="empty">No data</td></tr>':hist.map(h=>{
      const isExp=expandedIds.has(h.id);
      return`<tr><td class="ts">${dts(h.ts)}</td><td style="font-weight:700;color:#f0f6fc">${esc(h.ticker)}</td><td class="ts">${esc(h.analysis_date||'-')}</td><td>${sig(h.signal)}</td><td style="color:#d29922">${h.confidence!=null?h.confidence+'%':'-'}</td><td class="ts">${esc(h.user_id||'-')}</td><td>${h.was_correct===true?'<span class="badge ok">&#x2713;</span>':h.was_correct===false?'<span class="badge err">&#x2717;</span>':'-'}</td><td><button class="btn-view" data-action="toggleDetails" data-arg="${Number(h.id)}">View</button></td></tr>
      <tr id="details-${Number(h.id)}" style="display:${isExp?'table-row':'none'}"><td colspan="8"><div class="archive-details" style="display:block"><div class="json-box" id="json-${Number(h.id)}"></div></div></td></tr>`;
    }).join('');
    expandedIds.forEach(id=>loadAnalysisJson(id));

    // Populate user select on first load
    populateUserDropdown();

  }catch(e){
    console.error('Dashboard error:',e);
    document.getElementById('lu').textContent='Error: '+e.message;
  }
}

// ─── User dropdown ──────────────────────────────────────────
let _usersPopulated=false;
async function populateUserDropdown(){
  if(_usersPopulated)return;
  try{
    const r=await adminFetch('/users');
    if(!r.ok){console.warn('Could not load user list: HTTP '+r.status);return;}
    const users=await r.json();
    if(!Array.isArray(users)||users.length===0){
      console.warn('No users returned from /users');return;
    }
    const sel=document.getElementById('user-select');
    sel.innerHTML='<option value="">-- select user --</option>'+users.map(u=>`<option value="${esc(u.id)}">#${esc(u.id)} ${esc(u.display_name||u.username)} (${esc(u.username)})</option>`).join('');
    _usersPopulated=true;
  }catch(e){console.warn('Could not populate user list:',e);}
}

// ─── AI Engine Monitor ────────────────────────────────────────
let _aiMode='running';

function setAIMode(mode,btn){
  _aiMode=mode;
  document.querySelectorAll('.btn-mode').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  document.getElementById('ai-ticker-filter').value='';
  loadAIEngine();
}

async function loadAIEngine(){
  const ticker=document.getElementById('ai-ticker-filter')?.value?.trim()||'';
  const params=new URLSearchParams({mode:_aiMode,limit:'30'});
  if(ticker)params.set('ticker',ticker);
  try{
    const r=await adminFetch('/api/v1/dashboard/ai-engine?'+params);
    if(!r.ok){console.warn('AI engine fetch failed:',r.status);return;}
    const d=await r.json();
    renderAIEngine(d);
  }catch(e){console.warn('AI engine error:',e);}
}

function renderAIEngine(d){
  if(!d)return;
  const s=d.summary||{};
  document.getElementById('ai_running').textContent=s.running??0;
  document.getElementById('ai_queued').textContent=s.queued??0;
  document.getElementById('ai_stuck').textContent=s.stuck??0;
  const jobs=d.jobs||[];
  document.getElementById('ai_total').textContent=jobs.length;
  document.getElementById('ai_updated').textContent=ts(d.generated_at);

  const tbody=document.getElementById('ai-jobs-tbody');
  if(jobs.length===0){
    tbody.innerHTML='<tr><td colspan="9" class="empty">No jobs found</td></tr>';
  }else{
    tbody.innerHTML=jobs.map(j=>{
      const status=j.status||'?';
      const scl=status==='RUNNING'?'active':status==='SUCCEEDED'?'ok':'err';
      const pct=j.progress_pct||0;
      const barCls=status==='SUCCEEDED'?'done':status==='FAILED'?'failed':'running';
      const tl=j.phase_timeline||[];
      const hasTimeline=tl.length>0;
      return `<tr>
        <td style="font-weight:700;color:#f0f6fc">${esc(j.ticker||'-')}${j.is_stuck?' <span class="badge err">STUCK</span>':''}</td>
        <td><span class="badge ${scl}">${esc(status)}</span></td>
        <td style="max-width:180px"><div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(j.current_phase||j.stage||'-')}</div><div class="phase-bar"><div class="phase-bar-fill ${barCls}" style="width:${Number(pct)||0}%"></div></div></td>
        <td class="ts">${esc(pct)}%</td>
        <td class="ts">${esc(j.age_label||'-')}</td>
        <td class="ts">${esc(j.elapsed_label||'-')}</td>
        <td><span class="badge hold">${esc(j.scan_type||'standard')}</span></td>
        <td class="ts" style="color:#bc8cff">${fmt(j.tokens_used||0)}</td>
        <td style="max-width:110px"><span class="ts" style="font-size:9px">${esc(j.job_id)}</span>${j.is_stuck?` <button class="btn-view err" style="font-size:9px;padding:2px 6px" data-action="cancelAIMonitorJob" data-arg="${esc(j.job_id)}">X</button>`:''}</td>
      </tr>
      ${hasTimeline?`<tr><td colspan="9" style="padding:4px 12px 8px">
        <div style="display:flex;gap:4px;flex-wrap:wrap;font-size:10px;color:#6e7681">
          ${tl.map((p,i,a)=>{
            const dc=p.state==='active'?'active':p.state==='done'?'done':p.state==='failed'?'failed':'';
            return `<div style="display:flex;align-items:center;gap:6px;padding:2px 6px;background:#0d1117;border-radius:4px;border:1px solid #21262d;flex:0 0 auto;min-width:100px">
              <div class="timeline-dot ${dc}"></div>
              <div><div style="color:#8b949e;font-weight:600">${esc(p.stage||'-')}</div><div style="font-size:9px;color:#484f58;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(String(p.message||'').slice(0,50))}</div></div>
            </div>`;
          }).join('')}
        </div>
      </td></tr>`:''}`;
    }).join('');
  }

  // Latest by ticker
  const latest=d.latest_success||[];
  const ltbody=document.getElementById('ai-latest-tbody');
  if(latest.length===0){
    ltbody.innerHTML='<tr><td colspan="9" class="empty">No completed analyses</td></tr>';
  }else{
    ltbody.innerHTML=latest.map(l=>`<tr>
      <td style="font-weight:700;color:#f0f6fc">${esc(l.ticker||'-')}</td>
      <td>${sig(l.signal)}</td>
      <td style="color:#d29922">${l.confidence_pct!=null?l.confidence_pct+'%':'-'}</td>
      <td class="ts">${esc(l.analysis_tier||l.scan_type||'-')}</td>
      <td style="color:#c9a84c">${l.current_price_inr!=null?'₹'+l.current_price_inr.toLocaleString('en-IN'):'-'}</td>
      <td style="color:#c9a84c">${l.target_12m!=null?'₹'+l.target_12m.toLocaleString('en-IN'):'-'}</td>
      <td class="${l.upside_12m_pct!=null&&l.upside_12m_pct>0?'pnl-pos':'pnl-neg'}">${l.upside_12m_pct!=null?l.upside_12m_pct.toFixed(1)+'%':'-'}</td>
      <td class="ts">${fmt(l.tokens_used||0)}</td>
      <td class="ts">${esc(l.analysis_date||'-')}</td>
    </tr>`).join('');
  }
}

async function cancelAIMonitorJob(jobId){
  if(!confirm('Cancel job '+jobId+'?'))return;
  try{
    const r=await adminFetch('/analyze/'+jobId+'/cancel',{method:'POST'});
    if(r.ok)loadAIEngine();
    else console.warn('Cancel failed:',r.status);
  }catch(e){console.warn('Cancel error:',e);}
}

// ─── Ops pages: flags, jobs, audit, usage ─────────────────────
const OPS_ERR=(what,status)=>`<tr><td colspan="8" class="empty">Could not load ${esc(what)} (${esc(status)})</td></tr>`;
function opsRows(tableId,html){document.querySelector('#'+tableId+' tbody').innerHTML=html;}

function flagToggle(f){
  if(f.description==='unregistered')return '';
  return `<button class="btn-view" data-action="toggleFlag" data-arg="${esc(f.key)}" data-enabled="${f.enabled?'1':'0'}">Turn ${f.enabled?'OFF':'ON'}</button>`;
}
async function loadFlags(){
  try{
    const r=await adminFetch('/api/v1/admin/flags');
    if(!r.ok){opsRows('flags-table',OPS_ERR('flags',r.status));return;}
    const d=await r.json();
    opsRows('flags-table',d.flags.map(f=>`<tr>
      <td style="font-weight:700">${esc(f.key)}</td>
      <td>${esc(f.description)}</td>
      <td><span class="badge ${f.enabled?'ok':'hold'}">${f.enabled?'ON':'OFF'}</span></td>
      <td class="ts">${esc(f.source)}</td>
      <td class="ts">${esc(f.updated_at?dts(f.updated_at):'-')}</td>
      <td>${flagToggle(f)}</td>
    </tr>`).join('')||'<tr><td colspan="6" class="empty">No flags</td></tr>');
  }catch(e){opsRows('flags-table',OPS_ERR('flags','network'));}
}
async function toggleFlag(key,el){
  const turnOn=el.dataset.enabled!=='1';
  if(!confirm('Turn '+(turnOn?'ON':'OFF')+' '+key+' for all users?'))return;
  const msg=document.getElementById('flags-msg');
  try{
    const r=await adminFetch('/api/v1/admin/flags/'+encodeURIComponent(key),{
      method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:turnOn})});
    msg.textContent=r.ok?'':'Update failed ('+r.status+')';
  }catch(e){msg.textContent='Update failed (network)';}
  loadFlags();
}

async function loadJobs(){
  try{
    const [s,f]=await Promise.all([
      adminFetch('/api/v1/admin/job-runs/summary?days=7'),
      adminFetch('/api/v1/admin/job-runs?status=failed&limit=20')]);
    if(!s.ok)opsRows('jobs-summary',OPS_ERR('jobs',s.status));
    else{
      const d=await s.json();
      document.getElementById('jobs-overall').textContent=d.overall_success_pct==null?'no runs yet':d.overall_success_pct+'% success overall';
      opsRows('jobs-summary',d.jobs.map(j=>`<tr><td style="font-weight:700">${esc(j.job_name)}</td><td>${fmt(j.runs)}</td><td>${fmt(j.failures)}</td><td>${esc(j.success_pct)}%</td><td>${stbadge(j.last_status==='ok'?'completed':j.last_status==='failed'?'error':j.last_status)}</td><td class="ts">${esc(dts(j.last_started_at))}</td><td class="ts">${esc((j.last_error||'').slice(0,120))}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">No finished runs</td></tr>');
    }
    if(!f.ok)opsRows('jobs-failures',OPS_ERR('failures',f.status));
    else{
      const d=await f.json();
      opsRows('jobs-failures',d.runs.map(r=>`<tr><td class="ts">${esc(dts(r.started_at))}</td><td style="font-weight:700">${esc(r.job_name)}</td><td class="ts">${r.duration_ms==null?'-':fmt(r.duration_ms)+' ms'}</td><td class="ts">${esc((r.error||'').slice(0,200))}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">No failed runs</td></tr>');
    }
  }catch(e){opsRows('jobs-summary',OPS_ERR('jobs','network'));}
}

let auditNext=null;
async function loadAudit(older){
  const url='/api/v1/admin/audit?action_prefix=admin_&limit=50'+(older&&auditNext?'&before_id='+auditNext:'');
  try{
    const r=await adminFetch(url);
    if(!r.ok){opsRows('audit-table',OPS_ERR('audit log',r.status));return;}
    const d=await r.json();
    auditNext=d.next_before_id;
    const rows=d.entries.map(e=>`<tr><td class="ts">${esc(dts(e.created_at))}</td><td class="ts">${esc(e.actor_user_id)}</td><td style="font-weight:700">${esc(e.action)}</td><td class="ts">${esc(JSON.stringify(Object.fromEntries(Object.entries(e.details||{}).filter(([k])=>k!=='_ctx'))))}</td><td class="ts">${esc(e.ip_address||'-')}</td></tr>`).join('');
    const body=document.querySelector('#audit-table tbody');
    if(older)body.insertAdjacentHTML('beforeend',rows);
    else body.innerHTML=rows||'<tr><td colspan="5" class="empty">No entries</td></tr>';
  }catch(e){opsRows('audit-table',OPS_ERR('audit log','network'));}
}
function loadAuditOlder(){loadAudit(true);}

async function loadUsage(){
  try{
    const r=await adminFetch('/api/v1/admin/analytics/daily?days=14');
    if(!r.ok){opsRows('usage-table',OPS_ERR('usage',r.status));return;}
    const d=await r.json();
    document.getElementById('usage-active-users').textContent=fmt(d.active_users);
    opsRows('usage-table',d.rows.map(x=>`<tr><td class="ts">${esc(x.date)}</td><td style="font-weight:700">${esc(x.event_name)}</td><td>${fmt(x.events)}</td><td>${fmt(x.users)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">No events yet</td></tr>');
  }catch(e){opsRows('usage-table',OPS_ERR('usage','network'));}
}

// ─── Event wiring (no inline handlers: the page CSP forbids inline script) ───
const actions={refreshAll,showPage,showUserTab,triggerHarvest,setAIMode,cancelAIMonitorJob,toggleDetails:id=>toggleDetails(Number(id)),
  toggleFlag,loadAuditOlder};
document.addEventListener('click',e=>{
  const el=e.target.closest('[data-action]');
  const fn=el&&actions[el.dataset.action];
  if(fn)fn(el.dataset.arg,el);
});
document.getElementById('user-select').addEventListener('change',e=>loadUser(e.target.value));
document.getElementById('ai-ticker-filter').addEventListener('input',()=>loadAIEngine());

// Init
refreshAll();
loadAIEngine();
setInterval(refreshAll, 30000);
setInterval(loadAIEngine, 10000);
