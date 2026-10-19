"""I02 honesty guard: no random number may reach a user as data.

Pure AST walk of backend/routers, backend/services and backend/repositories.
Imports no backend module and needs no network. Import aliases are resolved
per file (``import random as r``, ``import numpy as _np``,
``from numpy import random as nr``, ``from random import uniform as u``), so a
renamed import cannot hide a ``random.*`` / ``numpy.random.*`` call.

A call is allowed only for a (relative path, enclosing function) pair listed in
ALLOWED, with a reason. Never allow a function whose result reaches an API
response as data: use an 'unavailable' state instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SCANNED_DIRS = ("routers", "services", "repositories")
FLAGGED_PREFIXES = ("random.", "numpy.random.")

_JITTER = "retry/backoff jitter in time.sleep; never returned as data"

ALLOWED: dict[tuple[str, str], str] = {
    ("routers/analysis.py", "_fetch_info"): _JITTER,
    ("routers/market.py", "nifty_history_endpoint"): _JITTER,
    ("routers/market.py", "sector_weekly_endpoint"): _JITTER,
    ("services/market_service.py", "_fetch"): _JITTER,
    ("services/market_service.py", "_yf_frame"): _JITTER,
    ("services/nse_client.py", "_fetch_single_index"): _JITTER + " (imported as _random)",
    ("services/yfinance_client.py", "_yf_fetch_info_uncached"): _JITTER,
    ("services/yfinance_client.py", "_yf_price_uncached"): _JITTER + " (request pacing)",
    ("services/math_engines/monte_carlo_bootstrap.py", "compute"): (
        "seeded (seed=42) bootstrap resampling of real returns for a simulation, not data"
    ),
}


def build_alias_map(tree: ast.AST) -> dict[str, str]:
    """Map every local name bound by an import (at any depth) to its canonical dotted name."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    aliases[a.asname] = a.name
                else:
                    # `import numpy.random` binds `numpy`
                    root = a.name.split(".")[0]
                    aliases[root] = root
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
    return aliases


def _dotted(node: ast.AST) -> str | None:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _is_main_guard(test: ast.expr) -> bool:
    if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)):
        return False
    sides = [test.left, test.comparators[0]]
    has_name = any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides)
    has_main = any(isinstance(s, ast.Constant) and s.value == "__main__" for s in sides)
    return has_name and has_main


class RandomCallVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, aliases: dict[str, str]) -> None:
        self.rel_path = rel_path
        self.aliases = aliases
        self.func_stack: list[str] = []
        self.hits: list[tuple[str, str, str]] = []

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.func_stack.append(node.name)
        self.generic_visit(node)
        self.func_stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_If(self, node: ast.If) -> None:
        if _is_main_guard(node.test):
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func)
        if name:
            head, _, rest = name.partition(".")
            canonical = self.aliases.get(head, head) + ("." + rest if rest else "")
            if canonical.startswith(FLAGGED_PREFIXES):
                func = self.func_stack[-1] if self.func_stack else "<module>"
                self.hits.append((self.rel_path, func, canonical))
        self.generic_visit(node)


def scan_source(source: str, rel_path: str = "<string>") -> list[tuple[str, str, str]]:
    tree = ast.parse(source)
    visitor = RandomCallVisitor(rel_path, build_alias_map(tree))
    visitor.visit(tree)
    return visitor.hits


def scan_tree() -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    for d in SCANNED_DIRS:
        for path in sorted((BACKEND / d).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(BACKEND).as_posix()
            hits.extend(scan_source(path.read_text(encoding="utf-8"), rel))
    return hits


def test_no_unlisted_random_calls():
    offenders = sorted({h for h in scan_tree() if (h[0], h[1]) not in ALLOWED})
    assert not offenders, (
        "Random-number calls outside ALLOWED (use an 'unavailable' state, not a random number):\n"
        + "\n".join(f"  {p}::{f} -> {c}" for p, f, c in offenders)
    )


def test_allowlist_has_no_stale_entries():
    seen = {(p, f) for p, f, _ in scan_tree()}
    stale = sorted(set(ALLOWED) - seen)
    assert not stale, "Stale ALLOWED entries (no random call there any more), remove them:\n" + "\n".join(
        f"  {p}::{f}" for p, f in stale
    )


def test_visitor_resolves_aliases():
    cases = {
        "import random as r\ndef f():\n    return r.random()": ("f", "random.random"),
        "import numpy as _np\ndef g():\n    return _np.random.rand(3)": ("g", "numpy.random.rand"),
        "from random import uniform as u\ndef h():\n    return u(1, 2)": ("h", "random.uniform"),
        "import numpy.random as npr\ndef i():\n    return npr.normal()": ("i", "numpy.random.normal"),
        "from numpy import random as nr\ndef j():\n    return nr.rand()": ("j", "numpy.random.rand"),
        "from numpy.random import default_rng\ndef k():\n    return default_rng(1)": (
            "k",
            "numpy.random.default_rng",
        ),
        "def m():\n    import random as _random\n    return _random.uniform(0, 1)": ("m", "random.uniform"),
    }
    for src, (func, canonical) in cases.items():
        assert scan_source(src) == [("<string>", func, canonical)], src


def test_visitor_ignores_non_random_and_main_guard():
    assert scan_source("import numpy as _np\ndef f(x):\n    return _np.isnan(x)") == []
    assert scan_source("import random\nif __name__ == '__main__':\n    print(random.random())") == []
    assert scan_source("import random\nrandom.seed(1)") == [("<string>", "<module>", "random.seed")]
