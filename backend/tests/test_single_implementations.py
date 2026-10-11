"""ARCH-18: each shared rule has one implementation that every caller uses."""
import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def test_copilot_strip_emoji_keeps_rupee_and_dash():
    from services.copilot_service import strip_emoji
    from services.harvester_reformatter import strip_emoji as canonical

    assert strip_emoji is canonical
    assert strip_emoji("₹1,200 – up 📈") == "₹1,200 – up"


@pytest.mark.parametrize("raw,expected", [
    ('Sure! {"a":1} thanks', {"a": 1}),
    ('```json\n{"signal": "buy", "t": {"bull": 1}}\n```\nGood luck!', {"signal": "buy", "t": {"bull": 1}}),
    # Array payloads (macro_impact, trade_journal_stats) must survive intact.
    ('```json\n[{"d": "positive"}, {"d": "neutral"}]\n```', [{"d": "positive"}, {"d": "neutral"}]),
    ('Here you go: [{"pattern": "x"}]', [{"pattern": "x"}]),
    ('Note [draft]: {"a": 2}', {"a": 2}),
])
def test_extract_json_from_text(raw, expected):
    from services.llm_utils import extract_json_from_text

    assert json.loads(extract_json_from_text(raw)) == expected


def test_extract_json_fallbacks():
    from services.llm_utils import extract_json_from_text

    assert extract_json_from_text("```\nplain text\n```") == "plain text"
    assert extract_json_from_text("no ticks") == "no ticks"


def test_json_extractor_is_shared():
    import helpers
    from services import orchestrator, yfinance_client
    from services.llm_utils import extract_json_from_text

    assert helpers._extract_json_from_text is extract_json_from_text
    assert orchestrator._extract_json_from_text is extract_json_from_text
    assert yfinance_client._extract_json_from_text is extract_json_from_text


def test_legacy_stress_test_route_removed():
    from main import app

    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/portfolio/stress-test" not in paths
    assert "/api/v1/portfolio/stress-test" in paths


@pytest.mark.parametrize("name", ["strip_emoji", "_?extract_json_from_text", "_?check_kyc_gate"])
def test_rule_defined_once(name):
    pattern = re.compile(rf"^\s*def {name}\(", re.MULTILINE)
    hits = [
        str(p.relative_to(BACKEND))
        for d in ("services", "routers", "core")
        for p in (BACKEND / d).rglob("*.py")
        if pattern.search(p.read_text(encoding="utf-8", errors="ignore"))
    ]
    hits += [f for f in ("helpers.py", "main.py") if pattern.search((BACKEND / f).read_text(encoding="utf-8"))]
    assert len(hits) == 1, hits
