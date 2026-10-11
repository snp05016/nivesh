#!/usr/bin/env python3
"""
Export the FastAPI OpenAPI schema to backend/openapi.json, the committed
API contract between the backend and the iOS app (ARCH-04).

    python backend/scripts/export_openapi.py          # regenerate the snapshot
    python backend/scripts/export_openapi.py --check  # exit 1 if it is stale

Run it after any route or schema change and commit the result, so the diff is
reviewed. CI runs --check. No server or real secrets are needed: the app is
imported against a throwaway SQLite file with NIVESH_TESTING=1 (no .env load).
"""

import argparse
import difflib
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT = BACKEND_DIR / "openapi.json"

sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("NIVESH_TESTING", "1")
os.environ.setdefault(
    "DATABASE_URL", f"sqlite:///{tempfile.mkdtemp(prefix='nivesh-openapi-')}/openapi.db"
)
os.environ.setdefault("ENABLE_SCHEDULER", "false")
os.environ.setdefault("JWT_SECRET", "openapi-export-dummy-secret-0123456789")


def render() -> str:
    import main  # after the env defaults above

    return json.dumps(main.app.openapi(), indent=2, sort_keys=True) + "\n"


def _operations(text: str) -> set[str]:
    paths = json.loads(text).get("paths", {})
    return {f"{m.upper()} {p}" for p, ops in paths.items() for m in ops}


def main_cli() -> int:
    parser = argparse.ArgumentParser(description="Export or check backend/openapi.json")
    parser.add_argument("--check", action="store_true", help="fail if openapi.json is stale")
    args = parser.parse_args()

    current = render()
    if not args.check:
        SNAPSHOT.write_text(current, encoding="utf-8")
        print(f"[OK] wrote {SNAPSHOT} ({len(_operations(current))} operations)")
        return 0

    if not SNAPSHOT.exists():
        print(f"[FAIL] {SNAPSHOT} is missing; run scripts/export_openapi.py and commit it",
              file=sys.stderr)
        return 1
    committed = SNAPSHOT.read_text(encoding="utf-8")
    if committed == current:
        print(f"[OK] {SNAPSHOT.name} is up to date")
        return 0

    old_ops, new_ops = _operations(committed), _operations(current)
    print(f"[FAIL] {SNAPSHOT.name} is stale; run scripts/export_openapi.py and commit the diff",
          file=sys.stderr)
    for op in sorted(new_ops - old_ops):
        print(f"  + {op}", file=sys.stderr)
    for op in sorted(old_ops - new_ops):
        print(f"  - {op}", file=sys.stderr)
    diff = list(difflib.unified_diff(committed.splitlines(), current.splitlines(),
                                     "openapi.json (committed)", "openapi.json (generated)",
                                     lineterm=""))
    print("\n".join(diff[:200]), file=sys.stderr)
    if len(diff) > 200:
        print(f"... {len(diff) - 200} more diff lines", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main_cli())
