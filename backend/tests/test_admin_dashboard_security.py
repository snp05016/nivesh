"""AUTH-19 / GH-688 — the admin dashboard runs no inline script, its CSP forbids inline
script, every server string is escaped, and logged request paths are size-capped."""
import re
import uuid
from pathlib import Path

import core.dashboard_state as ds

BACKEND = Path(__file__).resolve().parents[1]


def _script_src(csp: str) -> str:
    return next(d for d in csp.split(";") if d.strip().startswith("script-src"))


def test_dashboard_csp_forbids_inline_script(client):
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    script_src = _script_src(page.headers["content-security-policy"])
    assert "'unsafe-inline'" not in script_src
    assert "'self'" in script_src
    # every other response keeps the strict default
    assert client.get("/ping").headers["content-security-policy"] == "default-src 'self'"


def test_dashboard_page_has_no_inline_script_or_handlers(client):
    html = client.get("/").text
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), "inline <script> block"
    assert not re.search(r"\son[a-z]+\s*=", html, re.I), "inline event handler"
    assert "<style" not in html
    assert 'src="/admin-assets/admin.js"' in html
    assert 'href="/admin-assets/admin.css"' in html
    chart = re.search(r'<script src="https://cdnjs\.cloudflare\.com[^>]*>', html).group(0)
    assert 'integrity="sha512-' in chart and 'crossorigin="anonymous"' in chart


def test_admin_js_escapes_server_strings(client):
    resp = client.get("/admin-assets/admin.js")
    assert resp.status_code == 200
    js = resp.text
    assert "function esc(" in js and "[&<>\"']" in js
    for raw in ("${r.path}", "${u.display_name", "${u.username}", "${v.title}", "${n.headline}",
                "${e.path", "${j.job_id}", "${l.key"):
        assert raw not in js, raw
    assert not re.search(r"\son[a-z]+=\"", js), "inline handler emitted from JS templates"
    assert client.get("/admin-assets/admin.css").status_code == 200


def test_main_py_no_longer_embeds_dashboard_markup():
    src = (BACKEND / "main.py").read_text()
    assert "<script" not in src
    assert "_DASHBOARD_HTML" not in src


def test_request_log_caps_path_and_params(client):
    marker = uuid.uuid4().hex[:8]
    long_path = "/" + marker + "x" * 1000
    client.get(long_path, params={"q": "y" * 1000})
    with ds._dash_lock:
        entries = [e for e in ds._request_log if e["path"].startswith("/" + marker)]
    assert entries, "request was not logged"
    entry = entries[0]
    assert len(entry["path"]) <= 200
    assert all(len(v) <= 200 for v in entry["params"].values())
