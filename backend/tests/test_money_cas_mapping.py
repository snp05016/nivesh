"""CAS parse + mapping (spec 3.5): PII stripping, per-ISIN plan, killable child, licence closure."""
from __future__ import annotations

import json
import logging
import multiprocessing
import re
import threading
from datetime import date
from importlib import metadata
from pathlib import Path

import pytest

from services import money_cas_mapping as mapping
from services import money_cas_parser as parser

FIXTURE = Path(__file__).parent / "fixtures" / "cas_sample.json"
HDFC, AXIS_REG, AXIS_OLD = "INF179K01VC4", "INF846K01DP8", "INF846K01ZZ1"
BANNED_KEYS = {"investor_info", "PAN", "KYC", "PANKYC", "nominees", "advisor", "folio", "folios", "transactions",
               "name_of_investor", "email", "address", "mobile"}


@pytest.fixture
def real_processes(monkeypatch):
    """tests/conftest.py blocks Process.start (TEST-02); the CAS child tests need the real one.

    Re-create BaseProcess.start from the stdlib source with the real module's globals."""
    import ast
    import importlib.util
    import multiprocessing.process as mp_process

    origin = importlib.util.find_spec("multiprocessing.process").origin
    tree = ast.parse(Path(origin).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "BaseProcess")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "start")
    namespace: dict = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), origin, "exec"), vars(mp_process), namespace)
    monkeypatch.setattr(mp_process.BaseProcess, "start", namespace["start"])


@pytest.fixture(scope="module")
def cas():
    return json.loads(FIXTURE.read_text())


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def test_normalize_strips_personal_data(cas):
    out = mapping.normalize(cas)
    blob = json.dumps(out)
    assert not (set(_keys(out)) & BANNED_KEYS)
    for secret in ("XXXXX0000X", "Test Investor", "example.invalid", "1 Test Road", "9999999999", "Test Nominee",
                   "ARN-0000", "1234567/89", "7654321/01"):
        assert secret not in blob
    assert out["statement"] == {"from": "2016-01-01", "to": "2026-10-08", "source": "CAMS", "type": "DETAILED"}


def test_folios_combine_per_isin(cas):
    out = mapping.normalize(cas)
    hdfc = [s for s in out["schemes"] if s["isin"] == HDFC]
    assert len(hdfc) == 1
    assert hdfc[0]["close"] == pytest.approx(123.456)
    assert hdfc[0]["valuation"] == {"date": "2026-10-08", "nav": 45.67, "value": 5638.07, "cost": 5000.0}
    assert len(out["schemes"]) == 4


def test_plan_modes_and_reasons(cas):
    out = mapping.normalize(cas)
    plans = {p["isin"] or p["name"]: p for p in mapping.plan(out, {}, set())}
    assert plans[HDFC]["mode"] == "balance"
    assert plans[HDFC]["adjust"]["quantity"] == 123.456
    assert plans[HDFC]["adjust"]["price"] == pytest.approx(5000.0 / 123.456, abs=1e-3)
    assert plans[HDFC]["adjust"]["date"] == "2026-10-08"
    assert plans[AXIS_REG]["flags"] == ["cost_unknown"] and plans[AXIS_REG]["adjust"]["price"] == 60.0
    assert (plans[AXIS_OLD]["mode"], plans[AXIS_OLD]["reason"]) == ("skipped", "zero_balance")
    assert plans["Mystery Fund - Growth"]["reason"] == "isin_missing"
    summary = mapping.preview_summary(list(plans.values()))
    assert summary == {"schemes": 4, "balance": 2, "skipped": 2, "value_inr": round(5638.07 + 3000.0, 2)}


def test_plan_manual_older_and_closing(cas):
    out = mapping.normalize(cas)
    plans = {p["isin"]: p for p in mapping.plan(out, {HDFC: date(2026, 10, 8), AXIS_OLD: date(2026, 1, 1)}, {AXIS_REG})}
    assert plans[HDFC]["reason"] == "older_statement"
    assert plans[AXIS_REG]["reason"] == "manual_entries_exist"
    closing = plans[AXIS_OLD]
    assert closing["mode"] == "balance" and closing["adjust"]["quantity"] == 0.0 and closing["adjust"]["price"] == 0.0
    assert closing["flags"] == []


