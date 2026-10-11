"""Contract, formatting, config and fixture tests (spec 6, 11.1; package ml-contract)."""

from __future__ import annotations

import json
import re
from datetime import date

import pytest
from pydantic import ValidationError

from research import config
from research.contract import FACT_LABELS, Fact, HorizonOutlook, ResearchReport, outlook_event
from research.export_contract import FIXTURE_DIR, SCHEMA_PATH, main, render_all
from research.formatting import make_fact, range_text

AS_OF = date(2026, 10, 9)
FIXTURES = ("no_edge.json", "validated_cohort.json", "out_of_universe_degraded.json")


def _fact(fid: str, value: float | None, **kw) -> Fact:
    return make_fact(fid, value, source="computed", as_of=AS_OF, **kw)


@pytest.mark.parametrize("name", FIXTURES)
def test_fixtures_validate(name: str) -> None:
    data = json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    report = ResearchReport.model_validate(data)
    assert report.schema_version == "research.v1"


def test_validated_cohort_is_stored_output() -> None:
    report = ResearchReport.model_validate_json((FIXTURE_DIR / "validated_cohort.json").read_bytes())
    assert (report.staleness, report.narrative, report.live_track_record, report.compliance) == (None,) * 4
    assert all(o.tier_text is None and o.prediction_id is None for o in report.outlooks)
    assert all(h.tier_text is None for h in report.model_card.horizons)
    cohort = report.outlooks[0].cohort
    assert cohort is not None and cohort.bucket == 4 and cohort.frequency.display == "54%"


def test_export_check_is_clean() -> None:
    assert main(["--check"]) == 0
    assert all(path.read_bytes() == data for path, data in render_all().items())


def test_unavailable_fact_with_value_raises() -> None:
    with pytest.raises(ValidationError):
        Fact(id="risk.vol_pctl", label="x", value=52.0, unit="pctl", decimals=0, signed=False,
             display="52nd percentile", status="unavailable", reason="source_unavailable",
             source="computed", as_of=AS_OF, method=None)


@pytest.mark.parametrize("bad", [
    {"status": "ok", "reason": "stale_source"},  # reason only when status != ok
    {"status": "stale", "reason": None},  # stale needs a reason
    {"display": None},  # display null iff value null
    {"value": float("nan")},
    {"unexpected": 1},  # extra="forbid"
])
def test_fact_invariants(bad: dict) -> None:
    good = _fact("risk.vol_pctl", 52).model_dump()
    with pytest.raises(ValidationError):
        Fact.model_validate({**good, **bad})


def test_make_fact_unavailable_needs_reason() -> None:
    with pytest.raises(ValueError):
        _fact("risk.vol_pctl", None)
    fact = _fact("risk.vol_pctl", float("nan"), reason="insufficient_history")
    assert (fact.status, fact.value, fact.display, fact.reason) == ("unavailable", None, None, "insufficient_history")


@pytest.mark.parametrize("fid,value,expected", [
    ("snapshot.last_close", 2875.4, "₹2,875.40"),
    ("snapshot.last_close", 12345678.9, "₹1,23,45,678.90"),
    ("snapshot.median_turnover_63d_cr", 1234.5, "₹1,234.5 crore"),
    ("snapshot.market_cap_cr", 123456, "₹1.2 lakh crore"),
    ("snapshot.r_1m_pct", -3.14, "−3.1%"),
    ("snapshot.r_1m_pct", 3.14, "+3.1%"),
    ("snapshot.r_1m_pct", -0.04, "0.0%"),  # rounds to zero: no sign
    ("snapshot.r_6m_pct", 9.85, "+9.9%"),  # half-up on the decimal value
    ("outlook.21.cohort.frequency", 0.54, "54%"),
    ("risk.vol_pctl", 72, "72nd percentile"),
    ("risk.vol_pctl", 11, "11th percentile"),
    ("risk.vol_pctl", 21, "21st percentile"),
    ("risk.vol_pctl", 13, "13th percentile"),
    ("risk.vol_pctl", 3, "3rd percentile"),
    ("risk.vol_pctl", 62.5, "63rd percentile"),  # suffix follows the half-up number shown
    ("risk.vol_pctl", 0.5, "1st percentile"),
    ("snapshot.market_cap_cr", 99999.6, "₹1.0 lakh crore"),  # switch decided on the rounded value
    ("risk.drawdown.days_since_peak", 14, "14 trading days"),
    ("snapshot.excess_12m_vs_nifty50_pp", 3.2, "+3.2 percentage points"),
    ("risk.beta.raw", 1.08, "1.08"),
    ("fund.pe_ttm", 18.4, "18.4x"),
    ("fund.piotroski.f_score", 6, "6"),
    ("fund.cfo_to_pat", -0.5, "−0.50"),  # unsigned facts get no "+", negatives keep U+2212
])
def test_make_fact_display(fid: str, value: float, expected: str) -> None:
    fact = _fact(fid, value)
    assert fact.display == expected
    assert fact.label == FACT_LABELS[fid]


