#!/usr/bin/env python3
"""Fail when a backend Python module has no importer outside the tests.

Usage: find_unreferenced_modules.py [<backend-root>]   (default: backend/ next to scripts/)

Every .py file under the root is parsed (never imported). References are the
dotted names in `import` / `from ... import` statements (relative ones resolved)
plus string constants shaped like module paths ("services.x", "main:app"), so
importlib/uvicorn/mock-style references count. A module is live when some live,
non-test file references it or one of its submodules. Dead modules are dropped
and the scan repeats, so code imported only by other dead code is reported too.

Candidates exclude tests/, migrations/, and the importer-only scripts/ (run by
hand) and vendored tradingagents-core/ (which imports backend services). Entry
points nothing imports belong in ALLOWLIST.

ponytail: module-level only; a dead function inside a live module is not caught.
Swap in vulture if that matters.
"""
import ast
import re
import sys
from pathlib import Path

# Dotted module names that are intentionally unreferenced. Only shrink this list:
# a new dead module should be deleted or wired up, not added here.
ALLOWLIST = {
    "main",  # uvicorn entry point (main:app)
    "conftest",  # pytest
    # Unreferenced or test-only when this check landed (audit ARCH-19); other audit
    # items decide whether each is wired up or deleted.
    "services.rate_limiter",  # ARCH-11 wires it in
    "services.outcome_tracker",  # ML-03 registers the outcome job after DB-03
    "services.macro_modifiers",
    "models.signal_config",
    # Test-only engines that MATH-22 fixed and tested (capital gains, XIRR, IV);
    # wire them into the portfolio/options routes or delete them with their tests.
    "services.math_engines.capital_gains_calculator",
    "services.math_engines.implied_volatility_engine",
    "services.math_engines.xirr_calculator",
    # Research engine client and router, landed ahead of main.py wiring.
    "routers.research",
    "repositories.research_repo",
    "services.research",
    "services.research.client",
    "services.research.config",
    "services.research.facts",
    "services.research.formatter",
    "services.research.jobs",
    "services.research.serve",
    "services.research.templates",
    "services.research.validator",
}

IMPORTER_ONLY = ("scripts", "tradingagents-core")
SKIP_DIRS = {"tests", "migrations", "venv", ".venv", "__pycache__", *IMPORTER_ONLY}
DOTTED = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*$")


def module_name(path: Path, root: Path) -> str:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def references(path: Path, root: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    except (SyntaxError, UnicodeDecodeError):
        return set()
    package = module_name(path, root).split(".")
    if path.name != "__init__.py":
        package = package[:-1]
    refs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            mod = ".".join(base + ([node.module] if node.module else []))
            if mod:
                refs.add(mod)
            refs.update(f"{mod}.{a.name}" if mod else a.name for a in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and re.search(r"[.:]", node.value):
            for s in node.value.split(":"):
                if DOTTED.match(s):
                    refs.add(s)
    return {r.removeprefix("backend.") for r in refs}


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "backend").resolve()
    files = [p for p in root.rglob("*.py") if not SKIP_DIRS.intersection(p.relative_to(root).parts[:-1])]
    candidates = {module_name(p, root): p for p in files}
    files += [p for d in IMPORTER_ONLY for p in (root / d).rglob("*.py")]
    refs = {p: references(p, root) for p in files}

    # Each file's references and their parent packages, minus the file itself and its
    # own ancestors, so a package kept alive only by its own children still counts as dead.
    reached = {}
    for p, r in refs.items():
        own = module_name(p, root)
        ancestors = {own.rsplit(".", i)[0] for i in range(own.count(".") + 1)}
        reached[own] = {x.rsplit(".", i)[0] for x in r for i in range(x.count(".") + 1)} - ancestors

    dead: set[str] = set()
    while True:
        live = set().union(*(r for m, r in reached.items() if m not in dead))
        newly = {m for m in candidates if m not in dead and m not in ALLOWLIST and m not in live}
        if not newly:
            break
        dead |= newly

    for m in sorted(dead):
        print(f"unreferenced: {candidates[m].relative_to(root)} ({m})")
    stale = sorted(a for a in ALLOWLIST if a not in candidates)
    for a in stale:
        print(f"stale ALLOWLIST entry (module gone, remove it): {a}")
    if dead or stale:
        print(f"{len(dead)} unreferenced module(s): delete them, wire them up, or (entry points only) allowlist.")
        return 1
    print(f"OK: all {len(candidates)} backend modules are referenced or allowlisted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