def test_keys_stable_and_unit_sensitive(cas):
    a = mapping.plan(mapping.normalize(cas), {}, set())[0]["adjust"]["key"]
    b = mapping.plan(mapping.normalize(cas), {}, set())[0]["adjust"]["key"]
    assert a == b and re.fullmatch(r"casbal:[0-9a-f]{48}", a)
    changed = json.loads(FIXTURE.read_text())
    changed["folios"][1]["schemes"][0]["close"] = "24.456"
    c = mapping.plan(mapping.normalize(changed), {}, set())[0]["adjust"]["key"]
    assert c != a


def test_timeout_kills_child_and_leaves_none_alive(real_processes):
    with pytest.raises(parser.CASParseError) as exc:
        parser.parse_cas_pdf(b"%PDF", "pw", target="tests.cas_fake_parsers:sleeper", timeout=0.5)
    assert exc.value.code == "PARSE_TIMEOUT"
    assert multiprocessing.active_children() == []


def test_child_error_is_classified_and_message_not_leaked(real_processes, caplog):
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(parser.CASParseError) as exc:
            parser.parse_cas_pdf(b"%PDF", "s3cret-pw", target="tests.cas_fake_parsers:raiser", timeout=20)
    assert exc.value.code == "UNSUPPORTED_STATEMENT"
    assert "s3cret-pw" not in caplog.text and "s3cret-pw" not in str(exc.value)


def test_third_concurrent_call_is_busy(real_processes):
    results = []

    def run():
        try:
            parser.parse_cas_pdf(b"%PDF", "pw", target="tests.cas_fake_parsers:sleeper", timeout=4)
        except parser.CASParseError as e:
            results.append(e.code)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    deadline = threading.Event()
    while parser._SEM._value > 0 and not deadline.wait(0.05):  # both slots taken
        pass
    with pytest.raises(parser.CASParseError) as exc:
        parser.parse_cas_pdf(b"%PDF", "pw", target="tests.cas_fake_parsers:sleeper", timeout=1)
    assert exc.value.code == "PARSE_BUSY"
    for t in threads:
        t.join()
    assert results == ["PARSE_TIMEOUT", "PARSE_TIMEOUT"]
    assert multiprocessing.active_children() == []


def test_wrong_password_and_demat_mapping(monkeypatch, caplog):
    casparser = pytest.importorskip("casparser")
    from casparser.exceptions import IncorrectPasswordError

    def wrong(*_a, **_k):
        raise IncorrectPasswordError("bad pw: s3cret-pw")

    monkeypatch.setattr(casparser, "read_cas_pdf", wrong)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(parser.CASParseError) as exc:
            parser._read_and_normalize(b"%PDF", "s3cret-pw")
    assert exc.value.code == "WRONG_PASSWORD" and "s3cret-pw" not in caplog.text

    monkeypatch.setattr(casparser, "read_cas_pdf", lambda *a, **k: {"file_type": "NSDL"})
    with pytest.raises(parser.CASParseError) as exc:
        parser._read_and_normalize(b"%PDF", "pw")
    assert exc.value.code == "DEMAT_CAS_NOT_SUPPORTED"

    def broken(*_a, **_k):
        raise ValueError("garbage")

    monkeypatch.setattr(casparser, "read_cas_pdf", broken)
    with pytest.raises(parser.CASParseError) as exc:
        parser._read_and_normalize(b"nope", "pw")
    assert exc.value.code == "UNSUPPORTED_STATEMENT"


def _closure(name, seen):
    key = re.split(r"[ ;<>=!~\[(]", name, maxsplit=1)[0].lower().replace("_", "-")
    if key in seen:
        return
    try:
        dist = metadata.distribution(key)
    except metadata.PackageNotFoundError:
        return
    seen[key] = dist
    for req in dist.requires or []:
        if "extra ==" in req:
            continue
        _closure(req, seen)


def test_casparser_dependency_closure_has_no_gpl():
    pytest.importorskip("casparser")
    seen: dict = {}
    _closure("casparser", seen)
    bad = []
    for name, dist in seen.items():
        meta = dist.metadata
        fields = [meta.get("License") or "", meta.get("License-Expression") or ""] + (meta.get_all("Classifier") or [])
        text = " | ".join(fields)
        if "AGPL" in text.upper() or re.search(r"(?<!L)GPL", text.upper()) and "LGPL" not in text.upper():
            bad.append(name)
    assert not bad, f"copyleft licence in casparser's dependency closure: {bad}"
