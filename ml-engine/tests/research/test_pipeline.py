"""Nightly pipeline, report assembly and on-demand compute (spec 2.2, 6, 11.1; package ml-assembly-pipeline).

Dev end to end runs on ``RESEARCH_LOCAL_CSV`` (skipped when absent). Store-mode
runs use a curated store built from the last 400 CSV sessions with synthetic
ISINs; the bhavcopy downloader and yfinance are fakes, so nothing touches the
network.
"""

from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from research import config, pipeline, registry, train
from research.contract import RunItem, RunStatus
from research.marketdata import bhavcopy, store
from research.report import assemble_report, predictions_for

needs_csv = pytest.mark.skipif(not config.LOCAL_CSV.exists(), reason="RESEARCH_LOCAL_CSV not available")
D = date(2026, 6, 23)  # last session of the local CSV (a Tuesday)
N_SYMBOLS = 49


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_a: Any, **_k: Any) -> None:
        raise AssertionError("network access in a unit test")

    monkeypatch.setattr(bhavcopy.urllib.request, "urlopen", refuse)
    monkeypatch.setattr(store.YFinance, "__init__", refuse)


class FakeYF:
    """yfinance stand-in: raw bars from a frame, no actions."""

    def __init__(self, bars: pd.DataFrame | None = None) -> None:
        self._bars = bars if bars is not None else pd.DataFrame(columns=["symbol", "date"])

    def bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        b = self._bars.loc[self._bars["symbol"] == symbol]
        b = b.loc[(b["date"] >= pd.Timestamp(start)) & (b["date"] <= pd.Timestamp(end))]
        return b.loc[:, ["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)

    def actions(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(columns=["date", "dividend", "split"])


def _no_bhavcopy(_d: date) -> bytes | None:
    return None


def _items(data_dir: Path, status: RunStatus) -> list[RunItem]:
    path = data_dir / "runs" / status.run_id / "items.jsonl"
    assert path.exists()
    return [RunItem.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def fast_models(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """``train --fast --train-production`` for 21 and 63, promoted with --allow-fast; returns models/."""
    if not config.LOCAL_CSV.exists():
        pytest.skip("RESEARCH_LOCAL_CSV not available")
    data_dir = tmp_path_factory.mktemp("models")
    for h in config.HORIZONS:
        assert train.main(["--horizon", str(h), "--source", "local_csv", "--data-dir", str(data_dir),
                           "--fast", "--train-production"]) == 0
    for mdir in (data_dir / "models").iterdir():
        if (mdir / registry.MANIFEST).exists():
            registry.promote(mdir.name, data_dir=data_dir, allow_fast=True)
    assert set(registry.read_registry(data_dir)["active"]) == {"21", "63"}
    return data_dir / "models"


def _with_models(models: Path, data_dir: Path) -> Path:
    shutil.copytree(models, data_dir / "models")
    return data_dir


@pytest.fixture(scope="module")
def csv_rows() -> pd.DataFrame:
    if not config.LOCAL_CSV.exists():
        pytest.skip("RESEARCH_LOCAL_CSV not available")
    raw = pd.read_csv(config.LOCAL_CSV)
    raw["date"] = pd.to_datetime(raw["date"]).astype("datetime64[ns]")
    days = pd.DatetimeIndex(raw["date"]).unique().sort_values()[-400:]
    raw = raw.loc[raw["date"].isin(list(days))].sort_values(["symbol", "date"]).reset_index(drop=True)
    isin = {s: f"INE{i:05d}A010" for i, s in enumerate(sorted(raw["symbol"].unique()))}
    raw["isin"] = raw["symbol"].map(isin)
    raw["prev_close"] = raw.groupby("symbol")["close"].shift()
    raw["volume"] = raw["volume"].astype(float)
    raw["turnover_inr"] = raw["close"] * raw["volume"]
    raw["trades"] = np.nan
    raw["source"] = "nse_bhavcopy"
    assert pd.Timestamp(D) == raw["date"].max()
    return raw


@pytest.fixture(scope="module")
def store_dir(tmp_path_factory: pytest.TempPathFactory, csv_rows: pd.DataFrame) -> Path:
    """A curated store holding every CSV session before D (D itself has no bhavcopy)."""
    root = tmp_path_factory.mktemp("store")
    store._curate(root, csv_rows.loc[csv_rows["date"] < pd.Timestamp(D), store._RAW_COLUMNS])
    return root


def _store_copy(store_dir: Path, tmp_path: Path, models: Path | None = None) -> Path:
    root = tmp_path / "data"
    shutil.copytree(store_dir, root)
    if models is not None:
        _with_models(models, root)
    return root


def _evening(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 20, 0, tzinfo=pipeline.IST)


# ── dev end to end (local CSV) ──────────────────────────────────────────────


@needs_csv
def test_cli_dev_run_without_artefact(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = pipeline.main(["--as-of", D.isoformat(), "--source", "local_csv", "--data-dir", str(tmp_path),
                          "--fundamentals", "skip"])
    assert code == 0
    status = RunStatus.model_validate(json.loads(capsys.readouterr().out.strip().splitlines()[-1]))
    assert status.status == "degraded" and status.counts.reports == N_SYMBOLS and status.counts.predictions == 0
    items = _items(tmp_path, status)
    assert len(items) == N_SYMBOLS
    for item in items:
        assert item.predictions == []
        assert [o.evidence_tier for o in item.report.outlooks] == ["unavailable", "unavailable"]
        assert all(o.reason_codes == ["manifest_invalid"] for o in item.report.outlooks)
        assert item.report.coverage.universe_quality == "survivorship_biased"
        assert item.report.fundamentals.status == "unavailable"
        assert {s.stage: s.status for s in item.report.pipeline}["fundamentals"] == "skipped"
        assert all(o.tier_text is None and o.prediction_id is None for o in item.report.outlooks)
        assert item.report.staleness is None and item.report.narrative is None
    assert (tmp_path / "snapshots" / D.isoformat() / "features.parquet").exists()
    run = json.loads((tmp_path / "runs" / status.run_id / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "degraded" and run["finished_at"]


@needs_csv
def test_dev_run_with_fast_artefact(tmp_path: Path, fast_models: Path) -> None:
    data_dir = _with_models(fast_models, tmp_path)
    status = pipeline.run_nightly(D, [], "local_csv", data_dir, "skip")
    assert status.status in ("ok", "degraded"), status.error
    items = _items(data_dir, status)
    assert len(items) == N_SYMBOLS
    csv = pd.read_csv(config.LOCAL_CSV)
    closes = csv.loc[csv["date"] == D.isoformat()].set_index("symbol")["close"]
    for item in items:
        r = item.report
        assert r.coverage.in_universe
        for o in r.outlooks:
            assert o.evidence_tier == "no_reliable_edge"
            assert o.reason_codes[0] == "survivorship_biased_universe"
            assert o.cohort is None and o.model_id and o.procedure_id == config.PROCEDURE_ID
        assert len(item.predictions) == 2
        for p in item.predictions:
            assert p.evidence_tier == "no_reliable_edge" and p.reason_codes[0] == "survivorship_biased_universe"
            assert p.entry_close == pytest.approx(float(closes[r.symbol]), rel=1e-12)
            assert p.expected_maturity_date.weekday() < 5 and p.expected_maturity_date > D
            assert p.bucket in (1, 2, 3, 4, 5) and 0.0 < p.rank_pct < 1.0
            assert p.feature_hash and len(p.feature_hash) == 64
        assert r.model_card.manifest_sha256 and r.model_card.data_period
        assert r.snapshot.last_close.value == pytest.approx(float(closes[r.symbol]))
    assert [p.expected_maturity_date for p in items[0].predictions] == [date(2026, 7, 22), date(2026, 9, 18)]
    assert status.counts.predictions == 2 * N_SYMBOLS


@needs_csv
def test_suspect_close_blanks_outlooks_and_risk(tmp_path: Path, fast_models: Path) -> None:
    data_dir = _with_models(fast_models, tmp_path)
    panel = store.load_panel(source="local_csv")
    hit = (panel["entity_id"] == "TCS") & (panel["date"] == pd.Timestamp(D))
    panel.loc[hit, "quality_flags"] = "suspect"
    panel.loc[hit, "px_idx"] = np.nan
    ctx = pipeline.build_context(panel, D, data_dir=data_dir, index=None)
    report = assemble_report(ctx, "TCS", fundamentals_mode="skip")
    assert all(o.evidence_tier == "unavailable" and o.reason_codes == ["data_quality_flag"] for o in report.outlooks)
    assert report.risk.var_status == "unavailable" and report.risk.var_1d == []
    assert report.risk.vol_ewma_ann_pct.reason == "data_quality_flag"
    assert report.snapshot.last_close.status == "unavailable"
    assert "data_quality_flag" in report.degraded_reasons and report.coverage.outlook_eligible is False
    assert predictions_for(ctx, "TCS", report) == []
    other = assemble_report(ctx, "INFY", fundamentals_mode="skip")
    assert len(predictions_for(ctx, "INFY", other)) == 2


@needs_csv
def test_compute_symbol(tmp_path: Path) -> None:
    with pytest.raises(pipeline.UnknownSymbol):
        pipeline.compute_symbol("NOSUCH", source="local_csv", data_dir=tmp_path, fundamentals_mode="skip")
    report = pipeline.compute_symbol("tcs.ns", as_of=D, source="local_csv", data_dir=tmp_path,
                                     fundamentals_mode="skip")
    assert report.origin == "on_demand" and report.symbol == "TCS" and report.as_of.market_date == D
    assert not (tmp_path / "runs").exists()


# ── store mode: fallback, failure, holiday ──────────────────────────────────


@needs_csv
def test_fallback_night_marks_predictions(tmp_path: Path, store_dir: Path, fast_models: Path,
                                          csv_rows: pd.DataFrame) -> None:
    root = _store_copy(store_dir, tmp_path, fast_models)
    yf = FakeYF(csv_rows.loc[csv_rows["date"] == pd.Timestamp(D)])
    status = pipeline.run_nightly(D, ["TCS"], "store", root, "skip", fetch=_no_bhavcopy, yf=yf, now=_evening(D))
    assert status.status == "degraded", status.error
    assert "prices_fallback_yfinance" in (status.error or "")
    items = _items(root, status)
    assert len(items) == N_SYMBOLS
    preds = [p for item in items for p in item.predictions]
    assert len(preds) == 2 * N_SYMBOLS
    assert all("prices_fallback_yfinance" in p.reason_codes for p in preds)
    r = items[0].report
    assert r.coverage.universe_quality == "pit" and r.isin and r.isin.startswith("INE")
    assert {s.stage: s.status for s in r.pipeline}["prices"] == "degraded"
    assert {s.id: s.status for s in r.provenance.sources}["nse_bhavcopy"] == "fallback"
    assert all("prices_fallback_yfinance" in o.reason_codes for o in r.outlooks)
    panel = store.load_panel(start=D, end=D, source="store", data_dir=root)
    assert set(panel["source"]) == {"yfinance"}
    assert bool(panel["prev_close"].isna().all())


@needs_csv
def test_prices_failure_writes_no_items(tmp_path: Path, store_dir: Path) -> None:
    root = _store_copy(store_dir, tmp_path)
    status = pipeline.run_nightly(D, [], "store", root, "skip", fetch=_no_bhavcopy, yf=FakeYF(), now=_evening(D))
    assert status.status == "failed" and status.stage == "prices"
    assert status.error and "PricesUnavailable" in status.error
    assert not (root / "runs" / status.run_id / "items.jsonl").exists()
    on_disk = RunStatus.model_validate_json((root / "runs" / status.run_id / "run.json").read_text(encoding="utf-8"))
    assert on_disk.status == "failed" and on_disk.finished_at is not None


@needs_csv
def test_next_morning_without_data_is_a_holiday(tmp_path: Path, store_dir: Path) -> None:
    root = _store_copy(store_dir, tmp_path)
    morning = _evening(D) + timedelta(hours=12)
    status = pipeline.run_nightly(D, [], "store", root, "skip", fetch=_no_bhavcopy, yf=FakeYF(), now=morning)
    assert status.status == "skipped_holiday"
    assert not (root / "runs" / status.run_id / "items.jsonl").exists()


def test_symbol_normalisation_and_maturity() -> None:
    assert pipeline.normalise_symbol(" reliance.ns ") == "RELIANCE"
    assert pipeline.normalise_symbol("TCS.BO") == "TCS"
    from research.report import expected_maturity

    assert expected_maturity(date(2026, 10, 9), 1) == date(2026, 10, 12)  # Friday -> Monday
    assert expected_maturity(date(2026, 10, 9), 21) == date(2026, 11, 9)
