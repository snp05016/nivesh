"""C12: keep blocking project calls out of `async def` and catch `await` on plain functions.

Ruff's flake8-async codes (backend/ruff.toml) cover generic blocking I/O. This stdlib-ast test
covers what ruff cannot know:

1. project blocking calls (get_session, deepseek_chat, claude_messages, claude_haiku,
   yfinance.download / yfinance.Ticker) called inside an async def;
2. an `await` whose callee resolves exactly to a plain `def` (same module, a backend import
   alias, or a method of the same class). Attribute calls on other objects are never flagged.

A trailing `# async-ok: <reason>` comment suppresses a finding. The baseline can only shrink.
It never imports backend modules.
"""
import ast
import re
from pathlib import Path
from typing import Callable, Iterator, Optional

BACKEND = Path(__file__).resolve().parent.parent

BLOCKING_NAMES = {"get_session", "deepseek_chat", "claude_messages", "claude_haiku"}
BLOCKING_DOTTED = {"yfinance.download", "yfinance.Ticker"}
_ASYNC_OK = re.compile(r"#\s*async-ok:\s*\S")

Finding = tuple[str, str, str, str]  # (path, enclosing function, check, callee)


# --- scanner -----------------------------------------------------------------

class Tree:
    """Source files of one backend tree: {relative path: source}, parsed on demand."""

    def __init__(self, files: dict[str, str]):
        self.files = files
        self._parsed: dict[str, Optional[ast.Module]] = {}

    def parse(self, rel: str) -> Optional[ast.Module]:
        if rel not in self._parsed:
            try:
                self._parsed[rel] = ast.parse(self.files[rel]) if rel in self.files else None
            except SyntaxError:
                self._parsed[rel] = None
        return self._parsed[rel]

    def module_file(self, dotted: str) -> Optional[str]:
        base = dotted.replace(".", "/")
        for candidate in (f"{base}.py", f"{base}/__init__.py"):
            if candidate in self.files:
                return candidate
        return None

    def toplevel_defs(self, rel: str) -> tuple[set[str], set[str]]:
        """(plain def names, async def names) defined at module level of `rel`."""
        tree = self.parse(rel)
        sync, asyn = set(), set()
        for node in tree.body if tree else []:
            if isinstance(node, ast.FunctionDef):
                sync.add(node.name)
            elif isinstance(node, ast.AsyncFunctionDef):
                asyn.add(node.name)
        return sync, asyn


def _package_of(rel: str) -> list[str]:
    parts = rel[:-3].split("/")
    return parts if parts[-1] == "__init__" and parts.pop() else parts[:-1]


