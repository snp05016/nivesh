"""Static checks for the admin console's Flags, Jobs, Audit and Usage pages (CSP cannot be unit-tested)."""
import re
from pathlib import Path

ADMIN = Path(__file__).resolve().parent.parent / "static" / "admin"
HTML = (ADMIN / "index.html").read_text(encoding="utf-8")
JS = (ADMIN / "admin.js").read_text(encoding="utf-8")
PAGES = ("flags", "jobs", "audit", "usage")


def _function(name: str) -> str:
    start = re.search(rf"(async )?function {name}\(", JS)
    assert start, name
    nxt = re.search(r"\n(async )?function |\n// ───|\nlet |\nconst ", JS[start.end():])
    return JS[start.start(): start.end() + (nxt.start() if nxt else len(JS))]


def test_pages_and_nav_tabs_exist():
    for page in PAGES:
        assert f'id="page-{page}"' in HTML
        assert f'data-action="showPage" data-arg="{page}"' in HTML


def test_no_inline_handlers_or_script():
    assert not re.search(r"\son[a-z]+\s*=", HTML)
    for body in re.findall(r"<script\b[^>]*>(.*?)</script>", HTML, flags=re.S):
        assert body.strip() == ""


def test_usage_labels():
    assert "Active users with analytics on" in HTML
    assert "Counts only users who turned on usage analytics." in HTML
    assert 'id="usage-active-users"' in HTML and 'id="flags-table"' in HTML
    assert 'id="jobs-summary"' in HTML and 'id="jobs-failures"' in HTML and 'id="audit-table"' in HTML
    assert 'data-action="loadAuditOlder"' in HTML


def test_js_uses_the_admin_endpoints():
    for endpoint in ("/api/v1/admin/flags", "/api/v1/admin/job-runs/summary?days=7",
                     "/api/v1/admin/job-runs?status=failed&limit=20", "/api/v1/admin/audit",
                     "/api/v1/admin/analytics/daily?days=14"):
        assert endpoint in JS, endpoint
    assert "active_users" in JS


def test_server_strings_go_through_esc():
    flags, jobs, audit, usage = (_function(n) for n in ("loadFlags", "loadJobs", "loadAudit", "loadUsage"))
    for expr in ("esc(f.key)", "esc(f.description)", "esc(f.source)"):
        assert expr in flags, expr
    for expr in ("esc(j.job_name)", "esc(r.job_name)", "esc((j.last_error", "esc((r.error"):
        assert expr in jobs, expr
    for expr in ("esc(e.action)", "esc(e.actor_user_id)", "esc(e.ip_address"):
        assert expr in audit, expr
    for expr in ("esc(x.event_name)", "esc(x.date)"):
        assert expr in usage, expr


def test_every_interpolation_in_render_functions_is_escaped_or_numeric():
    allowed = re.compile(r"^(esc\(|flagToggle\(|fmt\(|stbadge\(|dts\(|f\.enabled\?|r\.duration_ms==null|d\.overall_success_pct)")
    for name in ("loadFlags", "flagToggle", "loadJobs", "loadAudit", "loadUsage"):
        for expr in re.findall(r"\$\{(.*?)\}", _function(name)):
            assert allowed.match(expr.strip()), f"{name}: unescaped interpolation ${{{expr}}}"


def test_toggle_flag_confirms_and_sends_json():
    toggle = _function("toggleFlag")
    assert "confirm(" in toggle and "PUT" in toggle
    assert "application/json" in toggle and "JSON.stringify({enabled" in toggle
    assert "Update failed (" in toggle


def test_show_page_activates_by_data_arg_and_loads_new_pages():
    show = _function("showPage")
    assert "navMap" not in JS
    assert "t.dataset.arg===name" in show
    for loader in ("loadFlags", "loadJobs", "loadAudit", "loadUsage"):
        assert loader in show


def test_actions_registered():
    assert re.search(r"const actions=\{[^}]*toggleFlag[^}]*loadAuditOlder", JS, flags=re.S)
