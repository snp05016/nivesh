"""Registry, trial ledger, lockbox and the walk-forward CLI (spec 4.3, 5.1, 11.1; package ml-models-registry).

The CLI tests run ``train --fast --source local_csv`` on ``RESEARCH_LOCAL_CSV``
(about 5 s each) in temporary data dirs; they skip when the CSV is absent.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from research import config, registry, train

needs_csv = pytest.mark.skipif(not config.LOCAL_CSV.exists(), reason="RESEARCH_LOCAL_CSV not available")
H = 21


def _train(data_dir: Path, *extra: str) -> int:
    return train.main(["--horizon", str(H), "--source", "local_csv", "--data-dir", str(data_dir), "--fast", *extra])


def _model_id(data_dir: Path) -> str:
    return next(p.name for p in (data_dir / "models").iterdir() if (p / "validation.json").exists())


@pytest.fixture(scope="module")
def fast_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Two identical fast runs (the second with --train-production) in one data dir."""
    if not config.LOCAL_CSV.exists():
        pytest.skip("RESEARCH_LOCAL_CSV not available")
    data_dir = tmp_path_factory.mktemp("fast")
    assert _train(data_dir) == 0
    mid = _model_id(data_dir)
    first = (data_dir / "models" / mid / "validation.json").read_bytes()
    assert _train(data_dir, "--train-production") == 0
    return {"data_dir": data_dir, "model_id": mid, "first_validation": first}


def _copy_artefact(fast_run: dict[str, Any], tmp_path: Path) -> Path:
    dst = tmp_path / "models" / fast_run["model_id"]
    shutil.copytree(registry.model_dir(fast_run["model_id"], fast_run["data_dir"]), dst)
    return dst


# ── determinism, validation outputs ─────────────────────────────────────────