def _imports(rel: str, tree: ast.Module) -> dict[str, str]:
    """local name -> dotted target, from import / from-import statements anywhere in the module."""
    names: dict[str, str] = {}
    package = _package_of(rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    names[alias.asname] = alias.name
                else:
                    names[alias.name.split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - (node.level - 1)] if node.level - 1 <= len(package) else []
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            for alias in node.names:
                names[alias.asname or alias.name] = f"{module}.{alias.name}" if module else alias.name
    return names


def _chain(node: ast.AST) -> Optional[list[str]]:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return parts[::-1]
    return None


def _walk_own_body(func: ast.AST) -> Iterator[ast.AST]:
    """Nodes of a function body, not descending into nested defs, lambdas or classes."""
    stack = list(reversed(getattr(func, "body", [])))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def _async_functions(tree: ast.AST, cls: Optional[ast.ClassDef] = None) -> Iterator[tuple[ast.AsyncFunctionDef, Optional[ast.ClassDef]]]:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            yield from _async_functions(node, node)
        else:
            if isinstance(node, ast.AsyncFunctionDef):
                yield node, cls
            yield from _async_functions(node, cls)


def _suppressed(lines: list[str], node: ast.AST) -> bool:
    for lineno in {node.lineno, getattr(node, "end_lineno", node.lineno)}:
        if 0 < lineno <= len(lines) and _ASYNC_OK.search(lines[lineno - 1]):
            return True
    return False


def scan_source(rel: str, source: str, tree_index: Optional[Tree] = None) -> list[Finding]:
    """Findings for one module. `tree_index` resolves imports to other backend modules."""
    tree_index = tree_index or Tree({rel: source})
    module = ast.parse(source)
    lines = source.splitlines()
    imports = _imports(rel, module)
    local_sync, local_async = tree_index.toplevel_defs(rel) if rel in tree_index.files else (set(), set())
    if rel not in tree_index.files:
        tree_index = Tree({**tree_index.files, rel: source})
        local_sync, local_async = tree_index.toplevel_defs(rel)
    findings: list[Finding] = []

    def resolved(call_func: ast.AST) -> Optional[str]:
        chain = _chain(call_func)
        if not chain:
            return None
        root = imports.get(chain[0])
        if root is None:
            return chain[0] if len(chain) == 1 else None  # unknown object: attribute calls are skipped
        return ".".join([root] + chain[1:])

    def sync_target(call_func: ast.AST, cls: Optional[ast.ClassDef]) -> Optional[str]:
        """Dotted description of the callee when it is exactly a plain def, else None."""
        chain = _chain(call_func)
        if not chain:
            return None
        if len(chain) == 1:
            name = chain[0]
            if name in imports:  # (a) from <backend module> import f [as g]
                dotted = imports[name]
                mod, _, func = dotted.rpartition(".")
                target = tree_index.module_file(mod) if mod else None
                if target:
                    sync, asyn = tree_index.toplevel_defs(target)
                    return dotted if func in sync and func not in asyn else None
                return None
            if name in local_sync and name not in local_async:  # (a) same module
                return name
            return None
        if chain[0] == "self" and len(chain) == 2 and cls is not None:  # (b)
            kinds = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == chain[1]]
            if kinds and all(isinstance(n, ast.FunctionDef) for n in kinds):
                return f"self.{chain[1]}"
            return None
        if len(chain) == 2 and chain[0] in imports:  # (c) mod.f()
            target = tree_index.module_file(imports[chain[0]])
            if target:
                sync, asyn = tree_index.toplevel_defs(target)
                if chain[1] in sync and chain[1] not in asyn:
                    return f"{imports[chain[0]]}.{chain[1]}"
        return None

    for func, cls in _async_functions(module):
        for node in _walk_own_body(func):
            if isinstance(node, ast.Call):
                dotted = resolved(node.func)
                if dotted and (dotted.split(".")[-1] in BLOCKING_NAMES or dotted in BLOCKING_DOTTED) \
                        and not _suppressed(lines, node):
                    findings.append((rel, func.name, "blocking-call", dotted))
            elif isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                target = sync_target(node.value.func, cls)
                if target and not _suppressed(lines, node):
                    findings.append((rel, func.name, "await-sync", target))
    return findings


def scan_files(files: dict[str, str], scan_set: Callable[[str], bool]) -> set[Finding]:
    index = Tree(files)
    found: set[Finding] = set()
    for rel in sorted(files):
        if scan_set(rel):
            found.update(scan_source(rel, files[rel], index))
    return found


def in_scan_set(rel: str) -> bool:
    return rel == "main.py" or rel.startswith(("routers/", "core/", "middleware/", "services/"))


def load_backend() -> dict[str, str]:
    skip = {"venv", ".venv", "tests", "tests_suite", "tradingagents-core", "migrations", "__pycache__", "scripts"}
    files = {}
    for path in BACKEND.rglob("*.py"):
        rel = path.relative_to(BACKEND)
        if rel.parts[0] in skip or "__pycache__" in rel.parts:
            continue
        files[rel.as_posix()] = path.read_text(encoding="utf-8")
    return files


# --- unit cases --------------------------------------------------------------

def _scan(source, extra=None, rel="routers/h.py"):
    return scan_files({rel: source, **(extra or {})}, lambda r: r == rel)


def test_flags_get_session_in_async_def():
    assert _scan("async def h():\n    get_session()\n") == {("routers/h.py", "h", "blocking-call", "get_session")}


def test_flags_get_session_with_statement_and_alias():
    src = "from database import get_session as gs\nasync def h():\n    with gs() as s:\n        pass\n"
    assert _scan(src) == {("routers/h.py", "h", "blocking-call", "database.get_session")}


def test_to_thread_and_nested_def_pass():
    assert _scan("import asyncio\nasync def h():\n    await asyncio.to_thread(get_session)\n") == set()
    assert _scan("async def h():\n    def inner():\n        get_session()\n    return inner\n") == set()
    assert _scan("async def h():\n    f = lambda: get_session()\n") == set()
    assert _scan("def h():\n    get_session()\n") == set()


