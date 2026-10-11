#!/usr/bin/env python3
"""Print the backend HTTP route inventory as a markdown table.

Usage: route_inventory.py [<backend-root>]   (default: backend/ next to scripts/)

Static only: main.py and every router module are parsed with ast, never
imported, so it runs anywhere without backend dependencies. It follows the
`from X import Y [as Z]` bindings in main.py, each `app.include_router(...,
prefix=...)`, each `APIRouter(prefix=...)`, and the `@<router>.<method>(path)`
decorators, plus `@app.<method>` routes declared in main.py itself.

ponytail: only literal-string prefixes/paths and routers bound by a plain
`name = APIRouter(...)`; routes built dynamically (add_api_route, f-strings)
are not seen. Use app.routes on the server if that ever matters.
"""
import ast
import sys
from pathlib import Path

METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "websocket"}


def _str(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _kw(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            return _str(kw.value)
    return None


def _routes(tree: ast.Module, prefixes: dict[str, str], rel: str):
    """Yield (method, path, handler, source) for decorated functions."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name) and dec.func.attr in METHODS):
                continue
            var = dec.func.value.id
            if var not in prefixes:
                continue
            path = _str(dec.args[0]) if dec.args else _kw(dec, "path")
            if path is None:
                continue
            yield dec.func.attr.upper(), prefixes[var] + path, node.name, f"{rel}:{dec.lineno}"


def _router_prefixes(tree: ast.Module) -> dict[str, str]:
    out = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == "APIRouter"):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = _kw(node.value, "prefix") or ""
    return out


def inventory(root: Path):
    main = root / "main.py"
    tree = ast.parse(main.read_text(), str(main))
    rows = list(_routes(tree, {"app": ""}, "backend/main.py"))

    # local name -> (module file, router variable or None if the name is the module)
    bindings: dict[str, tuple[Path, str | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and not node.level:
            base = root.joinpath(*node.module.split("."))
            for alias in node.names:
                local = alias.asname or alias.name
                if (base / f"{alias.name}.py").is_file():
                    bindings[local] = (base / f"{alias.name}.py", None)
                elif base.with_suffix(".py").is_file():
                    bindings[local] = (base.with_suffix(".py"), alias.name)

    mounted: set[Path] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "include_router" and node.args):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name):
            local, var = arg.value.id, arg.attr
        elif isinstance(arg, ast.Name):
            local, var = arg.id, None
        else:
            continue
        if local not in bindings:
            continue
        path, bound_var = bindings[local]
        var = var if bound_var is None else bound_var
        if var is None:
            continue
        mounted.add(path)
        mod_tree = ast.parse(path.read_text(), str(path))
        prefixes = _router_prefixes(mod_tree)
        if var not in prefixes:
            continue
        outer = _kw(node, "prefix") or ""
        rel = path.relative_to(root.parent).as_posix()
        rows += _routes(mod_tree, {var: outer + prefixes[var]}, rel)

    unmounted = sorted(p.relative_to(root.parent).as_posix()
                       for p in (root / "routers").glob("*.py")
                       if p.name != "__init__.py" and p not in mounted)
    rows.sort(key=lambda r: (r[1], r[0], r[3]))
    return rows, unmounted


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "backend"
    rows, unmounted = inventory(root.resolve())
    print("| Method | Path | Handler | Source |")
    print("|---|---|---|---|")
    for method, path, handler, source in rows:
        print(f"| `{method}` | `{path or '/'}` | `{handler}` | `{source}` |")
    print()
    print(f"{len(rows)} routes.", end="")
    if unmounted:
        print(" Router modules not mounted in backend/main.py: "
              + ", ".join(f"`{u}`" for u in unmounted) + ".", end="")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