@needs_csv
def test_fast_local_csv_is_byte_identical(fast_run: dict[str, Any]) -> None:
    mdir = registry.model_dir(fast_run["model_id"], fast_run["data_dir"])
    assert (mdir / "validation.json").read_bytes() == fast_run["first_validation"]
    vj = json.loads(fast_run["first_validation"])
    assert vj["fast"] is True and vj["lockbox_spent"] is True and vj["lockbox_opened_at"] is None
    assert vj["universe_quality"] == "survivorship_biased"
    assert vj["tier"] == "no_reliable_edge"
    assert vj["reason_codes"][:2] == ["survivorship_biased_universe", "gate_failed:G0"]
    assert vj["data_checks"]["manifest_verifies"] is False  # a local CSV has no hashed raw snapshot
    assert "\\n" not in (mdir / "validation.md").read_text(encoding="utf-8")
    gate = json.loads((mdir / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["tier"] == vj["tier"] and gate["gates"] == vj["gates"]


@needs_csv
def test_model_and_baselines_share_fold_hashes(tmp_path: Path) -> None:
    rc = train.RunConfig(horizon=H, source="local_csv", data_dir=tmp_path, fast=True)
    inputs = train.build_inputs(rc)
    folds = train._folds(inputs, rc)
    oos, hashes, _ = train.walk_forward(inputs, folds, rc)
    expected = [f.hash for f in folds]
    assert hashes[train.MODEL] == expected
    assert set(hashes) == {train.MODEL, "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"}
    assert all(v == expected for v in hashes.values())
    assert sorted(oos["k"].unique().tolist()) == [f.k for f in folds]


# ── trial ledger ────────────────────────────────────────────────────────────


def _trial(**over: Any) -> dict[str, Any]:
    row = {"procedure_id": config.PROCEDURE_ID, "horizon": H, "scorer_id": "lgbm", "config_sha256": "c" * 64,
           "git_sha": "abc", "data_sha256": "d" * 64, "metrics": {"mean_ic": 0.01},
           "monthly_net_active": [["2024-01-01", 0.01]]}
    row.update(over)
    return row


def test_store_trial_deduplicates_and_dev_routes_separately(tmp_path: Path) -> None:
    assert registry.append_trial(_trial(), dev=False, data_dir=tmp_path) is True
    assert registry.append_trial(_trial(git_sha="other", metrics={}), dev=False, data_dir=tmp_path) is False
    assert registry.append_trial(_trial(data_sha256="e" * 64), dev=False, data_dir=tmp_path) is True
    rows = registry.read_trials(tmp_path, dev=False)
    assert len(rows) == 2 and all(len(r["trial_id"]) == 16 and r["created_at"] for r in rows)
    assert not registry.trials_path(tmp_path, dev=True).exists()
    assert registry.append_trial(_trial(), dev=True, data_dir=tmp_path) is True
    assert len(registry.read_trials(tmp_path, dev=True)) == 1
    assert len(registry.read_trials(tmp_path, dev=False)) == 2
    with pytest.raises(ValueError):
        registry.append_trial({"procedure_id": "x"}, dev=False, data_dir=tmp_path)


def test_dev_routing_rules() -> None:
    assert train.RunConfig(horizon=H, source="store").dev is False
    assert train.RunConfig(horizon=H, source="store", fast=True).dev is True
    assert train.RunConfig(horizon=H, source="store", null_calibration=20).dev is True
    assert train.RunConfig(horizon=H, source="local_csv").dev is True


@needs_csv
def test_fast_run_appends_only_to_trials_dev(fast_run: dict[str, Any]) -> None:
    d = fast_run["data_dir"]
    assert not registry.trials_path(d, dev=False).exists()
    rows = registry.read_trials(d, dev=True)
    assert sorted(r["scorer_id"] for r in rows) == sorted(s + "+fast" for s in train.TRIAL_SCORERS)  # once, not twice
    assert all(r["monthly_net_active"] for r in rows)


@needs_csv
def test_null_calibration_appends_only_to_trials_dev(tmp_path: Path) -> None:
    assert _train(tmp_path, "--null-calibration", "1") == 0
    assert not registry.trials_path(tmp_path, dev=False).exists()
    rows = registry.read_trials(tmp_path, dev=True)
    assert [r["scorer_id"] for r in rows] == ["lgbm+null0"]
    out = json.loads(next((tmp_path / "models" / "null_calibration").glob("*.json")).read_text(encoding="utf-8"))
    assert out["replicates"] == 1 and out["results"][0]["tier"] == "no_reliable_edge" and out["passed"] is True


# ── lockbox ─────────────────────────────────────────────────────────────────


def _lockbox_view(vj: dict[str, Any]) -> dict[str, Any]:
    p = vj["probability"]
    return {"opened_at": vj["lockbox_opened_at"], "lockbox": vj["lockbox"],
            "prob": [p["bss_ci95_lockbox"], p["ece_lockbox"], p["n_eff_lockbox"]],
            "gates": [g for g in vj["gates"] if g.get("id") in ("G6", "P")]}


@needs_csv
def test_lockbox_needs_confirmation_opens_once_and_is_reused(tmp_path: Path) -> None:
    assert _train(tmp_path, "--open-lockbox") == 2
    assert _train(tmp_path, "--open-lockbox", "--confirm-config-sha", "0" * 64) == 2
    assert _train(tmp_path, "--confirm-config-sha", config.config_sha256()) == 2  # needs --open-lockbox
    assert not registry.lockbox_path(tmp_path, dev=True).exists()

    assert _train(tmp_path, "--open-lockbox", "--confirm-config-sha", config.config_sha256()) == 0
    # A dev (--fast, local_csv) opening never touches the production lockbox log.
    assert not registry.lockbox_path(tmp_path).exists()
    log = [json.loads(x) for x in registry.lockbox_path(tmp_path, dev=True).read_text(encoding="utf-8").splitlines()]
    assert len(log) == 1
    assert set(log[0]) == {"procedure_id", "horizon", "config_sha256", "git_sha", "data_sha256", "opened_at",
                           "result_sha256"}
    mid = _model_id(tmp_path)
    vpath = tmp_path / "models" / mid / "validation.json"
    opened = json.loads(vpath.read_text(encoding="utf-8"))
    assert opened["lockbox_opened_at"] == log[0]["opened_at"]
    assert opened["lockbox"]["n_dates"] > 0 and opened["lockbox"]["rank_ic_mean"] is not None
    assert any(g["id"] == "G6" and g["value"] is not None for g in opened["gates"])

    # A later run without --open-lockbox carries the recorded block and the same G6/P rows.
    assert _train(tmp_path) == 0
    assert _lockbox_view(json.loads(vpath.read_text(encoding="utf-8"))) == _lockbox_view(opened)

    assert _train(tmp_path, "--open-lockbox", "--confirm-config-sha", config.config_sha256()) == 2
    assert len(registry.lockbox_path(tmp_path, dev=True).read_text(encoding="utf-8").splitlines()) == 1
    with pytest.raises(PermissionError):
        registry.append_lockbox(log[0], tmp_path, dev=True)

    # A tampered recorded result fails closed.
    rpath = registry.lockbox_result_path(config.PROCEDURE_ID, H, tmp_path, dev=True)
    rec = json.loads(rpath.read_text(encoding="utf-8"))
    rec["result"]["hac_t"] = 9.9
    rpath.write_bytes(registry.canonical_json(rec))
    assert _train(tmp_path) == 2
    assert not registry.lockbox_path(tmp_path).exists()


def test_lockbox_result_is_recorded_once(tmp_path: Path) -> None:
    import hashlib

    block = {"rank_ic_mean": 0.01, "hac_t": 1.2, "net_monthly_pct": 0.1, "n_dates": 3}
    row = {"procedure_id": config.PROCEDURE_ID, "horizon": H, "config_sha256": "c" * 64, "git_sha": "g",
           "data_sha256": "d" * 64, "opened_at": "2026-10-11T00:00:00+00:00",
           "result_sha256": hashlib.sha256(registry.canonical_json(block)).hexdigest()}
    with pytest.raises(ValueError):
        registry.append_lockbox({**row, "result_sha256": "0" * 64}, tmp_path, result=block)
    assert registry.recorded_lockbox(config.PROCEDURE_ID, H, tmp_path) is None
    registry.append_lockbox(row, tmp_path, result=block)
    assert registry.recorded_lockbox(config.PROCEDURE_ID, H, tmp_path) == (row, block)
    assert registry.recorded_lockbox(config.PROCEDURE_ID, H, tmp_path, dev=True) is None
    registry.lockbox_result_path(config.PROCEDURE_ID, H, tmp_path).unlink()
    with pytest.raises(registry.ArtefactError, match="unreadable"):
        registry.recorded_lockbox(config.PROCEDURE_ID, H, tmp_path)


def test_production_training_needs_recorded_lockbox(tmp_path: Path) -> None:
    rc = train.RunConfig(horizon=H, source="store", data_dir=tmp_path, train_production=True)
    with pytest.raises(train.LockboxRefused, match="recorded first"):
        train.check_lockbox(rc)
    train.check_lockbox(train.RunConfig(horizon=H, source="local_csv", data_dir=tmp_path, train_production=True))


# ── artefact verification and promotion ─────────────────────────────────────


@needs_csv
def test_artefact_verifies_only_with_allow_fast(fast_run: dict[str, Any], tmp_path: Path) -> None:
    mdir = _copy_artefact(fast_run, tmp_path)
    with pytest.raises(registry.ArtefactError, match="allow-fast"):
        registry.verify(mdir)
    manifest, sha = registry.verify(mdir, allow_fast=True)
    assert manifest["fast"] is True and manifest["objective"] == "regression" and len(sha) == 64
    assert set(manifest["files"]) >= {"booster_s11.txt", "calibrator.json", "gate_result.json", "validation.json"}
    assert manifest["gate_result"]["tier"] == "no_reliable_edge"
    assert registry.main(["verify", "--model-id", mdir.name, "--data-dir", str(tmp_path)]) == 1
    assert registry.main(["promote", "--model-id", mdir.name, "--data-dir", str(tmp_path)]) == 1
    assert registry.main(["promote", "--model-id", mdir.name, "--data-dir", str(tmp_path), "--allow-fast"]) == 0
    art = registry.load_active(H, tmp_path)
    assert art.model_id == mdir.name and art.tier == "no_reliable_edge" and len(art.boosters) == 1
    assert registry.main(["verify", "--active", "--data-dir", str(tmp_path)]) == 0


@needs_csv
def test_rerun_never_rewrites_a_manifest_bound_artefact(fast_run: dict[str, Any], tmp_path: Path) -> None:
    mdir = _copy_artefact(fast_run, tmp_path)
    before = {p.name: p.read_bytes() for p in mdir.iterdir()}
    registry.promote(mdir.name, data_dir=tmp_path, allow_fast=True)
    assert _train(tmp_path) == 2
    assert _train(tmp_path, "--train-production") == 2
    assert {p.name: p.read_bytes() for p in mdir.iterdir()} == before
    registry.verify(mdir, allow_fast=True)
    assert registry.main(["verify", "--active", "--data-dir", str(tmp_path)]) == 0


@needs_csv
def test_tampered_booster_fails_verify(fast_run: dict[str, Any], tmp_path: Path) -> None:
    mdir = _copy_artefact(fast_run, tmp_path)
    registry.promote(mdir.name, data_dir=tmp_path, allow_fast=True)
    booster = mdir / "booster_s11.txt"
    booster.write_text(booster.read_text(encoding="utf-8").replace("leaf_value=", "leaf_value=1", 1), encoding="utf-8")
    with pytest.raises(registry.ArtefactError, match="sha256 mismatch for booster_s11.txt"):
        registry.verify(mdir, allow_fast=True)
    with pytest.raises(registry.ArtefactError):
        registry.load_active(H, tmp_path)
    assert registry.main(["verify", "--model-id", mdir.name, "--data-dir", str(tmp_path), "--allow-fast"]) == 1
    assert registry.main(["verify", "--active", "--data-dir", str(tmp_path)]) == 1


@needs_csv
def test_objective_mismatch_refused(fast_run: dict[str, Any], tmp_path: Path) -> None:
    mdir = _copy_artefact(fast_run, tmp_path)
    path = mdir / registry.MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))

    edited = {**manifest, "objective": "binary"}
    path.write_bytes(registry.canonical_json(edited))
    with pytest.raises(registry.ArtefactError, match="objective mismatch"):
        registry.verify(mdir, allow_fast=True)

    # A booster trained for another objective, even with a consistent manifest hash.
    booster = mdir / "booster_s11.txt"
    booster.write_text(booster.read_text(encoding="utf-8").replace("objective=regression", "objective=binary sigmoid:1", 1),
                       encoding="utf-8")
    files = {**manifest["files"], "booster_s11.txt": registry.sha256_file(booster)}
    path.write_bytes(registry.canonical_json({**manifest, "files": files}))
    with pytest.raises(registry.ArtefactError, match="objective mismatch in booster_s11.txt"):
        registry.verify(mdir, allow_fast=True)


@needs_csv
def test_promoted_manifest_change_is_refused(fast_run: dict[str, Any], tmp_path: Path) -> None:
    mdir = _copy_artefact(fast_run, tmp_path)
    registry.promote(mdir.name, data_dir=tmp_path, allow_fast=True)
    path = mdir / registry.MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["gate_result"]["tier"] = "validated_edge"  # every file still matches
    path.write_bytes(registry.canonical_json(manifest))
    registry.verify(mdir, allow_fast=True)
    with pytest.raises(registry.ArtefactError, match="differs from the registry"):
        registry.load_active(H, tmp_path)


def test_missing_artefact_and_registry(tmp_path: Path) -> None:
    with pytest.raises(registry.ArtefactError, match="manifest.json missing"):
        registry.verify(tmp_path / "nope")
    with pytest.raises(registry.ArtefactError, match="no active artefact"):
        registry.load_active(63, tmp_path)
    with pytest.raises(ValueError):
        registry.model_dir("../escape", tmp_path)
    assert registry.main(["verify", "--active", "--data-dir", str(tmp_path)]) == 1
