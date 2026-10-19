"""Nivesh FDL: a small, typed, point-in-time-safe feature definition language.

A program is a list of ``name = expr`` lines. It is parsed with :mod:`ast`
(never evaluated), checked against a declared input schema, hash-consed into a
DAG shared by every definition, and run by a vectorised pandas executor.

Grammar (a strict subset of Python expressions)::

    program := (NAME "=" expr)*                 one definition per statement
    expr    := expr ("+" | "-" | "*" | "/" | "**") expr
             | ("-" | "+") expr
             | expr ("<" | "<=" | ">" | ">=" | "==" | "!=") expr   -> 1.0 / 0.0
             | OP "(" expr | INT | NUMBER, ... ")"                  whitelisted ops only
             | NAME                              schema field or an earlier definition
             | NUMBER

Ops: ``where(c,a,b)``, ``abs log sqrt sign``, ``clip(x,lo,hi)``; per entity
over the panel calendar ``lag(x,n) diff(x,n) mean std min max sum (x,n)
ewm(x,span) zscore(x,n) corr(x,y,n)``; per date ``rank(x)`` (pct),
``demean(x)``, ``cs_zscore(x)``. Window/lag arguments are integer literals in
[1, 756] ([2, 756] for std/zscore/corr).

Time model. Every value is stamped with the half-session *slot* at which it is
known, relative to the row's bar date t: slot 2k is the open of t+k and 2k+1
the close of t+k. A base field's slot is its ``available`` point plus
``2 * available_lag``; ``lag(x, n)`` moves it 2n slots earlier; every other op
takes the max over its inputs. An output whose slot is after the decision time
(the close of t by default) is rejected, as is any reference to a
``future=True`` field (labels).

Values. Everything is float64. A cell exists only where the panel has a row:
cross-sectional ops see only same-date rows, time-series ops look only
backwards, and non-finite results (x/0, log(0)) become NaN. A window with any
NaN gives NaN (no coverage rule, no fill). Each node is NaN until the entity
has ``warmup`` bars, so ``run`` on a panel truncated at T reproduces every
row <= T of the full run exactly.
"""
from __future__ import annotations

import ast
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["FDLError", "Node", "Program", "compile_program", "panel_schema"]

MAX_WINDOW = 756
MAX_SOURCE_CHARS = 100_000
_SLOT = {"open": 0, "close": 1, "next_open": 2}
_DECISION = {"open": 0, "close": 1}
_DTYPES = {"float", "int", "bool"}

_BINOPS: dict[type[ast.operator], str] = {
    ast.Add: "add", ast.Sub: "sub", ast.Mult: "mul", ast.Div: "div", ast.Pow: "pow",
}
_CMPOPS: dict[type[ast.cmpop], str] = {
    ast.Lt: "lt", ast.LtE: "le", ast.Gt: "gt", ast.GtE: "ge", ast.Eq: "eq", ast.NotEq: "ne",
}
_COMMUTATIVE = {"add", "mul", "eq", "ne"}  # exact in IEEE arithmetic, so args are sorted
# Signatures: "x" an expression, "n" a window literal, "c" a numeric literal.
_FUNCS: dict[str, tuple[str, ...]] = {
    "where": ("x", "x", "x"), "clip": ("x", "c", "c"),
    "abs": ("x",), "log": ("x",), "sqrt": ("x",), "sign": ("x",),
    "lag": ("x", "n"), "diff": ("x", "n"),
    "mean": ("x", "n"), "std": ("x", "n"), "min": ("x", "n"), "max": ("x", "n"), "sum": ("x", "n"),
    "ewm": ("x", "n"), "zscore": ("x", "n"), "corr": ("x", "x", "n"),
    "rank": ("x",), "demean": ("x",), "cs_zscore": ("x",),
}
_MIN_WINDOW = {"std": 2, "zscore": 2, "corr": 2}
_ROLLING = {"mean", "std", "min", "max", "sum", "ewm", "zscore", "corr"}


class FDLError(ValueError):
    """A rejected program or schema; ``line``/``col`` are 1-based (0 = whole program)."""

    def __init__(self, line: int, col: int, message: str) -> None:
        super().__init__(f"line {line}, col {col}: {message}")
        self.line, self.col, self.message = line, col, message


