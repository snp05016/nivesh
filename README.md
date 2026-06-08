# Nivesh

Nivesh is an iOS application and backend analytical engine designed for comprehensive stock portfolio management and automated financial analysis. The platform combines a premium, highly tactile user interface with an advanced server-side architecture capable of ingesting market data and producing synthesized investment insights.

## Architecture Overview

The system is built on a decoupled architecture comprising a SwiftUI iOS frontend and a FastAPI Python backend. 

### Frontend (iOS / SwiftUI)
The iOS application adheres to a strict design system. The user interface avoids raw hex colors and default system typography, relying instead on heavily curated semantic tokens (engraved serifs, monospaced serial number fonts, and strict color palettes). This ensures the app feels secure and legible, optimized for rapid financial decision-making. 

The frontend employs a unidirectional data flow and MVVM architecture. Key features include:
- Interactive portfolio dashboards with sector allocation charting.
- Custom iOS Home Screen widgets (WidgetKit) for live profit and loss tracking.
- Extensive native integrations including Face ID/Touch ID biometric locking, EventKit for earnings calendar reminders, and SFSpeechRecognizer for voice search.
- Interactive historical signal timelines and analysis difference tracking.

### Backend (FastAPI / Python)
The backend operates as the central data ingestion and analysis hub. It relies on a structured Controller-Service-Repository pattern to ensure business logic is isolated from routing and database operations.

Data structures and pipelines include:
- Market Data Harvesting: Scheduled asynchronous workers utilize APScheduler to scrape and ingest data from sources like Yahoo Finance (equities, corporate actions, splits/bonuses), AMFI (mutual fund NAVs), NSE (bulk/block deals, institutional net flows), and RSS feeds (financial news).
- Caching Layer: Real-time price and sector lookups are backed by a Redis caching layer with an in-memory dictionary fallback to minimize external API rate limits.
- Portfolio Engine: Handles complex calculations such as portfolio versus Nifty 50 benchmark compound annual growth rate, sliding window rate limiting, and macroeconomic stress testing against various risk scenarios.
- Database Models: Built on SQLAlchemy, managing core models like User, PortfolioHolding, AnalysisHistory, PriceTarget, BlockDeal, and NewsArticle. 

## Artificial Intelligence Pipeline

The core analytical strength of Nivesh relies on a multi-agent AI pipeline. When a stock analysis is requested, the backend orchestrates a dialectic framework where a bull agent and a bear agent debate the fundamentals, technicals, and recent news sentiment of a given equity. 

This pipeline heavily leverages large language models to synthesize raw data into actionable signals. Development and runtime generation within this repository utilize models including Anthropic's Claude, Google's Gemini, and DeepSeek. These models are responsible for scoring sentiment, predicting target prices, extracting metadata, and generating the final analytical briefs presented to the user.

## Setup and Deployment

### Backend
1. Install Python 3.10 or higher and the required dependencies from the backend directory.
2. Ensure Redis is running locally or provide a connection string.
3. Set up the required environment variables for the LLM providers (Claude, Gemini, DeepSeek) and database connections.
4. Run the FastAPI application using uvicorn.

### iOS
1. Open the Xcode workspace located in the iOS directory.
2. Ensure you have an active Apple Developer account for capabilities like Push Notifications and Siri speech recognition.
3. Configure the backend API URL in the app's environment configuration.
4. Build and run on an iOS 17 compatible device or simulator.

## License

MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
