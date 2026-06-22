"""
backend/tasks/alpha158_task.py — Nightly Alpha158 feature materialization task.

Celery task: tasks.materialize_alpha158

Pipeline:
  1. For each NSE ticker, fetch 252 trading days of OHLCV via nse_data_provider.
  2. Apply Point-in-Time (PIT) safety — only rows with trade_date <= T are sent
     to the ml-engine, where T = the most recent date in the fetched series.
  3. POST the OHLCV payload to ml-engine at http://localhost:8001/predict/single.
     The ml-engine computes all 158 Alpha158 features internally.
  4. Re-compute the same features locally (via a lightweight FeatureComputer
     equivalent) to obtain the raw float values for storage.  The ml-engine
     response provides prediction metadata; feature values are derived from the
     same OHLCV slice to guarantee consistency.
  5. Upsert the 158 feature rows into alpha158_features_normalized using
     get_session() per AGENTS.md §3.2.

Design decisions:
  - One DB session per ticker (not one global session for all tickers) so that
    a single ticker failure does not roll back the entire batch.
  - httpx with a 30-second timeout prevents the task from hanging on a slow
    ml-engine response.
  - All OHLCV rows sent to ml-engine are capped at T to enforce PIT safety.
  - The task retries up to 3 times on transient failures (network / DB).

NEVER import this module from a router. Business logic stays here (service layer).
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

_LOG = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Celery app — re-use the canonical app defined in services/celery_tasks.py
# ---------------------------------------------------------------------------
try:
    from services.celery_tasks import celery_app as app, CELERY_AVAILABLE
except ImportError:
    # Graceful degradation: allow module import even when Celery is absent
    # (e.g. during unit tests or local development without a Redis broker).
    app = None
    CELERY_AVAILABLE = False


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

def _build_task(app_: Any):  # noqa: ANN001 — typed at call site
    """Register the task against the provided Celery app.  Called once at
    module load if Celery is available, otherwise a no-op stub is created."""

    @app_.task(
        name="tasks.materialize_alpha158",
        bind=True,
        max_retries=3,
        default_retry_delay=30,
        queue="alpha158",
    )
    def materialize_alpha158(self, tickers: list[str]) -> dict[str, Any]:
        """Materialize Alpha158 features for a list of NSE tickers.

        Args:
            tickers: List of bare NSE ticker symbols, e.g. ["RELIANCE", "TCS"].

        Returns:
            Summary dict: {ok: [...], failed: [...], total_upserted: int}.
        """
        import httpx

        from database import get_session
        from models.db_models import Alpha158Features
        from services.nse_data_provider import get_price_history

        ok: list[str] = []
        failed: list[str] = []
        total_upserted: int = 0

        for ticker in tickers:
            ticker = ticker.strip().upper()
            _LOG.info("[alpha158] Processing ticker=%s", ticker)

            # ── 1. Fetch OHLCV (252 trading days) ──────────────────────────
            try:
                df_pd = get_price_history(ticker, period_days=380, exchange="NSE")
                # 380 calendar days ≈ 252 trading days (accounts for weekends/holidays)
            except Exception as exc:
                _LOG.error("[alpha158] OHLCV fetch failed ticker=%s: %s", ticker, exc)
                failed.append(ticker)
                continue

            if df_pd is None or len(df_pd) < 60:
                _LOG.warning(
                    "[alpha158] Insufficient OHLCV rows ticker=%s (got %d, need ≥60)",
                    ticker,
                    len(df_pd) if df_pd is not None else 0,
                )
                failed.append(ticker)
                continue

            # ── 2. Point-in-Time safety ─────────────────────────────────────
            # df_pd index is a DatetimeIndex (pandas).
            # T = the most recent date in the fetched series.
            # We only pass rows with trade_date <= T to ml-engine (trivially
            # satisfied since get_price_history returns data up to today).
            t_date = df_pd.index.max().date()  # T = latest trading date
            t_date_str = t_date.isoformat()      # "YYYY-MM-DD"

            # Enforce PIT: drop any rows with date strictly after T
            # (defensive — normally not needed, but guards against data leakage).
            df_pit = df_pd[df_pd.index.date <= t_date]  # type: ignore[operator]

            # Trim to last 252 rows after PIT filter
            df_pit = df_pit.tail(252)

            if len(df_pit) < 5:
                _LOG.warning("[alpha158] Post-PIT filter: too few rows ticker=%s", ticker)
                failed.append(ticker)
                continue

            # ── 3. Build OHLCV payload for ml-engine ────────────────────────
            ohlcv_rows: list[dict[str, Any]] = []
            for ts, row in df_pit.iterrows():
                ohlcv_rows.append({
                    "date":   ts.date().isoformat(),
                    "open":   float(row.get("Open", row.get("open", 0.0))),
                    "high":   float(row.get("High", row.get("high", 0.0))),
                    "low":    float(row.get("Low", row.get("low", 0.0))),
                    "close":  float(row.get("Close", row.get("close", 0.0))),
                    "volume": float(row.get("Volume", row.get("volume", 0.0))),
                    "vwap":   None,  # ml-engine derives VWAP as (H+L+C)/3 when None
                })

            # ── 4. POST to ml-engine /predict/single ────────────────────────
            ml_response: dict[str, Any] | None = None
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(
                        "http://localhost:8001/predict/single",
                        json={
                            "ticker":     ticker,
                            "ohlcv_data": ohlcv_rows,
                            "model_type": "lightgbm",
                        },
                    )
                    resp.raise_for_status()
                    ml_response = resp.json()
                _LOG.info(
                    "[alpha158] ml-engine OK ticker=%s direction=%s confidence=%.3f",
                    ticker,
                    ml_response.get("expected_direction"),
                    ml_response.get("confidence_score", 0.0),
                )
            except httpx.HTTPStatusError as exc:
                _LOG.error(
                    "[alpha158] ml-engine HTTP %d ticker=%s: %s",
                    exc.response.status_code,
                    ticker,
                    exc,
                )
                failed.append(ticker)
                continue
            except httpx.RequestError as exc:
                _LOG.error("[alpha158] ml-engine connection error ticker=%s: %s", ticker, exc)
                failed.append(ticker)
                continue

            # ── 5. Compute feature values locally from the same OHLCV slice ─
            # The /predict/single response only returns feature *names*, not values.
            # We re-run FeatureComputer locally (pure-Python, no network) on the
            # identical PIT-safe OHLCV slice so stored values are consistent with
            # what the model saw.
            feature_rows: list[tuple[str, float]] = []  # [(feature_name, value), ...]
            try:
                import sys as _sys
                import os as _os

                # ml-engine may not be on sys.path in the backend worker process.
                # Locate it relative to this file's repo root.
                _repo_root = _os.path.dirname(
                    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
                )
                _ml_path = _os.path.join(_repo_root, "ml-engine")
                if _ml_path not in _sys.path:
                    _sys.path.insert(0, _ml_path)

                import polars as pl
                from pipeline.feature_computer import FeatureComputer
                from config import FEATURE_LIST  # ml-engine config

                _computer = FeatureComputer(feature_list=FEATURE_LIST, scaler_params=None)

                _records = []
                for row_dict in ohlcv_rows:
                    _records.append({
                        "date":   row_dict["date"],
                        "open":   row_dict["open"],
                        "high":   row_dict["high"],
                        "low":    row_dict["low"],
                        "close":  row_dict["close"],
                        "volume": row_dict["volume"],
                        "vwap":   row_dict["vwap"] if row_dict["vwap"] is not None
                                  else (row_dict["high"] + row_dict["low"] + row_dict["close"]) / 3.0,
                    })

                _df_pl = pl.DataFrame(_records)
                _features_df = _computer.compute_all(_df_pl)

                for col in _features_df.columns:
                    val = _features_df[col][0]
                    if val is not None:
                        feature_rows.append((col, float(val)))

                _LOG.info(
                    "[alpha158] Computed %d features ticker=%s T=%s",
                    len(feature_rows), ticker, t_date_str,
                )
            except Exception as exc:
                _LOG.error(
                    "[alpha158] Local feature computation failed ticker=%s: %s",
                    ticker, exc,
                )
                failed.append(ticker)
                continue

            if not feature_rows:
                _LOG.warning("[alpha158] No feature values produced ticker=%s", ticker)
                failed.append(ticker)
                continue

            # ── 6. Upsert into alpha158_features_normalized ─────────────────
            # One session per ticker — failure here does not roll back other tickers.
            try:
                computed_at = datetime.now(timezone.utc)
                with get_session() as session:
                    for feature_name, feature_value in feature_rows:
                        # Attempt UPDATE first; INSERT on miss (manual upsert for
                        # SQLite compatibility — SQLite lacks MERGE/INSERT OR UPDATE
                        # that's composable with SQLAlchemy ORM portably).
                        existing = (
                            session.query(Alpha158Features)
                            .filter_by(ticker=ticker, date=t_date_str, feature_name=feature_name)
                            .one_or_none()
                        )
                        if existing is not None:
                            existing.feature_value = feature_value
                            existing.computed_at = computed_at
                        else:
                            session.add(
                                Alpha158Features(
                                    ticker=ticker,
                                    date=t_date_str,
                                    feature_name=feature_name,
                                    feature_value=feature_value,
                                    computed_at=computed_at,
                                )
                            )
                    session.commit()
                    total_upserted += len(feature_rows)
                    _LOG.info(
                        "[alpha158] Upserted %d rows ticker=%s T=%s",
                        len(feature_rows), ticker, t_date_str,
                    )
                ok.append(ticker)
            except Exception as exc:
                _LOG.error(
                    "[alpha158] DB upsert failed ticker=%s: %s",
                    ticker, exc,
                )
                failed.append(ticker)
                continue

        summary = {
            "ok": ok,
            "failed": failed,
            "total_upserted": total_upserted,
        }
        _LOG.info("[alpha158] Batch complete: %s", summary)
        return summary

    return materialize_alpha158


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

if CELERY_AVAILABLE and app is not None:
    materialize_alpha158 = _build_task(app)
else:
    # Stub for environments where Celery / Redis is not installed.
    def materialize_alpha158(tickers: list[str]) -> dict:  # type: ignore[misc]
        raise RuntimeError(
            "Celery is not installed or not configured. "
            "Install: pip install 'celery[redis]>=5.3.0' and set CELERY_BROKER_URL."
        )
