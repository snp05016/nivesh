"""OPS-06: systemd (nivesh.service) is the only production supervisor. Deploy runbooks must
not kill :8000 or start an unsupervised nohup/--reload uvicorn logging to /tmp."""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNBOOKS = [
    ".claude/skills/nivesh-deploy/SKILL.md",
    ".opencode/skills/senior-engineer/workflows/deployment-handoff.md",
    "AGENTS.md",
    "README.md",
    "docs/codebase/DEPLOYMENT_MAP.md",
]
FORBIDDEN = [r"nohup\s.*uvicorn", r"fuser -k 8000", r"/tmp/uvicorn\.log", r"pkill -f 'uvicorn'"]


@pytest.mark.parametrize("rel", RUNBOOKS)
def test_runbook_uses_systemd_only(rel):
    path = REPO / rel
    if not path.exists():
        pytest.skip(f"{rel} not in this checkout")
    text = path.read_text()
    for pattern in FORBIDDEN:
        assert not re.search(pattern, text), f"{rel} still matches {pattern!r}"


def test_run_sh_is_local_only():
    text = (REPO / "backend" / "run.sh").read_text()
    assert "LOCAL DEVELOPMENT ONLY" in text
    assert re.search(r"--host \"?(\$\{HOST:-)?127\.0\.0\.1", text)
    assert "kill -9" not in text
