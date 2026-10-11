"""Model artefacts, manifests, the active registry, the trial ledger and the lockbox log (spec 3.7, 4.3, 5.1).

Layout under ``$RESEARCH_DATA_DIR/models``::

    {model_id}/booster_s{seed}.txt  calibrator.json  manifest.json
    {model_id}/gate_result.json  validation.json  validation.md
    registry.json        active artefact per horizon, plus promotion history
    TRIALS.jsonl         one row per distinct store trial
    TRIALS_DEV.jsonl     --fast, --null-calibration and local_csv runs
    LOCKBOX_LOG.jsonl    one row per lockbox opening (procedure, horizon)
    LOCKBOX_LOG_DEV.jsonl  openings from dev runs (never spend the real lockbox)
    lockbox/{procedure_id}-h{h}[-dev].json  the recorded result of that opening

``manifest.json`` binds every artefact file by sha256 together with the
feature list, objective, parameters, config/git/data hashes, the gate result
and the ``fast`` flag. ``verify`` refuses a tampered file, a feature or
objective mismatch, and a fast artefact unless ``allow_fast``. Promotion never
happens automatically; it is the operator's CLI call::

    python -m research.registry promote --model-id ID [--allow-fast] [--data-dir D]
    python -m research.registry verify (--model-id ID | --active) [--allow-fast] [--data-dir D]

Both exit non-zero on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb

from . import config
from .features import FEATURE_VERSION, FEATURES
from .models.calibration import CohortCalibrator

MANIFEST = "manifest.json"
REQUIRED_FILES = ("calibrator.json", "gate_result.json", "validation.json")
TRIAL_KEY = ("procedure_id", "horizon", "scorer_id", "config_sha256", "data_sha256")


class ArtefactError(Exception):
    """An artefact failed verification; ``problems`` lists every reason."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


# ── paths and small io helpers ──────────────────────────────────────────────


def models_dir(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir or config.DATA_DIR) / "models"


def model_dir(model_id: str, data_dir: str | Path | None = None) -> Path:
    if not model_id or "/" in model_id or model_id.startswith("."):
        raise ValueError(f"invalid model_id {model_id!r}")
    return models_dir(data_dir) / model_id


def booster_name(seed: int) -> str:
    return f"booster_s{seed}.txt"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Stable bytes for hashing and for files that must be byte-identical across runs."""
    return (json.dumps(obj, indent=2, sort_keys=False, allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── manifest ────────────────────────────────────────────────────────────────


def write_manifest(mdir: Path, fields: Mapping[str, Any]) -> str:
    """Hash every artefact file in ``mdir`` into ``manifest.json``; return the manifest sha256.

    ``fields`` must include ``seeds``; the booster files for those seeds and
    ``REQUIRED_FILES`` must already exist.
    """
    names = [booster_name(int(s)) for s in fields["seeds"]] + list(REQUIRED_FILES)
    if (mdir / "validation.md").exists():
        names.append("validation.md")
    missing = [n for n in names if not (mdir / n).exists()]
    if missing:
        raise ArtefactError([f"missing file {n}" for n in missing])
    manifest = {**fields, "files": {n: sha256_file(mdir / n) for n in names}}
    data = canonical_json(manifest)
    write_atomic(mdir / MANIFEST, data)
    return hashlib.sha256(data).hexdigest()


def _booster_header(text: str) -> dict[str, str]:
    """``key=value`` lines of a LightGBM model file before the first tree."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("Tree="):
            break
        if "=" in line:
            k, v = line.split("=", 1)
            out.setdefault(k.strip(), v.strip())
    return out


