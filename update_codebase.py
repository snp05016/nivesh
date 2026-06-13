import os

def update_api_contract():
    path = '/Users/saumya/Desktop/nivesh/CodebaseInformation/API_CONTRACT_MAP.md'
    with open(path, 'r') as f:
        content = f.read()
    
    if '## Domain: Copilot' not in content:
        new_domains = """
## Domain: Copilot

### Chat
- **Swift Caller:** `NetworkManager.chatCopilot(...)`
- **Backend Receiver:** `routers/copilot.py → copilot_chat()`
- **HTTP Method & Route:** `POST /api/v1/copilot/chat`
- **Bridge Status:** ✅ Match

## Domain: Quantitative Tools

### NL Screener
- **Swift Caller:** `NetworkManager.queryNLScreener(...)`
- **Backend Receiver:** `routers/nl_screener.py → query_screener()`
- **HTTP Method & Route:** `POST /api/v1/nl-screener/query`
- **Bridge Status:** ✅ Match

### Correlation Matrix
- **Swift Caller:** `NetworkManager.getCorrelationMatrix(...)`
- **Backend Receiver:** `routers/correlation.py → get_correlation()`
- **HTTP Method & Route:** `GET /portfolio/correlation`
- **Bridge Status:** ✅ Match

### Market Anomalies
- **Swift Caller:** `NetworkManager.getAnomalies(...)`
- **Backend Receiver:** `routers/anomalies.py → get_anomalies()`
- **HTTP Method & Route:** `GET /anomalies`
- **Bridge Status:** ✅ Match

### Sector Rotation
- **Swift Caller:** `NetworkManager.getSectorRotation(...)`
- **Backend Receiver:** `routers/sector_rotation.py → get_sector_rotation()`
- **HTTP Method & Route:** `GET /api/v1/sector-rotation`
- **Bridge Status:** ✅ Match

### Stress Test
- **Swift Caller:** `NetworkManager.runStressTest(...)`
- **Backend Receiver:** `routers/stress_test.py → run_stress_test()`
- **HTTP Method & Route:** `POST /portfolio/stress-test`
- **Bridge Status:** ✅ Match

### Earnings Surprise
- **Swift Caller:** `NetworkManager.getEarningsSurprise(...)`
- **Backend Receiver:** `routers/earnings_surprise.py → get_surprises()`
- **HTTP Method & Route:** `GET /api/v1/earnings/surprises`
- **Bridge Status:** ✅ Match

"""
        content += new_domains
        with open(path, 'w') as f:
            f.write(content)


def update_arch_map():
    path = '/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE_MAP.md'
    with open(path, 'r') as f:
        content = f.read()
        
    if '## 1.6. Advanced Quantitative Features' not in content:
        new_section = """
## 1.6. Advanced Quantitative Features (June 2026)

### Backend Updates
- **Copilot**: Global AI assistant `routers/copilot.py` and `services/copilot_service.py`.
- **Stress Test**: Portfolio shock analysis `routers/stress_test.py`.
- **NL Screener**: Natural language stock discovery `routers/nl_screener.py`.
- **Correlation Matrix**: Cross-asset trailing matrix `routers/correlation.py`.
- **Anomaly Scanner**: APScheduler integrated scanner `routers/anomalies.py`.
- **Sector Rotation**: Sector flow analysis `routers/sector_rotation.py`.
- **Earnings Surprise**: Tracks beats/misses `routers/earnings_surprise.py`.

### iOS & Frontend Updates
- **Global Views**: Added `.withCopilot()` to `ContentView`.
- **New Screens**: Added `StressTestScreen`, `NLScreenerScreen`, `CorrelationMatrixScreen`, `MarketAnomalyScreen`, `SectorRotationScreen`, `EarningsSurpriseScreen`.
- **Integration**: Mapped new tools natively into `MarketSection` in `ContentView.swift`.

"""
        content = content.replace('## 2. Complete Directory Structure', new_section + '## 2. Complete Directory Structure')
        with open(path, 'w') as f:
            f.write(content)


def update_arch():
    path = '/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE.md'
    with open(path, 'r') as f:
        content = f.read()
        
    if '7 Advanced Agentic Features' not in content:
        new_decisions = """
9. **7 Advanced Agentic Features**: Seamless integration of 7 major LLM-driven components (Copilot, NL Screener, Stress Test, Correlation, Anomalies, Sector Rotation, Earnings). Deeply integrated across FastAPI and SwiftUI matching the Banknote Aesthetic token system.
"""
        if 'serve instantly.\n\n---' in content:
            content = content.replace('serve instantly.\n\n---', f'serve instantly.\n{new_decisions}\n---')
        else:
            content += new_decisions
        with open(path, 'w') as f:
            f.write(content)

update_api_contract()
update_arch_map()
update_arch()
print('Successfully updated CodebaseInformation files.')
