# Quant Lab Implementation Report

**Date:** 2026-06-24
**Branch:** feat/prediction-calibration-lightgbm
**Feature:** Quant Lab -- ML Signal Card + Full Research View

---

## Overview

The Quant Lab feature adds quantitative research and ML model transparency tooling to the Nivesh iOS app. It consists of two main UI components backed by new and existing backend endpoints.

## Components Delivered

### 1. StockMLSignalCard (Compact ML Signal)

A compact card embedded in the StockProfileView Overview tab that displays the current ML model prediction for a stock. Shows:

- Directional signal (Bullish / Bearish / Neutral) with color-coded indicator
- Confidence percentage with visual bar
- Model version identifier
- Top feature drivers influencing the prediction
- Tap target to open the full Quant Lab view

### 2. QuantLabView (Full-Screen Research View)

A dedicated full-screen view accessible from the ML Signal Card, organized into 9 research sections:

1. **ML Signal Summary** -- expanded signal with feature drivers
2. **Calibration Curve** -- prediction vs. actual outcome calibration
3. **Pillar Attribution** -- contribution breakdown by analysis pillar
4. **Model Versions** -- active model registry with metadata
5. **Alpha Validation** -- out-of-sample alpha metrics
6. **Strategy Sweep** -- parameter sweep results for trading strategies
7. **Regime Breakdown** -- performance segmented by market regime
8. **Cost Sensitivity** -- impact of transaction costs on strategy returns
9. **Raw JSON Inspector** -- developer tool for inspecting raw API responses

### 3. Backend: ML Signal Endpoint

New `GET /api/v1/stocks/{symbol}/ml-signal` endpoint that proxies to the ML engine, retrieves the current prediction, and returns a typed response with direction, confidence, model version, and feature drivers.

### 4. Backend: Cost Sensitivity Typed Response

The existing `GET /api/v1/backtests/cost-sensitivity` endpoint received a typed Pydantic response model for consistent serialization.

## Architecture

- **iOS Layer:** 5 new files + 2 modified files following MVVM with unidirectional data flow
- **Backend Layer:** 1 new endpoint + 1 endpoint response typing, Controller-Service-Repository pattern maintained
- **Data Flow:** StockProfileView -> StockMLSignalCard -> QuantLabView -> QuantLabViewModel -> QuantLabAPIClient -> Backend -> ML Engine

## Files Summary

| Layer | New Files | Modified Files |
|-------|-----------|----------------|
| iOS   | 5         | 2              |
| Backend | 1 endpoint | 1 response schema |
| Tests | 7 test cases | -- |