def verify(mdir: Path, *, allow_fast: bool = False) -> tuple[dict[str, Any], str]:
    """Check one artefact directory; return ``(manifest, manifest_sha256)`` or raise ArtefactError."""
    path = mdir / MANIFEST
    if not path.exists():
        raise ArtefactError([f"{MANIFEST} missing in {mdir.name}"])
    raw = path.read_bytes()
    try:
        manifest = json.loads(raw)
    except ValueError as exc:
        raise ArtefactError([f"{MANIFEST} is not valid JSON: {exc}"]) from exc
    if not isinstance(manifest, dict):
        raise ArtefactError([f"{MANIFEST} is not an object"])

    problems: list[str] = []
    if manifest.get("fast") is not False and not allow_fast:
        problems.append("fast artefact refused without --allow-fast")
    objective = config.LGBM_PARAMS["objective"]
    if manifest.get("objective") != objective:
        problems.append(f"objective mismatch: {manifest.get('objective')!r} != {objective!r}")
    if manifest.get("features") != list(FEATURES):
        problems.append("feature list mismatch")
    if manifest.get("feature_version") != FEATURE_VERSION:
        problems.append(f"feature_version mismatch: {manifest.get('feature_version')!r}")
    if manifest.get("procedure_id") != config.PROCEDURE_ID:
        problems.append(f"procedure_id mismatch: {manifest.get('procedure_id')!r}")

    files = manifest.get("files")
    seeds = manifest.get("seeds")
    if not isinstance(files, dict) or not isinstance(seeds, list) or not seeds:
        problems.append("manifest lacks files or seeds")
        raise ArtefactError(problems)
    for name in [booster_name(int(s)) for s in seeds] + list(REQUIRED_FILES):
        if name not in files:
            problems.append(f"manifest does not bind {name}")
    for name, expected in files.items():
        f = mdir / str(name)
        if "/" in str(name) or not f.is_file():
            problems.append(f"missing file {name}")
        elif sha256_file(f) != expected:
            problems.append(f"sha256 mismatch for {name}")
    for s in seeds:
        f = mdir / booster_name(int(s))
        if not f.is_file():
            continue
        head = _booster_header(f.read_text(encoding="utf-8", errors="replace"))
        if head.get("objective", "").split(" ")[0] != objective:
            problems.append(f"objective mismatch in {f.name}: {head.get('objective')!r}")
        if head.get("feature_names", "").split(" ") != list(FEATURES):
            problems.append(f"feature list mismatch in {f.name}")
    if problems:
        raise ArtefactError(problems)
    return manifest, hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Artefact:
    """A verified, loaded artefact for one horizon."""

    model_id: str
    horizon: int
    manifest: dict[str, Any]
    manifest_sha256: str
    boosters: list[lgb.Booster]
    calibrator: CohortCalibrator
    gate_result: dict[str, Any]

    @property
    def tier(self) -> str:
        return str(self.gate_result.get("tier", "no_reliable_edge"))


def load_artefact(mdir: Path, *, allow_fast: bool = False, expected_sha256: str | None = None) -> Artefact:
    """Verify then load boosters, calibrator and gate result."""
    manifest, sha = verify(mdir, allow_fast=allow_fast)
    if expected_sha256 is not None and sha != expected_sha256:
        raise ArtefactError([f"manifest sha256 differs from the registry for {mdir.name}"])
    boosters = [lgb.Booster(model_file=str(mdir / booster_name(int(s)))) for s in manifest["seeds"]]
    calibrator = CohortCalibrator.from_json(json.loads((mdir / "calibrator.json").read_text(encoding="utf-8")))
    gate_result = json.loads((mdir / "gate_result.json").read_text(encoding="utf-8"))
    return Artefact(
        model_id=str(manifest.get("model_id", mdir.name)),
        horizon=int(manifest["horizon"]),
        manifest=manifest,
        manifest_sha256=sha,
        boosters=boosters,
        calibrator=calibrator,
        gate_result=gate_result,
    )


# ── registry.json ───────────────────────────────────────────────────────────