@dataclass(frozen=True)
class Node:
    """One hash-consed DAG node. ``id`` is its topological position."""

    id: int
    op: str
    args: tuple[int, ...]
    params: tuple[float | int | str, ...]
    digest: str
    warmup: int  # bars of entity history needed before the value can be non-NaN
    avail: int | None  # slot at which the value is known (None: a constant)
    lineage: frozenset[str]


def panel_schema() -> dict[str, dict[str, object]]:
    """Schema of the numeric ``research.marketdata.store.PANEL_COLUMNS`` (fresh copy)."""
    at_close = ("high", "low", "close", "volume", "turnover_inr", "trades", "px_idx")
    out: dict[str, dict[str, object]] = {f: {"dtype": "float", "available": "close"} for f in at_close}
    out["open"] = {"dtype": "float", "available": "open"}
    out["prev_close"] = {"dtype": "float", "available": "open"}
    return out


def _describe(slot: int) -> str:
    day, phase = divmod(slot, 2)
    return f"{'close' if phase else 'open'} of t{day:+d}" if day else f"{'close' if phase else 'open'} of t"


def _check_schema(schema: Mapping[str, Mapping[str, object]]) -> dict[str, tuple[int, bool]]:
    """Validate the schema; return field -> (availability slot, is_future)."""
    out: dict[str, tuple[int, bool]] = {}
    for name, spec in schema.items():
        if not name.isidentifier():
            raise FDLError(0, 0, f"schema field {name!r} is not an identifier")
        dtype, avail = spec.get("dtype", "float"), spec.get("available", "close")
        lag, future = spec.get("available_lag", 0), spec.get("future", False)
        if dtype not in _DTYPES:
            raise FDLError(0, 0, f"schema field {name!r}: dtype {dtype!r} not in {sorted(_DTYPES)}")
        if avail not in _SLOT:
            raise FDLError(0, 0, f"schema field {name!r}: available {avail!r} not in {sorted(_SLOT)}")
        if not isinstance(lag, int) or isinstance(lag, bool) or lag < 0:
            raise FDLError(0, 0, f"schema field {name!r}: available_lag must be an int >= 0, got {lag!r}")
        out[name] = (_SLOT[str(avail)] + 2 * lag, bool(future))
    return out


