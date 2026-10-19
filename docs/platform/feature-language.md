---
title: Feature Language (FDL)
description: Nivesh's small, typed, point-in-time-safe feature definition language - grammar, operations, time model, warm-up, CSE, fingerprints and errors.
---

# Feature Language (FDL)

<p class="nv-lede">A small, typed language for writing features. It is parsed with Python's <code>ast</code> and
<strong>never evaluated</strong>. It is checked against a declared schema, hash-consed into a shared DAG and run by a
vectorised pandas executor. A feature that would need information from after the decision time does not
compile. Source: <code>ml-engine/lab/featurelang.py</code>.</p>

## Grammar

A program is a list of `name = expr` lines, a strict subset of Python expressions:

```text
program := (NAME "=" expr)*                 one definition per statement
expr    := expr ("+" | "-" | "*" | "/" | "**") expr
         | ("-" | "+") expr
         | expr ("<" | "<=" | ">" | ">=" | "==" | "!=") expr   -> 1.0 / 0.0
         | OP "(" expr | INT | NUMBER, ... ")"                  whitelisted ops only
         | NAME                              schema field or an earlier definition
         | NUMBER
```

- Names refer to schema fields or **earlier** definitions. There are no forward references, no redefinition and no shadowing of fields.
- Calls are positional only and limited to the whitelist below. Attributes, subscripts, imports, lambdas and chained comparisons are rejected.
- Programs are limited to 100,000 characters. Very deep nesting is reported as an error, not a crash.

## Operations

| Kind | Op | Signature | Notes |
|---|---|---|---|
| Arithmetic | `+ - * / **`, unary `-` | `x op y` | `+` and `*` are commutative, so their arguments are sorted for CSE |
| Comparison | `< <= > >= == !=` | `x op y` | Returns 1.0 / 0.0, or NaN if either side is NaN |
| Element-wise | `where(c, a, b)` | x, x, x | `a` where `c ≠ 0`, else `b`; NaN where `c` is NaN |
| | `clip(x, lo, hi)` | x, c, c | Literal bounds with `lo ≤ hi` |
| | `abs log sqrt sign` | x | |
| Time series, per entity | `lag(x, n)` · `diff(x, n)` | x, n | `diff = x − lag(x, n)` |
| | `mean std min max sum (x, n)` | x, n | Rolling, needs a full window (`min_periods = n`) |
| | `ewm(x, span)` | x, n | Exponential mean, `min_periods = span` |
| | `zscore(x, n)` | x, n | `(x − mean(x,n)) / std(x,n)` |
| | `corr(x, y, n)` | x, x, n | Rolling correlation |
| Cross-section, per date | `rank(x)` | x | Percentile rank across same-date rows |
| | `demean(x)` · `cs_zscore(x)` | x | Same-date mean (and std) |

Window and lag arguments must be **integer literals** in [1, 756], or [2, 756] for `std`, `zscore` and `corr`.

## Input schema

`panel_schema()` exposes the numeric columns of the research panel:

| Field | Available at |
|---|---|
| `open`, `prev_close` | open of *t* |
| `high`, `low`, `close`, `volume`, `turnover_inr`, `trades`, `px_idx` | close of *t* |

A schema entry can also declare `available: next_open`, `available_lag: k` (sessions) and
`future: true` (labels). Labels can never be used as feature inputs.

## Time model: slots

Every value is stamped with the half-session **slot** at which it becomes known, relative to the row's
bar date *t*: slot \(2k\) is the open of \(t+k\) and slot \(2k+1\) is the close of \(t+k\).

\[
\text{slot}(\text{field}) = \text{slot}(\text{available}) + 2\cdot\text{available\_lag},\qquad
\text{slot}(\text{lag}(x,n)) = \text{slot}(x) - 2n,\qquad
\text{slot}(\text{op}(x_1..x_m)) = \max_i \text{slot}(x_i)
\]

An output whose slot is later than the decision time (by default the close of *t*, slot 1) is rejected.
The error names the late inputs and suggests `lag(x, k)`. With `decision="open"` the limit is slot 0,
so `close` cannot be used without a lag.

## Values, NaNs and warm-up

- Everything is float64. A cell exists only where the panel has a row.
- Cross-sectional ops see only same-date rows, and time-series ops look only backwards.
- Non-finite results (`x/0`, `log(0)`) become NaN. Any NaN in a window gives NaN: there is no coverage rule and no fill.
- **Warm-up:** a field needs 1 bar; `lag`/`diff` add \(n\); rolling ops add \(n-1\); other ops take the maximum of their inputs. A value stays NaN until the entity has that many bars of its own history.

