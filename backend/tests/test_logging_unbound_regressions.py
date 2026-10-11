"""SILENT-V2: a function-local ``import logging`` makes ``logging`` a local name for
the whole function, so any earlier use (a cache-hit log line, an error handler)
raises UnboundLocalError and the endpoint returns 500.
"""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROUTERS = [
    "routers/analysis.py",
    "routers/market.py",
    "routers/portfolio.py",
    "routers/portfolio_analytics.py",
    "routers/morning_brief.py",
]


def test_no_function_local_logging_import():
    offenders = []
    for rel in ROUTERS:
        tree = ast.parse((BACKEND / rel).read_text(), rel)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Import) and any(a.name == "logging" for a in node.names):
                    offenders.append(f"{rel}:{node.lineno} ({fn.name})")
    assert not offenders, f"function-local 'import logging': {offenders}"


def test_quick_info_cache_hit_returns_cached_body(monkeypatch):
    import services.disk_cache as disk_cache
    from routers import analysis

    cached = {"ticker": "RELIANCE", "price": 2500.0}
    monkeypatch.setattr(disk_cache, "get", lambda namespace, key: cached)

    assert analysis.quick_info_endpoint("RELIANCE", "NSE") == cached


def test_morning_summary_error_path_returns_fallback(monkeypatch):
    from routers import morning_brief

    def _db_down():
        raise RuntimeError("db down")

    monkeypatch.setattr(morning_brief, "has_active_consent", lambda *a, **k: True)
    monkeypatch.setattr(morning_brief, "_dcache_get", lambda *a, **k: None)
    monkeypatch.setattr(morning_brief, "_dcache_set", lambda *a, **k: None)
    monkeypatch.setattr(morning_brief, "get_session", _db_down)

    body = morning_brief.morning_summary_endpoint(1, _caller=1)

    assert body["summary"] == "• Market data loaded. AI brief unavailable at this time."
    assert body["mood"] == "cautious"
