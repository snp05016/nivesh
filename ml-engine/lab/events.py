"""Market Event Reconstruction: what happened to a stock, and what was observable when.

Joins three kinds of item on one timeline, each tagged with its evidence type:
* `price_anomaly` / `volume_anomaly` — detected from prices only, using volatility and volume
  known BEFORE that day. No cause is inferred.
* `corporate_action` — from the exchange-derived event panel.
* `sourced_event` — dated events from curated scenarios, with their source URL.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

from .data import MarketData

SCENARIOS = Path(__file__).with_name("scenarios.json")


def anomalies(md: MarketData, symbol: str, start: date, end: date, z_thresh: float = 3.0, vol_mult: float = 3.0, lookback: int = 60) -> list[dict]:
    bars = md.history(symbol, end)
    out = []
    for i, b in enumerate(bars):
        if b.d < start or i < lookback + 1:
            continue
        prior = bars[i - lookback - 1: i]
        rets = [math.log(y.close / x.close) for x, y in zip(prior, prior[1:]) if x.close > 0 and y.close > 0]
        if len(rets) < lookback // 2:
            continue
        mu = sum(rets) / len(rets)
        sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / (len(rets) - 1))
        r = math.log(b.close / bars[i - 1].close) if bars[i - 1].close > 0 else 0.0
        z = (r - mu) / sd if sd > 0 else 0.0
        avg_v = sum(x.volume for x in prior[1:]) / lookback
        if abs(z) >= z_thresh:
            out.append({"date": b.d.isoformat(), "kind": "price_anomaly", "evidence": "prices", "return": round(math.exp(r) - 1, 4),
                        "z": round(z, 2), "text": f"Close-to-close move of {math.exp(r) - 1:+.1%}, {abs(z):.1f} standard deviations of the prior {lookback} sessions."})
        if avg_v > 0 and b.volume >= vol_mult * avg_v:
            out.append({"date": b.d.isoformat(), "kind": "volume_anomaly", "evidence": "prices", "volume_multiple": round(b.volume / avg_v, 1),
                        "text": f"Volume {b.volume / avg_v:.1f}x the prior {lookback}-session average."})
    return out


def timeline(md: MarketData, symbol: str, start: date, end: date) -> dict:
    items = anomalies(md, symbol, start, end)
    for a in md.actions.get(symbol, []):
        if start <= a.ex_date <= end:
            items.append({"date": a.ex_date.isoformat(), "kind": "corporate_action", "evidence": "exchange", "action": a.kind,
                          "factor": a.factor, "cash_per_share": a.cash_per_share, "source": a.source,
                          "text": f"{a.kind.title()} (ex-date)." if a.kind != "dividend" else f"Dividend of {a.cash_per_share:.2f} per share (ex-date)."})
    if SCENARIOS.exists():
        for sc in json.loads(SCENARIOS.read_text()).get("scenarios", []):
            relevant = symbol in sc.get("universe_hint", [])
            for ev in sc.get("timeline", []):
                d = ev.get("date", "")
                if start.isoformat() <= d <= end.isoformat():
                    items.append({"date": d, "kind": "sourced_event", "evidence": "source", "scenario": sc["id"], "market_wide": not relevant,
                                  "text": ev.get("event", ""), "source_url": ev.get("source_url", "")})
    items.sort(key=lambda x: (x["date"], x["kind"]))
    bars = [b for b in md.history(symbol, end) if b.d >= start]
    return {
        "symbol": symbol, "start": start.isoformat(), "end": end.isoformat(),
        "bars": [{"d": b.d.isoformat(), "c": b.close, "v": b.volume} for b in bars], "items": items,
        "note": "Anomalies are detected from prices using only earlier data; their causes are not inferred. A sourced event on the same day is a candidate explanation, not proof.",
    }
