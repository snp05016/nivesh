# Nivesh (निवेश) — Frontend Context

> Paste this into Claude to get frontend context before brainstorming next steps.
> Last updated: June 3, 2026. Reflects current implemented state.

---

## What Is This

**Nivesh Frontend** is a premium SwiftUI application styled like an Indian Rupee banknote. It provides high-end visual analysis of the Indian stock market, integrating a banknote-themed design system with advanced AI signals.

---

## Design System (Banknote Aesthetic)

- **Guilloché Patterns**: Animated dividers and background borders (`GuillocheDivider`).
- **Security Thread**: Gold vertical strip with micro-text (`SecurityThread`).
- **Ashoka Stamp**: Lion capital stamp integrated into Home.
- **RBI Seal**: Circular watermark on all cards.
- **Paper Texture**: 500-grain canvas noise overlay.
- **Verified Badge**: Blue checkmark for users/data.
- **Rupee Rustle**: Audio feedback for UI interactions (`AppSoundManager`).

---

## Key Features

### 1. 8-Tab Navigation
- **Home**: Morning Brief (Priority Items), Indices strip, Sector Pulse heatmap.
- **Directory**: Advanced search with screener presets (Hidden Gems, Momentum).
- **Assets**: Rupee-styled hero card, 10-segment risk meter, Red Flags system.
- **Alerts**: Manage price targets with foreground trigger checks.
- **Archives**: Locally cached analysis reports with Signal Change diffs.
- **Compare**: Side-by-side comparison of two stocks.
- **Registry**: App preferences, Dark mode, APNs registration.
- **Journal**: Log trade reasons, moods (FOMO/Contrarian), and outcomes.

### 2. Deep Analysis (5-Tab Deep Dive)
- **Overview**: Signal Change Flags, Confidence Rationale, and Worry Level.
- **Analysis**: Broker Ratings Strip, Macro strip, and Macro Impact Banner.
- **Fundaments**: Insider Trend Bars, Quarterly Financials, and Valuation Badge.
- **Charts**: 11 native **Swift Charts** (SMA, RSI, Volume, Stock vs Nifty).
- **News**: High-fidelity cards with images and summaries.

---

## Technical Architecture

- **State Management**: `@MainActor` ViewModels with `async/await`.
- **Haptics**: Centralized `HapticManager` with `EKPressStyle` spring animations.
- **Networking**: `NetworkManager.shared` with custom model decoding and server URL management.
- **Persistence**: `UserDefaults` for auth and `@AppStorage` for UI state.

---

## What Works

- **2FA Login**: Integrated authentication.
- **Portfolio Risk & Red Flags**: Comprehensive risk monitoring.
- **Trade Journaling**: Full lifecycle trade logging and stats.
- **Signal Flip Detection**: Visual indicators when outlook changes.
- **Advisor Matrix**: Integration of expert sentiment from YouTube harvest.
- **Hardened Market Data**: History fallbacks for indices/sectors.
- **Tutorial & Onboarding**: Animated overlays for new users.
