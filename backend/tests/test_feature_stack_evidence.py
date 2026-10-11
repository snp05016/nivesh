"""WIP-06: every ticked box in money_control_feature_stack.md must point at real code.

Pure file I/O; imports no backend module. A `[x]` line must carry
`(evidence: <repo-path>:<symbol>; ...)` and each pointer's file must exist and
contain the symbol, so the checklist cannot drift back to bulk-ticked intent.
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STACK = REPO_ROOT / "money_control_feature_stack.md"

CHECKED = re.compile(r"^\s*- \[x\] (.*)$")
EVIDENCE = re.compile(r"\(evidence: ([^)]+)\)")

# Capabilities the 2026-10 audit found with no code behind them; they must stay unticked.
KNOWN_UNBUILT = [
    "Android home-screen widgets",
    "Universal search",
    "Cryptocurrency search",
    "Only buyers",
    "Economic calendar",
    "Graham Number",
    "Ohlson O-score",
    "My Metrics",
    "Bullion",
    "ULIPs",
    "PDF contract-note upload",
    "Excel upload",
    "CAS import",
    "Portfolio X-Ray",
    "Text-to-speech for articles",
    "Live TV",
    "CNBC AWAAZ",
    "Podcasts",
    "Market Minutes",
    "Option chain",
    "Income-tax calculator",
    # Mock KYC/SIM stand-ins (kyc_consent_service is MOCK/DEMO): regulatory/security controls stay unticked.
    "KYC handling",
    "One-time SIM binding",
    "KYC completion",
    "KYC details",
    "SIM-binding controls",
    "KYC security",
]


def _checked_items():
    items = []
    for lineno, line in enumerate(STACK.read_text(encoding="utf-8").splitlines(), 1):
        m = CHECKED.match(line)
        if m:
            items.append((lineno, m.group(1)))
    return items


def _pointers():
    for lineno, body in _checked_items():
        m = EVIDENCE.search(body)
        if not m:
            continue
        for raw in m.group(1).split(";"):
            path, _, symbol = raw.strip().partition(":")
            yield lineno, path, symbol


def test_stack_has_checked_items():
    assert _checked_items(), "no [x] items parsed; the checklist format changed"


def test_every_checked_item_has_evidence():
    missing = [f"line {n}: {body}" for n, body in _checked_items() if not EVIDENCE.search(body)]
    assert not missing, "[x] without (evidence: path:symbol):\n" + "\n".join(missing)


def test_evidence_resolves():
    broken = []
    for lineno, path, symbol in _pointers():
        target = REPO_ROOT / path
        if not path or not symbol:
            broken.append(f"line {lineno}: malformed pointer {path!r}:{symbol!r}")
        elif not target.is_file():
            broken.append(f"line {lineno}: missing file {path}")
        elif symbol not in target.read_text(encoding="utf-8", errors="ignore"):
            broken.append(f"line {lineno}: {symbol!r} not found in {path}")
    assert not broken, "stale evidence pointers:\n" + "\n".join(broken)


@pytest.mark.parametrize("label", KNOWN_UNBUILT)
def test_known_unbuilt_items_stay_unchecked(label):
    ticked = [n for n, body in _checked_items() if body == label or body.startswith(label + " (")]
    assert not ticked, f"{label!r} is ticked at line(s) {ticked} but the audit found no code for it"