class _Builder:
    """Turns AST expressions into hash-consed nodes, checking names, ops and windows."""

    def __init__(self, fields: dict[str, tuple[int, bool]], later: dict[str, int]) -> None:
        self.fields, self.later = fields, later
        self.nodes: list[Node] = []
        self.by_digest: dict[str, int] = {}
        self.env: dict[str, int] = {}

    def intern(self, op: str, args: tuple[int, ...], params: tuple[float | int | str, ...]) -> int:
        """Return the id of the node (op, args, params), creating it only if new (CSE)."""
        if op in _COMMUTATIVE:
            args = tuple(sorted(args, key=lambda a: self.nodes[a].digest))
        kids = [self.nodes[a] for a in args]
        blob = json.dumps([op, list(params), [k.digest for k in kids]])
        digest = hashlib.sha256(blob.encode()).hexdigest()
        if digest in self.by_digest:
            return self.by_digest[digest]
        if op == "field":
            name = str(params[0])
            warmup, avail, lineage = 1, self.fields[name][0], frozenset({name})
        elif op == "const":
            warmup, avail, lineage = 0, None, frozenset()
        else:
            warmup = max(k.warmup for k in kids)
            slots = [k.avail for k in kids if k.avail is not None]
            avail = max(slots) if slots else None
            lineage = frozenset().union(*(k.lineage for k in kids))
            n = int(params[0]) if params else 0
            if op in ("lag", "diff"):
                warmup += n
            elif op in _ROLLING:
                warmup += n - 1
            if op == "lag" and avail is not None:
                avail -= 2 * n
        node = Node(len(self.nodes), op, args, params, digest, warmup, avail, lineage)
        self.nodes.append(node)
        self.by_digest[digest] = node.id
        return node.id

    def expr(self, e: ast.expr) -> int:
        """Compile one expression node."""
        if isinstance(e, ast.Constant):
            return self.intern("const", (), (_number(e),))
        if isinstance(e, ast.Name):
            return self.name(e)
        if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)):
            if isinstance(e.operand, ast.Constant):
                return self.intern("const", (), (_number(e),))
            inner = self.expr(e.operand)
            return self.intern("neg", (inner,), ()) if isinstance(e.op, ast.USub) else inner
        if isinstance(e, ast.BinOp) and type(e.op) in _BINOPS:
            return self.intern(_BINOPS[type(e.op)], (self.expr(e.left), self.expr(e.right)), ())
        if isinstance(e, ast.Compare):
            if len(e.ops) != 1 or type(e.ops[0]) not in _CMPOPS:
                raise _err(e, "only single comparisons with < <= > >= == != are allowed")
            return self.intern(_CMPOPS[type(e.ops[0])], (self.expr(e.left), self.expr(e.comparators[0])), ())
        if isinstance(e, ast.Call):
            return self.call(e)
        raise _err(e, f"unsupported syntax: {type(e).__name__}")

    def name(self, e: ast.Name) -> int:
        """Resolve a name to an earlier definition or a schema field."""
        if e.id in self.env:
            return self.env[e.id]
        if e.id in self.fields:
            if self.fields[e.id][1]:
                raise _err(e, f"{e.id!r} is a future (label) field and can never be a feature input")
            return self.intern("field", (), (e.id,))
        if e.id in self.later:
            raise _err(e, f"{e.id!r} is used before its definition on line {self.later[e.id]}")
        raise _err(e, f"unknown name {e.id!r} (not a schema field or an earlier definition)")

    def call(self, e: ast.Call) -> int:
        """Compile a whitelisted function call."""
        if not isinstance(e.func, ast.Name):
            raise _err(e, "only plain calls to whitelisted ops are allowed")
        fn = e.func.id
        if fn not in _FUNCS:
            raise _err(e, f"unknown function {fn!r}; allowed: {', '.join(sorted(_FUNCS))}")
        if e.keywords:
            raise _err(e, f"{fn}() takes positional arguments only")
        sig = _FUNCS[fn]
        if len(e.args) != len(sig):
            raise _err(e, f"{fn}() takes {len(sig)} arguments, got {len(e.args)}")
        args: list[int] = []
        params: list[float | int | str] = []
        for kind, a in zip(sig, e.args):
            if kind == "x":
                args.append(self.expr(a))
            elif kind == "n":
                params.append(_window(a, fn, _MIN_WINDOW.get(fn, 1)))
            else:
                params.append(_number(a))
        if fn == "clip" and float(params[0]) > float(params[1]):
            raise _err(e, "clip() needs lo <= hi")
        return self.intern(fn, tuple(args), tuple(params))


def _err(e: ast.AST, message: str) -> FDLError:
    return FDLError(getattr(e, "lineno", 0), getattr(e, "col_offset", -1) + 1, message)


def _literal(e: ast.expr) -> object:
    """The value of a (possibly negated) literal, else None."""
    if isinstance(e, ast.Constant):
        return e.value
    if isinstance(e, ast.UnaryOp) and isinstance(e.op, (ast.USub, ast.UAdd)) and isinstance(e.operand, ast.Constant):
        v = e.operand.value
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return -v if isinstance(e.op, ast.USub) else v
    return None


def _number(e: ast.expr) -> float:
    v = _literal(e)
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise _err(e, "expected a numeric literal")
    return float(v)


def _window(e: ast.expr, fn: str, lo: int) -> int:
    v = _literal(e)
    if not isinstance(v, int) or isinstance(v, bool):
        raise _err(e, f"{fn}() window/lag must be an integer literal")
    if not lo <= v <= MAX_WINDOW:
        hint = " (lag 0 is not a lag; negative lags look ahead)" if fn == "lag" else ""
        raise _err(e, f"{fn}() window/lag must be in [{lo}, {MAX_WINDOW}], got {v}{hint}")
    return v


# ── executor ────────────────────────────────────────────────────────────────