def test_flags_yfinance_calls():
    src = "import yfinance as yf\nasync def h():\n    yf.Ticker('X')\n    yf.download('X')\n"
    assert {f[3] for f in _scan(src)} == {"yfinance.Ticker", "yfinance.download"}


def test_await_on_imported_sync_function_is_flagged():
    files = {"services/x.py": "def f():\n    return 1\n"}
    src = "from services.x import f\nasync def h():\n    await f()\n"
    assert _scan(src, files) == {("routers/h.py", "h", "await-sync", "services.x.f")}


def test_await_on_async_function_and_third_party_calls_pass():
    files = {"services/x.py": "async def f():\n    return 1\n", "services/json.py": "def json():\n    return 1\n"}
    assert _scan("from services.x import f\nasync def h():\n    await f()\n", files) == set()
    assert _scan("async def h(request):\n    await request.json()\n", files) == set()
    assert _scan("async def h(client):\n    await client.get('u')\n", files) == set()


def test_name_defined_both_ways_is_skipped():
    src = "def f(): pass\nasync def f(): pass\nasync def h():\n    await f()\n"
    assert _scan(src) == set()


def test_await_self_method():
    sync_m = "class C:\n    def m(self): pass\n    async def h(self):\n        await self.m()\n"
    async_m = "class C:\n    async def m(self): pass\n    async def h(self):\n        await self.m()\n"
    assert _scan(sync_m) == {("routers/h.py", "h", "await-sync", "self.m")}
    assert _scan(async_m) == set()


def test_await_module_alias_function():
    files = {"services/llm.py": "def f():\n    return 1\n"}
    src = "from services import llm\nasync def h():\n    await llm.f()\n"
    assert _scan(src, files) == {("routers/h.py", "h", "await-sync", "services.llm.f")}


def test_relative_import_resolves():
    files = {"services/x.py": "def f():\n    return 1\n"}
    src = "from .x import f\nasync def h():\n    await f()\n"
    assert _scan(src, files, rel="services/y.py") == {("services/y.py", "h", "await-sync", "services.x.f")}


def test_async_ok_comment_suppresses():
    assert _scan("async def h():\n    get_session()  # async-ok: tiny read at startup\n") == set()
    assert _scan("async def h():\n    get_session()  # async-ok:\n") != set()


# --- repository gate ---------------------------------------------------------

# Findings at implementation time (2026-10-19, 57ffb85). This set can only shrink: fix the call
# (asyncio.to_thread, a plain def route) or mark a justified one with `# async-ok: reason`.
BASELINE: frozenset[Finding] = frozenset({
    ('services/alerts_service.py', '_poll_once', 'blocking-call', 'helpers.get_session'),
    ('services/alerts_service.py', 'send_apns', 'blocking-call', 'helpers.get_session'),
    ('services/news_harvester.py', 'harvest_news', 'blocking-call', 'database.get_session'),
    ('services/pkscreener_runner.py', 'run_nightly_screen', 'blocking-call', 'database.get_session'),
    ('services/portfolio_snapshot.py', 'pregen_morning_briefs_all_users', 'blocking-call', 'database.get_session'),
    ('services/portfolio_snapshot.py', 'pregen_morning_briefs_all_users', 'blocking-call', 'yfinance.Ticker'),
    ('services/portfolio_snapshot.py', 'snapshot_all_users', 'blocking-call', 'database.get_session'),
    ('services/portfolio_snapshot.py', 'snapshot_all_users', 'blocking-call', 'yfinance.Ticker'),
    ('services/sentiment_engine.py', 'backfill_existing_articles', 'blocking-call', 'database.get_session'),
    ('services/youtube_harvester.py', 'harvest_portfolio_videos', 'blocking-call', 'database.get_session'),
    ('services/youtube_harvester.py', 'harvest_youtube_metadata', 'blocking-call', 'database.get_session'),
})


def test_no_new_violations():
    found = scan_files(load_backend(), in_scan_set)
    new = sorted(found - BASELINE)
    assert not new, f"new blocking calls / awaits on sync functions in async code: {new}"


def test_baseline_not_stale():
    found = scan_files(load_backend(), in_scan_set)
    stale = sorted(BASELINE - found)
    assert not stale, f"baseline entries that no longer occur (delete them): {stale}"
