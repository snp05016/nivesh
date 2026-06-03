# Spec: Market Data Hardening & High-Fidelity News Reader

**Date:** 2026-06-02
**Status:** Approved (Brainstorming Complete)
**Topic:** Fixing missing sector/index data and implementing a premium news experience.

---

## 1. Problem Statement
1.  **Missing Market Data**: The "Market Indices" and "Sector Pulse" sections are frequently missing or failing on the Home Screen. This is due to `yfinance`'s `info` and `fast_info` properties returning `None` for Indian index symbols (e.g., `^NSEI`, `^BSESN`).
2.  **Limited News**: The current news display is text-only, lacks summaries, and doesn't provide an immersive reading experience.

## 2. Proposed Solution

### A. Backend Hardening (main.py)
- **Indices & Sectors**: Implement a "Double-Check" pattern in `_get_indices_data()` and `sector_performance_endpoint()`.
    - Primary: Try `fast_info` / `info`.
    - Fallback: If primary returns `None`, fetch `t.history(period="5d")`. 
    - Use the last two closing prices to calculate `change_abs` and `change_pct`.
- **News Data**: Update `quick_info_endpoint()` to extract additional fields from the `yfinance` news object:
    - `summary`: The descriptive snippet of the article.
    - `image_url`: Extracted from `content -> thumbnail -> originalUrl` or the largest resolution.

### B. iOS High-Fidelity News Experience
- **Models**: Add `summary: String?` and `imageUrl: String?` to `NewsItem` struct in `Models.swift`.
- **UI Components**:
    - `NewsItemCard`: Update to display the `imageUrl` as a hero background or side thumbnail.
    - `NewsReaderView`: A new SwiftUI view presented as a `.fullScreenCover` or `.sheet`. 
        - Large hero image.
        - Publisher and Date header.
        - Scrollable body text using the `summary` and additional context.
        - "Read Full Story" button linking to the original URL.
- **Home Screen**: Ensure `Market Indices` and `Sector Pulse` sections handle loading states gracefully and don't collapse if the primary fetch fails but the fallback is in progress.

---

## 3. Architecture & Data Flow
1.  **Backend Fetch**: `main.py` -> `yfinance` (Retry + Fallback) -> JSON Response.
2.  **App Fetch**: `NetworkManager` -> `QuickInfo` / `SectorPerformance` models.
3.  **Display**: `HomeScreen` / `AnalysisScreen` -> `NewsItemCard` -> `NewsReaderView` (on tap).

## 4. Testing Criteria
- **Indices**: Verify Nifty 50 and Sensex show prices even when `info` is empty.
- **Sectors**: Verify the Sector Heatmap is populated with live data.
- **News**: 
    - Verify images render correctly in news cards.
    - Verify tapping a card opens the Reader View with the correct summary.
    - Verify the "Read Full Story" link opens in Safari.

---

## 5. Self-Review
- **Placeholders**: None.
- **Consistency**: Backend fields (`summary`, `image_url`) match iOS `CodingKeys`.
- **Scope**: Focused strictly on the reported bugs and the news feature.
