# SECTOR ROTATION DASHBOARD — Autonomous Build for Antigravity CLI

Paste into Antigravity CLI. Do not ask. Build end-to-end.

## GOAL
Which sectors are gaining/losing momentum? Where is institutional money flowing? Sector performance over 1M/3M/6M/1Y with FII/DII overlay. Visual dashboard showing sector rotation in real time.

## BACKEND: backend/services/sector_rotation.py

Endpoint: GET /api/v1/market/sector-rotation?period=3m

Logic (zero LLM):
1. Fetch sector performance from existing /sector-performance endpoint
2. For each sector, compute: return over period, momentum (rate of change), FII/DII net flow
3. Build momentum matrix: x-axis = return, y-axis = momentum. Quadrants: Leaders (top right), Laggards (bottom left), Improving (top left), Fading (bottom right)
4. Track sector rotation: which sectors moved quadrants this week vs last week
5. Compute FII/DII flow per sector (from existing FIIDIIFlow table + sector mapping)
6. Institutional conviction score: FII buying + DII buying in sector / total sector volume

Response: {period, sectors: [{name, return_pct, momentum_score, quadrant, fii_flow_cr, dii_flow_cr, institutional_conviction, holdings_in_sector: [{ticker, weight}]}]}

## iOS: ios/StockApp/stockme/stockme/Views/SectorRotationScreen.swift

1. Period selector: 1M | 3M | 6M | 1Y chips
2. Quadrant scatter chart: each sector as a bubble. x=return, y=momentum, size=mcap. Colored by quadrant.
3. Sector cards below chart: sorted by momentum score
4. Each card: sector name, return %, momentum bar, FII/DII flow arrows, "You have X holdings here" badge
5. Institutional flow section: "FIIs buying IT (+Rs 2,500 Cr), selling Banks (-Rs 1,800 Cr)"
6. Tap sector -> filtered stock list of that sector from user portfolio + watchlist

## RULES
Zero LLM. Pure data viz. Reuse /sector-performance and FIIDIIFlow table. New files only.
