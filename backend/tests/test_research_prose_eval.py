"""Offline prose eval harness (spec_ai 3.3): stub generator only, no network, no LLM."""
import importlib.util
import pathlib
from datetime import date

import pytest

import database
from models.db_models import ResearchReportRow

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "research_prose_eval.py"
_spec = importlib.util.spec_from_file_location("research_prose_eval", _PATH)
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def _payload(sym):
    return {"symbol": sym, "report": {"symbol": sym}, "known_symbols": ["A"], "company_names": ["Acme"]}


def _stub(script):
    calls = []
    it = iter(script)

    def generate(report, *, known_symbols, company_names, allow_llm, calls_remaining):
        calls.append(calls_remaining)
        status, attempts, codes = next(it)
        return ({"status": status, "prompt_version": "rf-1", "validator_version": "gv-1"},
                attempts, [{"code": c} for c in codes])

    generate.calls = calls
    return generate


def test_metrics():
    gen = _stub([("llm_validated", 1, []), ("llm_validated", 2, ["literal_number"]),
                 ("template", 2, ["ADVICE", "literal_number"])])
    summary, samples = ev.run_eval([_payload("A"), _payload("B"), _payload("C")], max_calls=40, generate=gen)
    assert summary["n_evaluated"] == 3
    assert summary["first_pass_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert summary["validated_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert summary["failure_codes"] == {"literal_number": 2, "ADVICE": 1}
    assert summary["calls_used"] == 5
    assert len(samples) == 3 and all("narrative" in s for s in samples)


def test_max_calls_stops_the_run():
    gen = _stub([("llm_validated", 1, []), ("llm_validated", 1, []), ("llm_validated", 1, [])])
    summary, _ = ev.run_eval([_payload("A"), _payload("B"), _payload("C")], max_calls=2, generate=gen)
    assert summary["n_evaluated"] == 2 and summary["calls_used"] == 2


def _infile(tmp_path):
    f = tmp_path / "p.jsonl"
    f.write_text('{"symbol": "A", "report": {}, "known_symbols": [], "company_names": []}\n')
    return str(f)


def test_run_without_yes_returns_2(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setattr(ev, "run_eval", lambda *a, **k: pytest.fail("must not run"))
    assert ev.main(["run", "--in", _infile(tmp_path), "--max-calls", "5"]) == 2


def test_run_rejects_201_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    assert ev.main(["run", "--in", _infile(tmp_path), "--max-calls", "201", "--yes"]) == 2


def test_run_needs_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert ev.main(["run", "--in", _infile(tmp_path), "--max-calls", "5", "--yes"]) == 2


def test_no_arguments_prints_usage(capsys):
    assert ev.main([]) != 0
    assert "usage" in capsys.readouterr().out.lower()


def test_freeze_is_deterministic_and_report_only():
    syms = ["ZZEVAL1", "ZZEVAL2", "ZZEVAL3"]
    with database.get_session() as s:
        for sym, d, uid in (("ZZEVAL1", date(2099, 1, 5), "u1"), ("ZZEVAL2", date(2099, 1, 5), "u2"),
                            ("ZZEVAL3", date(2099, 1, 2), "u3")):
            s.add(ResearchReportRow(report_uid=uid, symbol=sym, as_of_date=d, engine_version="t",
                                    origin="nightly", status="ok", in_universe=True, report_json={"symbol": sym}))
        s.commit()
    try:
        with database.get_session() as s:
            a = ev.freeze(s, 5)
            b = ev.freeze(s, 5)
        assert a == b
        assert sorted(i["symbol"] for i in a) == ["ZZEVAL1", "ZZEVAL2"]
        assert all(set(i) == {"symbol", "report", "known_symbols", "company_names"} for i in a)
    finally:
        with database.get_session() as s:
            s.query(ResearchReportRow).filter(ResearchReportRow.symbol.in_(syms)).delete(synchronize_session=False)
            s.commit()