def test_make_fact_uncatalogued_needs_format() -> None:
    with pytest.raises(ValueError):
        _fact("factor.rsi_14.value", 46)
    fact = _fact("factor.rsi_14.value", 46.2, unit="ratio", decimals=0, signed=False, label="RSI")
    assert fact.display == "46"


def test_range_text() -> None:
    low, high = _fact("risk.range.21.low_pct", -6.2), _fact("risk.range.21.high_pct", 8.9)
    text = range_text(21, 756, low, high)
    assert text is not None
    assert text.startswith("Over the last 3 years, 8 in 10")
    assert text.endswith("This is not a forecast.")
    assert text == ("Over the last 3 years, 8 in 10 of this stock's 21-trading-day returns fell "
                    "between −6.2% and +8.9%. This is not a forecast.")
    assert range_text(21, 400, low, high).startswith("Over the last 19 months,")  # type: ignore[union-attr]
    missing = _fact("risk.range.21.high_pct", None, reason="insufficient_history")
    assert range_text(21, 200, low, missing) is None


def test_labels_fit() -> None:
    assert all(0 < len(label) <= 80 for label in FACT_LABELS.values())


def _property_names(node: object, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for name in node.get("properties", {}) if isinstance(node.get("properties"), dict) else {}:
            found.append((path, name))
        for key, child in node.items():
            found.extend(_property_names(child, f"{path}/{key}"))
    elif isinstance(node, list):
        for child in node:
            found.extend(_property_names(child, path))
    return found


def test_schema_has_no_forbidden_names() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    names = _property_names(schema)
    assert len(names) > 100
    forbidden = re.compile(
        r"^(signal|rating|zone|flag|gates)$|^(target|upside|downside|stop|entry|confidence)|coverage"
    )
    # The single exemption: ResearchReport's top-level universe-membership block
    # (spec 6.2 `coverage`), which is not a statistical coverage figure.
    bad = [(p, n) for p, n in names if forbidden.search(n) and not (p == "" and n == "coverage")]
    assert bad == []


def test_cohort_only_for_validated_edge() -> None:
    report = json.loads((FIXTURE_DIR / "validated_cohort.json").read_text(encoding="utf-8"))
    outlook = report["outlooks"][0]
    HorizonOutlook.model_validate(outlook)
    with pytest.raises(ValidationError):
        HorizonOutlook.model_validate({**outlook, "evidence_tier": "weak_evidence"})
    with pytest.raises(ValidationError):
        HorizonOutlook.model_validate({**outlook, "event": outlook_event(63)})


def test_duplicate_fact_id_rejected() -> None:
    report = json.loads((FIXTURE_DIR / "no_edge.json").read_text(encoding="utf-8"))
    report["snapshot"]["r_3m_pct"] = report["snapshot"]["r_1m_pct"]
    with pytest.raises(ValidationError):
        ResearchReport.model_validate(report)


def test_config_sha256_stable() -> None:
    sha = config.config_sha256()
    assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert sha == config.config_sha256()
    # Pre-registration pin: changing any constant is a new trial (spec 5.1).
    # Update this value (and regenerate the fixtures) only with a new procedure version.
    assert sha == "087ea137d486b3baceddd575fab994a2f01417743f253435073f1dfdd2aaf4f9"


def test_config_hash_ignores_paths(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    before = config.config_sha256()
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "LOCAL_CSV", tmp_path / "x.csv")
    assert config.config_sha256() == before
