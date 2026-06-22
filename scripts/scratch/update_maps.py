import re

def update_architecture_md():
    with open('/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE.md', 'r') as f:
        content = f.read()
    
    # 1. Tech Stack
    content = content.replace('iOS | SwiftUI, AVFoundation, Charts', 'iOS | SwiftUI, AVFoundation, Charts, WidgetKit')
    content = content.replace('Infra | DigitalOcean, multiprocessing, SSE streaming', 'Infra | DigitalOcean, multiprocessing, SSE streaming, Redis, APNs')
    
    # 2. Functional Areas
    content = content.replace('main.py — App entry, middleware, lifecycle', 'main.py — App entry, CorrelationIDMiddleware, APScheduler cron jobs')
    
    # 3. Controller-Service-Repository
    content = content.replace('• HTTP validation, rate limiting, auth', '• HTTP validation, sliding window rate limiting (helpers.py deque), auth')
    content = content.replace('20 services: orchestrator, sentiment_engine', '21 services: orchestrator, cache_service (Redis + in-memory), sentiment_engine')
    content = content.replace('SignalEvent, PriceTarget, TradeJournal, etc.', 'SignalEvent, PriceTarget, TradeJournal, BlockDeal, FIIDIIFlow, etc.')
    
    # 4. iOS Architecture
    ios_addition = """
### New Components & Extensions
```
• NiveshWidgetExtension (WidgetKit)
• AnalysisHistoryScreen, InteractiveTutorialScreen
• HomeLayoutEditorSheet, WatchlistTagsManager
• SpeechRecognizerManager, iPad NavigationSplitView adaptation
```
"""
    content = content.replace('### Design System (Theme.swift)', ios_addition + '\n### Design System (Theme.swift)')
    
    # 5. Key Design Decisions
    new_decisions = """
6. **Background Tasks over Polling**: Client-side polling for price alerts replaced with an APNs Webhook background task to conserve battery and reduce server load.

7. **Resilient Caching**: `_dcache` replaced with `services/cache_service.py` featuring `redis.asyncio` with an automatic in-memory fallback.

8. **Telemetry & Limits**: `CorrelationIDMiddleware` threads `X-Request-ID` through logs, and rate limiting upgraded to a sliding window deque per endpoint in `helpers.py`.
"""
    content = content.replace('serve instantly.\n\n---', f'serve instantly.\n{new_decisions}\n---')
    
    with open('/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE.md', 'w') as f:
        f.write(content)


def update_architecture_map_md():
    with open('/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE_MAP.md', 'r') as f:
        content = f.read()

    # Append a new section summarizing the architecture changes right after the first heading
    new_section = """
## 1.5. Recent Architectural Evolution (June 2026)

### Backend Updates
- **Caching**: Replaced `_dcache` with `services/cache_service.py` (using `redis.asyncio` with in-memory fallback).
- **Scheduling**: Added `APScheduler` in `main.py` for automated cron jobs (harvesting news, youtube, block deals, portfolio snapshot).
- **Alerts**: Replaced client-side polling for price alerts with a background APNs Webhook task.
- **Models**: Added new SQLAlchemy models: `BlockDeal` and `FIIDIIFlow`.
- **Telemetry**: Added `CorrelationIDMiddleware` to thread `X-Request-ID` across logs.
- **Rate Limiting**: Upgraded rate limiter to use a sliding window deque per endpoint in `helpers.py`.

### iOS & Frontend Updates
- **WidgetKit**: Added `NiveshWidgetExtension` for home screen widgets.
- **New Screens**: Added `AnalysisHistoryScreen`, `InteractiveTutorialScreen`, `HomeLayoutEditorSheet`.
- **Managers**: Added `WatchlistTagsManager` and `SpeechRecognizerManager`.
- **Adaptation**: Enhanced iPad experience with `NavigationSplitView`.

"""
    # Insert new section before "## 2. Complete Directory Structure"
    content = content.replace('## 2. Complete Directory Structure', new_section + '## 2. Complete Directory Structure')
    
    # Make some targeted str.replace for specific components
    content = content.replace('main.py                      # FastAPI app entrypoint (3042 lines) -- GOD NODE', 'main.py                      # FastAPI app entrypoint, APScheduler, CorrelationIDMiddleware -- GOD NODE')
    content = content.replace('helpers.py                   # Shared helpers, ticker constants, auth deps', 'helpers.py                   # Shared helpers, sliding window deque rate limiting, auth deps')
    
    # Update the cache mention if we can find it
    content = content.replace('_dcache', 'services/cache_service.py')
    
    with open('/Users/saumya/Desktop/nivesh/CodebaseInformation/ARCHITECTURE_MAP.md', 'w') as f:
        f.write(content)

update_architecture_md()
update_architecture_map_md()
print("Success")
