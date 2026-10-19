"""ML-07: immutable artifacts, verified MANIFEST.json, and startup integrity checks."""

from __future__ import annotations

import hashlib
import json

import lightgbm as lgb  # before main: load OpenMP first (see test_inference_semantics)
import numpy as np
import pytest

import main
import training.model_registry as mr
from config import FEATURE_LIST, LIGHTGBM_MODEL_PATH

_PASS = {"passed": True, "checks": {}, "reasons": [], "reasons_for_rejection": [],
         "base_rate": 0.55, "neutral_band": 0.02}


def _booster(n_features: int) -> lgb.Booster:
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, n_features))
    return lgb.train({"objective": "binary", "verbose": -1},
                     lgb.Dataset(X, (X[:, 0] > 0).astype(int)), num_boost_round=3)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setattr(mr, "REGISTRY_DIR", tmp_path / "registry")
    monkeypatch.setattr(mr, "_PRODUCTION_MODEL_PATH", tmp_path / "models" / "lgb_model.txt")
    monkeypatch.setattr(mr, "_PRODUCTION_MANIFEST_PATH", tmp_path / "models" / "MANIFEST.json")
    monkeypatch.setattr(mr, "evaluate_deployment_guardrails", lambda *a, **k: dict(_PASS))
    monkeypatch.setattr(main, "LIGHTGBM_MODEL_PATH", tmp_path / "models" / "lgb_model.txt")
    return tmp_path


def _save(version: str = "v1", n_features: int = len(FEATURE_LIST)):
    return mr.save_model_artifact(_booster(n_features), FEATURE_LIST[:n_features],
                                  {"data_sha256": "d" * 64}, [], {}, model_version=version)


def test_deploy_writes_manifest_matching_the_deployed_file(registry):
    _save()
    prod = mr.deploy_to_production("v1")
    manifest = json.loads((registry / "models" / "MANIFEST.json").read_text())

    assert manifest["sha256"] == hashlib.sha256(prod.read_bytes()).hexdigest()
    assert manifest["num_features"] == 158
    assert manifest["feature_list"] == FEATURE_LIST
    assert manifest["model_version"] == "v1"
    assert manifest["data_sha256"] == "d" * 64
    assert manifest["objective"].startswith("binary")
    assert manifest["gate"]["passed"] is True
    assert (manifest["base_rate"], manifest["neutral_band"]) == (0.55, 0.02)
    assert not list((registry / "models").glob("*.tmp"))
    assert main._verify_model(lgb.Booster(model_file=str(prod)), manifest) is None


def test_saving_an_existing_version_raises(registry):
    _save()
    with pytest.raises(FileExistsError):
        _save()


def test_deploy_rejects_booster_features_json_mismatch(registry):
    artifact = _save()
    (artifact / "features.json").write_text(json.dumps(FEATURE_LIST[:157]))
    with pytest.raises(ValueError):
        mr.deploy_to_production("v1")
    assert not (registry / "models" / "lgb_model.txt").exists()


def test_verify_model_rejects_sha_mismatch_and_wrong_feature_count(registry):
    _save()
    prod = mr.deploy_to_production("v1")
    manifest = json.loads((registry / "models" / "MANIFEST.json").read_text())
    booster = lgb.Booster(model_file=str(prod))

    assert "sha256" in main._verify_model(booster, {**manifest, "sha256": "0" * 64})

    small = _booster(157)
    small.save_model(str(prod))
    assert "features" in main._verify_model(small, {**manifest, "sha256": hashlib.sha256(prod.read_bytes()).hexdigest()})
    assert main._verify_model(booster, {}) == "no manifest"


def test_startup_unloads_booster_whose_manifest_does_not_match(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    manifest_path = tmp_path / "MANIFEST.json"
    manifest_path.write_text(json.dumps({"model_version": "v9", "sha256": "0" * 64, "gate": _PASS}))
    monkeypatch.setattr(main, "MANIFEST_PATH", manifest_path)
    with TestClient(main.app) as client:
        ready = client.get("/ready")
        status = client.get("/model/status").json()
    assert ready.status_code == 503
    assert ready.json()["reason"] == "model_integrity"
    assert status["lightgbm_loaded"] is False
    assert status["model_integrity_ok"] is False
    assert status["manifest_version"] == "v9"
    assert status["model_validated"] is False


def test_repo_has_no_unverified_version_marker():
    models_dir = LIGHTGBM_MODEL_PATH.parent
    assert not (models_dir / "DEPLOYED_VERSION").exists()
    assert not (models_dir / "VERSION").exists()
    manifest_path = models_dir / "MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        assert manifest["sha256"] == hashlib.sha256(LIGHTGBM_MODEL_PATH.read_bytes()).hexdigest()
