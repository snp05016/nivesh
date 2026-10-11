"""``validation.json`` to admin markdown (spec 5.8; ML-25, GH-626, GH-697).

The renderer reads only the JSON it is given: every number it prints is a
value from that JSON. It prints PASSED only for a gate criterion whose
``passed`` is exactly ``true``, writes no verdict prose, never emits a literal
backslash-n, and refuses to render without the COVID stress window slice.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

STRESS_WINDOW = "covid_2020_02_06"

_HEADER_KEYS = (
    "procedure_id", "horizon", "config_sha256", "git_sha", "data_sha256", "universe_quality",
    "oos_period", "lockbox_period", "lockbox_opened_at", "lockbox_spent", "n_dates", "avg_universe_n",
)
_KV_SECTIONS = (
    ("rank_ic", "Rank IC, out-of-sample daily"),
    ("vs_best_baseline", "Versus the best baseline (paired HAC t)"),
    ("hit_rate_directional", "Directional hit rate"),
    ("portfolio", "Portfolio: mean monthly active returns in percent, net of estimated costs, before tax"),
    ("probability", "Probability"),
    ("overfitting", "Overfitting"),
    ("lockbox", "Lockbox (one shot, spent)"),
    ("data_checks", "Data checks"),
)
_TAIL_KEYS = ("gates", "tier", "reason_codes", "probability_display_passed", "slices", "baselines", "horizon")


def _cell(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return format(v, ".6g") if math.isfinite(v) else "n/a"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_cell(x) for x in v) + "]"
    if isinstance(v, Mapping):
        return "; ".join(f"{k}: {_cell(x)}" for k, x in v.items())
    text = str(v).replace("\\n", " ").replace("\r", " ").replace("\n", " ")
    return text.replace("|", "/")


def _table(header: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def _kv(block: Mapping[str, Any], skip: tuple[str, ...] = ()) -> list[str]:
    return _table(["Field", "Value"], [[k, v] for k, v in block.items() if k not in skip])


def _nested(block: Mapping[str, Any], key_name: str) -> list[str]:
    """A {name: {field: value}} block as one table (scalars get a 'value' column)."""
    fields: list[str] = []
    for v in block.values():
        for f in v.keys() if isinstance(v, Mapping) else ["value"]:
            if f not in fields:
                fields.append(f)
    rows = [
        [name, *([v.get(f) for f in fields] if isinstance(v, Mapping) else [v])]
        for name, v in block.items()
    ]
    return _table([key_name, *fields], rows)


def render_markdown(validation_json: Mapping[str, Any]) -> str:
    """Render ``validation.json`` as markdown. Raises ValueError without the stress window."""
    vj = validation_json
    slices = vj.get("slices")
    if not isinstance(slices, Mapping) or not slices.get(STRESS_WINDOW):
        raise ValueError(f"validation.json lacks the {STRESS_WINDOW} stress window slice")
    if not isinstance(vj.get("gates"), list):
        raise ValueError("validation.json lacks the gates list")

    lines = [f"# Validation report: {_cell(vj.get('procedure_id'))}, horizon {_cell(vj.get('horizon'))} sessions", ""]
    lines += _kv({k: vj.get(k) for k in _HEADER_KEYS}) + [""]

    for key, title in _KV_SECTIONS:
        block = vj.get(key)
        if not isinstance(block, Mapping):
            continue
        lines += [f"## {title}", ""]
        lines += _kv(block, skip=("by_year", "auc_by_year")) + [""]
        for sub in ("by_year", "auc_by_year"):
            if isinstance(block.get(sub), Mapping) and block[sub]:
                lines += [f"### {sub}", ""] + _nested(block[sub], "year") + [""]
        if key == "rank_ic" and isinstance(vj.get("baselines"), Mapping):
            lines += ["## Baselines", ""] + _nested(vj["baselines"], "baseline") + [""]

    lines += ["## Slices", ""]
    for name, block in slices.items():
        lines += [f"### {_cell(name)}", ""]
        if isinstance(block, Mapping) and all(isinstance(v, Mapping) for v in block.values()):
            lines += _nested(block, "slice")
        elif isinstance(block, Mapping):
            lines += _kv(block)
        else:
            lines += _kv({"value": block})
        lines.append("")

    lines += ["## Gates", ""]
    lines += _table(
        ["Gate", "Level", "Metric", "Value", "Rule", "Threshold", "Status"],
        [
            [g.get("id"), g.get("level"), g.get("metric"), g.get("value"), g.get("op"), g.get("threshold"),
             "PASSED" if g.get("passed") is True else "FAILED"]
            for g in vj["gates"]
            if isinstance(g, Mapping)
        ],
    )
    lines += ["", "## Tier", ""]
    lines += _kv({k: vj.get(k) for k in ("tier", "reason_codes", "probability_display_passed") if k in vj})

    known = set(_HEADER_KEYS) | {k for k, _ in _KV_SECTIONS} | set(_TAIL_KEYS)
    other = {k: v for k, v in vj.items() if k not in known}
    if other:
        lines += ["", "## Other fields", ""] + _kv(other)

    text = "\n".join(lines) + "\n"
    if "\\n" in text:  # defence in depth: _cell already strips them
        raise ValueError("rendered report contains a literal backslash-n")
    return text
