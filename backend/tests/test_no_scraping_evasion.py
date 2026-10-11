"""REG-10: no anti-bot evasion in data acquisition: no residential-proxy
(ScraperAPI) fetches, no rotating fake User-Agents. Source scan only."""
import os
import re
from pathlib import Path

from config.settings import get_user_agent

BACKEND = Path(__file__).resolve().parents[1]

_PROXY = re.compile(r"scraperapi\.com|SCRAPERAPI_API_KEY", re.IGNORECASE)
_FAKE_UA_IMPORT = re.compile(r"^\s*(?:from|import)\s+fake_useragent\b", re.MULTILINE)


_SKIP_DIRS = {"tests", "venv", ".venv", "__pycache__", "site-packages", "node_modules", ".git"}


def _sources():
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                yield Path(root) / name


def test_no_residential_proxy_fetches():
    hits = [str(p.relative_to(BACKEND)) for p in _sources() if _PROXY.search(p.read_text(errors="ignore"))]
    assert hits == []


def test_no_fake_useragent():
    hits = [str(p.relative_to(BACKEND)) for p in _sources() if _FAKE_UA_IMPORT.search(p.read_text(errors="ignore"))]
    assert hits == []
    for req in BACKEND.glob("requirements*.txt"):
        assert "fake-useragent" not in req.read_text().lower(), req.name
        assert "fake_useragent" not in req.read_text().lower(), req.name


def test_user_agent_is_constant_and_honest():
    ua = get_user_agent()
    assert ua == get_user_agent()
    assert ua.startswith("NiveshBot/")
    assert "Mozilla" not in ua