!!! success "Truncation parity guarantee"
    Because of these rules, running a program on a panel truncated at date \(T\) reproduces every
    row \(\le T\) of the full run **exactly**. The Hypothesis Lab's Leakage Detector re-checks this on
    every experiment ([details](hypothesis-lab.md#9-leakage-parity-check)), and
    `test_truncation_parity` tests it directly.

## CSE and fingerprints

Each node's identity is `sha256([op, params, child digests])`. Building a node that already exists
returns the existing node, so shared subtrees are computed once across **all** definitions
(common-subexpression elimination). Arguments of commutative ops are sorted by digest first.

The program **fingerprint** is a SHA-256 over `name=digest` lines, sorted by name. It does not
change with whitespace, comments or the order of commutative arguments, and it changes whenever the
meaning changes. Experiments record it so that two runs of "the same idea" can be identified.

```python
compile_program("a=1+px_idx", schema).fingerprint == \
compile_program("a = px_idx + 1   # comment", schema).fingerprint   # True
```

## Examples

```python
ret_1    = px_idx / lag(px_idx, 1) - 1                       # (1)!
vol_20   = std(log(px_idx / lag(px_idx, 1)), 20)
mom_12_1 = lag(px_idx, 21) / lag(px_idx, 252) - 1            # (2)!
score    = cs_zscore(mom_12_1) - cs_zscore(vol_20)           # (3)!
gap      = open / lag(close, 1) - 1
```

1.  Warm-up 2 bars; known at the close of *t*.
2.  Known at the close of *t − 21*; warm-up 253 bars.
3.  Re-uses the `mom_12_1` and `vol_20` nodes (CSE). This program has 19 nodes in total.

`POST /lab/v1/features/compile` on this program returns, for each output:

| Output | Lineage | Warm-up bars | Availability |
|---|---|---|---|
| `ret_1` | `px_idx` | 2 | close of t |
| `vol_20` | `px_idx` | 21 | close of t |
| `mom_12_1` | `px_idx` | 253 | close of t-21 |
| `score` | `px_idx` | 253 | close of t |
| `gap` | `close`, `open` | 2 | open of t |

## Errors

Errors are `FDLError(line, col, message)` with 1-based positions. The API returns them as
`{ok: false, error, line, col}`. These were produced by the compiler:

| Source | Error |
|---|---|
| `x = lag(px_idx, 0)` | line 1, col 17: lag() window/lag must be in [1, 756], got 0 (lag 0 is not a lag; negative lags look ahead) |
| `x = std(close, 1)` | line 1, col 16: std() window/lag must be in [2, 756], got 1 |
| `x = mean(close, 1000)` | line 1, col 17: mean() window/lag must be in [1, 756], got 1000 |
| `x = foo(close)` | line 1, col 5: unknown function 'foo'; allowed: abs, clip, corr, cs_zscore, demean, diff, ewm, lag, log, max, mean, min, rank, sign, sqrt, std, sum, where, zscore |
| `x = close.shift(-1)` | line 1, col 5: only plain calls to whitelisted ops are allowed |
| `x = close[1]` | line 1, col 5: unsupported syntax: Subscript |
| `x = lag(close, n=5)` | line 1, col 5: lag() takes positional arguments only |
| `x = 1 < close < 2` | line 1, col 5: only single comparisons with < <= > >= == != are allowed |
| `x = clip(close, 5, 1)` | line 1, col 5: clip() needs lo <= hi |
| `x = y + 1` then `y = close` | line 1, col 5: 'y' is used before its definition on line 2 |
| `close = open` | line 1, col 1: 'close' shadows a schema field |
| `import os` | line 1, col 1: each line must be a single \`name = expression\` definition |
| `x = rank(fwd_ret)` (label field) | line 1, col 10: 'fwd_ret' is a future (label) field and can never be a feature input |
| `x = eps / close` (`eps` at next_open, lag 1) | line 1, col 5: 'x' is known at the open of t+2 but decisions are made at the close of t; late inputs: eps (open of t+2); wrap them in lag(x, k) |
| `x = close` with `decision="open"` | line 1, col 5: 'x' is known at the close of t but decisions are made at the open of t; late inputs: close (close of t); wrap them in lag(x, k) |

The last two rows are fixed by wrapping the late input in a lag: `x = lag(eps, 2) / close` compiles, and is known at the close of *t*.