def _roll(stat: str) -> Callable[[np.ndarray, int], np.ndarray]:
    def f(x: np.ndarray, n: int) -> np.ndarray:
        r = pd.DataFrame(x).rolling(n, min_periods=n)
        return np.asarray(getattr(r, stat)(), dtype=float)
    return f


def _cs(stat: str) -> Callable[[np.ndarray], np.ndarray]:
    def f(x: np.ndarray) -> np.ndarray:
        df = pd.DataFrame(x)
        if stat == "rank":
            return df.rank(axis=1, pct=True).to_numpy(float)
        out = df.sub(df.mean(axis=1), axis=0)
        return (out.div(df.std(axis=1), axis=0) if stat == "cs_zscore" else out).to_numpy(float)
    return f


def _cmp(fn: Callable[[np.ndarray, np.ndarray], np.ndarray]) -> Callable[[np.ndarray, np.ndarray], np.ndarray]:
    return lambda a, b: np.where(np.isnan(a) | np.isnan(b), np.nan, fn(a, b).astype(float))


def _zscore(x: np.ndarray, n: int) -> np.ndarray:
    return (x - _roll("mean")(x, n)) / _roll("std")(x, n)


def _corr(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    return pd.DataFrame(x).rolling(n, min_periods=n).corr(pd.DataFrame(y)).to_numpy(float)


def _lag(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full_like(x, np.nan)
    out[n:] = x[:-n]
    return out


_ELEMENTWISE: dict[str, Callable[..., np.ndarray]] = {
    "add": np.add, "sub": np.subtract, "mul": np.multiply, "div": np.divide, "pow": np.power,
    "neg": np.negative, "abs": np.abs, "log": np.log, "sqrt": np.sqrt, "sign": np.sign,
    "lt": _cmp(np.less), "le": _cmp(np.less_equal), "gt": _cmp(np.greater),
    "ge": _cmp(np.greater_equal), "eq": _cmp(np.equal), "ne": _cmp(np.not_equal),
    "where": lambda c, a, b: np.where(np.isnan(c), np.nan, np.where(c != 0, a, b)),
    "rank": _cs("rank"), "demean": _cs("demean"), "cs_zscore": _cs("cs_zscore"),
}
_TIMESERIES: dict[str, Callable[..., np.ndarray]] = {
    "lag": _lag, "diff": lambda x, n: x - _lag(x, n),
    "mean": _roll("mean"), "std": _roll("std"), "min": _roll("min"), "max": _roll("max"), "sum": _roll("sum"),
    "ewm": lambda x, n: pd.DataFrame(x).ewm(span=n, min_periods=n).mean().to_numpy(float),
    "zscore": _zscore, "corr": _corr,
}


@dataclass(frozen=True)
class Program:
    """A compiled FDL program: topologically ordered nodes plus named outputs."""

    nodes: tuple[Node, ...]
    outputs: dict[str, int]  # definition name -> node id, in definition order
    fingerprint: str
    decision: str

    def lineage(self, name: str) -> frozenset[str]:
        """Base schema fields the output ``name`` depends on."""
        return self.nodes[self.outputs[name]].lineage

    def warmup(self, name: str) -> int:
        """Bars of entity history needed before ``name`` can be non-NaN."""
        return self.nodes[self.outputs[name]].warmup

    def availability(self, name: str) -> str:
        """When ``name`` is known, relative to the bar date t (e.g. 'close of t')."""
        avail = self.nodes[self.outputs[name]].avail
        return "always (constant)" if avail is None else _describe(avail)

    def run(self, panel: pd.DataFrame, entity: str = "symbol") -> pd.DataFrame:
        """Evaluate every output; one row per panel row, sorted by (date, entity)."""
        fields = sorted({str(n.params[0]) for n in self.nodes if n.op == "field"})
        missing = [c for c in ("date", entity, *fields) if c not in panel.columns]
        if missing:
            raise KeyError(f"panel lacks columns {missing}")
        keys = panel[["date", entity]]
        if keys.duplicated().any():
            raise ValueError(f"panel has duplicate (date, {entity}) rows")
        dates = pd.Index(keys["date"].unique()).sort_values()
        ents = pd.Index(keys[entity].unique()).sort_values()
        ri, ci = dates.get_indexer(keys["date"]), ents.get_indexer(keys[entity])
        present = np.zeros((len(dates), len(ents)), dtype=bool)
        present[ri, ci] = True
        age = np.arange(len(dates))[:, None] - present.argmax(axis=0)[None, :] + 1
        vals: list[np.ndarray] = []
        with np.errstate(all="ignore"):
            for node in self.nodes:
                if node.op == "field":
                    out = np.full(present.shape, np.nan)
                    out[ri, ci] = panel[str(node.params[0])].to_numpy(dtype=float, na_value=np.nan)
                elif node.op == "const":
                    out = np.full(present.shape, float(node.params[0]))
                elif node.op == "clip":
                    out = np.clip(vals[node.args[0]], float(node.params[0]), float(node.params[1]))
                elif node.op in _TIMESERIES:
                    out = _TIMESERIES[node.op](*(vals[a] for a in node.args), int(node.params[0]))
                else:
                    out = _ELEMENTWISE[node.op](*(vals[a] for a in node.args))
                out = np.array(out, dtype=float)  # copy: pandas may hand back read-only views
                out[~np.isfinite(out) | ~present | (age < node.warmup)] = np.nan
                vals.append(out)
        res = pd.DataFrame({"date": dates[ri], entity: ents[ci]})
        for name, nid in self.outputs.items():
            res[name] = vals[nid][ri, ci]
        return res.sort_values(["date", entity], kind="stable").reset_index(drop=True)


def compile_program(
    src: str, schema: Mapping[str, Mapping[str, object]], decision: str = "close"
) -> Program:
    """Parse, type/availability-check and compile ``src`` into a :class:`Program`.

    ``schema`` maps field -> {"dtype", "available" (open|close|next_open),
    "available_lag" (sessions, default 0), "future" (default False)}.
    ``decision`` is when features are consumed: "close" (default) or "open" of t.
    """
    if decision not in _DECISION:
        raise FDLError(0, 0, f"decision must be one of {sorted(_DECISION)}")
    if len(src) > MAX_SOURCE_CHARS:
        raise FDLError(0, 0, f"program longer than {MAX_SOURCE_CHARS} characters")
    fields = _check_schema(schema)
    try:
        tree = ast.parse(src, mode="exec")
    except SyntaxError as exc:
        raise FDLError(exc.lineno or 0, exc.offset or 0, f"syntax error: {exc.msg}") from exc
    except RecursionError as exc:
        raise FDLError(0, 0, "program nested too deeply") from exc
    later = {
        t.id: s.lineno for s in tree.body if isinstance(s, ast.Assign) for t in s.targets if isinstance(t, ast.Name)
    }
    b = _Builder(fields, later)
    limit = _DECISION[decision]
    for stmt in tree.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name)):
            raise _err(stmt, "each line must be a single `name = expression` definition")
        name = stmt.targets[0].id
        if name in fields:
            raise _err(stmt, f"{name!r} shadows a schema field")
        if name in b.env:
            raise _err(stmt, f"{name!r} is already defined")
        try:
            nid = b.expr(stmt.value)
        except RecursionError as exc:
            raise _err(stmt, "expression nested too deeply") from exc
        node = b.nodes[nid]
        if node.avail is not None and node.avail > limit:
            late = sorted(f for f in node.lineage if fields[f][0] > limit)
            raise _err(stmt.value, (
                f"{name!r} is known at the {_describe(node.avail)} but decisions are made at the "
                f"{_describe(limit)}; late inputs: {', '.join(f'{f} ({_describe(fields[f][0])})' for f in late)}; "
                "wrap them in lag(x, k)"
            ))
        b.env[name] = nid
        del later[name]
    if not b.env:
        raise FDLError(0, 0, "empty program")
    canon = "\n".join(f"{k}={b.nodes[v].digest}" for k, v in sorted(b.env.items()))
    return Program(tuple(b.nodes), dict(b.env), hashlib.sha256(canon.encode()).hexdigest(), decision)