def read_registry(data_dir: str | Path | None = None) -> dict[str, Any]:
    path = models_dir(data_dir) / "registry.json"
    if not path.exists():
        return {"active": {}, "history": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("active", {})
    data.setdefault("history", [])
    return data


def promote(model_id: str, *, data_dir: str | Path | None = None, allow_fast: bool = False) -> dict[str, Any]:
    """Verify ``model_id`` and make it the active artefact for its horizon (operator action)."""
    mdir = model_dir(model_id, data_dir)
    manifest, sha = verify(mdir, allow_fast=allow_fast)
    entry = {
        "model_id": model_id,
        "horizon": int(manifest["horizon"]),
        "manifest_sha256": sha,
        "fast": bool(manifest.get("fast")),
        "allow_fast": bool(allow_fast),
        "tier": (manifest.get("gate_result") or {}).get("tier"),
        "promoted_at": _now(),
    }
    reg = read_registry(data_dir)
    reg["active"][str(entry["horizon"])] = entry
    reg["history"].append(entry)
    write_atomic(models_dir(data_dir) / "registry.json", canonical_json(reg))
    return entry


def load_active(horizon: int, data_dir: str | Path | None = None) -> Artefact:
    """The promoted artefact for ``horizon``, re-verified against its recorded manifest sha256."""
    entry = read_registry(data_dir)["active"].get(str(horizon))
    if not entry:
        raise ArtefactError([f"no active artefact for horizon {horizon}"])
    art = load_artefact(
        model_dir(str(entry["model_id"]), data_dir),
        allow_fast=bool(entry.get("allow_fast")),
        expected_sha256=str(entry["manifest_sha256"]),
    )
    if art.horizon != horizon:
        raise ArtefactError([f"artefact {art.model_id} is for horizon {art.horizon}, not {horizon}"])
    return art


# ── trial ledger ────────────────────────────────────────────────────────────


def trials_path(data_dir: str | Path | None = None, *, dev: bool) -> Path:
    return models_dir(data_dir) / ("TRIALS_DEV.jsonl" if dev else "TRIALS.jsonl")


def trial_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(row[k] for k in TRIAL_KEY)


def trial_id(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(list(trial_key(row)), separators=(",", ":")).encode()).hexdigest()[:16]


def read_trials(data_dir: str | Path | None = None, *, dev: bool, horizon: int | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(trials_path(data_dir, dev=dev))
    return [r for r in rows if horizon is None or int(r.get("horizon", -1)) == horizon]


def append_trial(row: Mapping[str, Any], *, dev: bool, data_dir: str | Path | None = None) -> bool:
    """Append one trial unless its (procedure_id, horizon, scorer_id, config_sha256, data_sha256) exists.

    Store runs go to TRIALS.jsonl; ``dev`` runs (``--fast``, ``--null-calibration``,
    ``local_csv``) go to TRIALS_DEV.jsonl. Returns True when a row was written.
    """
    missing = [k for k in TRIAL_KEY if k not in row]
    if missing:
        raise ValueError(f"trial row lacks {missing}")
    key = trial_key(row)
    if any(trial_key(r) == key for r in read_trials(data_dir, dev=dev)):
        return False
    full = {"trial_id": trial_id(row), **row}
    full.setdefault("created_at", _now())
    _append_jsonl(trials_path(data_dir, dev=dev), full)
    return True


def distinct_trials(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One row per trial key (the first wins), sorted by trial_id for order-free statistics."""
    seen: dict[tuple[Any, ...], dict[str, Any]] = {}
    for r in rows:
        seen.setdefault(trial_key(r), dict(r))
    return sorted(seen.values(), key=lambda r: trial_id(r))


# ── lockbox log ─────────────────────────────────────────────────────────────


LOCKBOX_FIELDS = ("procedure_id", "horizon", "config_sha256", "git_sha", "data_sha256", "opened_at", "result_sha256")


def lockbox_path(data_dir: str | Path | None = None, *, dev: bool = False) -> Path:
    """LOCKBOX_LOG.jsonl, or LOCKBOX_LOG_DEV.jsonl for dev runs so they never spend the real lockbox."""
    return models_dir(data_dir) / ("LOCKBOX_LOG_DEV.jsonl" if dev else "LOCKBOX_LOG.jsonl")


def lockbox_result_path(procedure_id: str, horizon: int, data_dir: str | Path | None = None, *,
                        dev: bool = False) -> Path:
    return models_dir(data_dir) / "lockbox" / f"{procedure_id}-h{horizon}{'-dev' if dev else ''}.json"


def lockbox_opened(procedure_id: str, horizon: int, data_dir: str | Path | None = None, *,
                   dev: bool = False) -> dict[str, Any] | None:
    for r in _read_jsonl(lockbox_path(data_dir, dev=dev)):
        if r.get("procedure_id") == procedure_id and int(r.get("horizon", -1)) == horizon:
            return r
    return None


def append_lockbox(row: Mapping[str, Any], data_dir: str | Path | None = None, *, dev: bool = False,
                   result: Mapping[str, Any] | None = None) -> None:
    """Record one opening, then its result block (never overwritten); refuses a second opening.

    The result file holds ``{"opened_at", "result"}``; ``row["result_sha256"]``
    must be the sha256 of ``canonical_json(result)``.
    """
    missing = [k for k in LOCKBOX_FIELDS if k not in row]
    if missing:
        raise ValueError(f"lockbox row lacks {missing}")
    proc, h = str(row["procedure_id"]), int(row["horizon"])
    if lockbox_opened(proc, h, data_dir, dev=dev) is not None:
        raise PermissionError(f"lockbox already opened for {proc} h={h}")
    if result is not None and hashlib.sha256(canonical_json(result)).hexdigest() != row["result_sha256"]:
        raise ValueError("result_sha256 does not match the lockbox result")
    _append_jsonl(lockbox_path(data_dir, dev=dev), {k: row[k] for k in LOCKBOX_FIELDS})  # logged first
    if result is not None:
        path = lockbox_result_path(proc, h, data_dir, dev=dev)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as fh:  # exclusive create: a recorded result is never overwritten
            fh.write(canonical_json({"opened_at": row["opened_at"], "result": result}))
            fh.flush()
            os.fsync(fh.fileno())


def recorded_lockbox(procedure_id: str, horizon: int, data_dir: str | Path | None = None, *,
                     dev: bool = False) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """``(log row, result block)`` of the one recorded opening, or None if never opened.

    Raises ArtefactError when the opening is logged but its result file is
    missing, unreadable, or does not hash to the logged ``result_sha256``.
    """
    row = lockbox_opened(procedure_id, horizon, data_dir, dev=dev)
    if row is None:
        return None
    path = lockbox_result_path(procedure_id, horizon, data_dir, dev=dev)
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
        result = rec["result"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ArtefactError([f"recorded lockbox result unreadable for {procedure_id} h={horizon}: {exc}"]) from exc
    if (not isinstance(result, dict) or rec.get("opened_at") != row.get("opened_at")
            or hashlib.sha256(canonical_json(result)).hexdigest() != row.get("result_sha256")):
        raise ArtefactError([f"recorded lockbox result does not match LOCKBOX_LOG for {procedure_id} h={horizon}"])
    return row, result


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m research.registry", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("promote", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--data-dir", default=None)
        p.add_argument("--allow-fast", action="store_true")
        if name == "promote":
            p.add_argument("--model-id", required=True)
        else:
            g = p.add_mutually_exclusive_group(required=True)
            g.add_argument("--model-id")
            g.add_argument("--active", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "promote":
            entry = promote(args.model_id, data_dir=args.data_dir, allow_fast=args.allow_fast)
            print(json.dumps(entry, sort_keys=True))
        elif args.active:
            active = read_registry(args.data_dir)["active"]
            if not active:
                raise ArtefactError(["no active artefacts"])
            for h in sorted(active, key=int):
                art = load_active(int(h), args.data_dir)
                print(f"ok h={h} {art.model_id} {art.manifest_sha256}")
        else:
            _, sha = verify(model_dir(args.model_id, args.data_dir), allow_fast=args.allow_fast)
            print(f"ok {args.model_id} {sha}")
    except (ArtefactError, ValueError, OSError) as exc:
        print(f"verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
