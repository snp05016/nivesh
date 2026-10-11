"""DB-29: the mock-data reset script refuses to run outside dev, and the
populate_portfolio.py wiper is gone."""
import importlib.util
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]

# Load from file; importing does not run main().
_spec = importlib.util.spec_from_file_location(
    "_reset_mock_user", BACKEND / "scripts" / "reset_mock_user.py"
)
assert _spec is not None and _spec.loader is not None
reset_mock_user = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reset_mock_user)


def test_refuses_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(SystemExit):
        reset_mock_user.require_dev_env(["x", "--yes"])


def test_refuses_when_environment_unset(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(SystemExit):
        reset_mock_user.require_dev_env(["x", "--yes"])


def test_refuses_without_yes_in_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(SystemExit):
        reset_mock_user.require_dev_env(["x"])


def test_allows_development_with_yes(monkeypatch, capsys):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert reset_mock_user.require_dev_env(["x", "--yes"]) is None
    assert "Target DB:" in capsys.readouterr().out


def test_no_hardcoded_credentials_or_real_account():
    assert not hasattr(reset_mock_user, "USER_PASSWORD")
    assert not hasattr(reset_mock_user, "USER_EMAIL")
    assert reset_mock_user.DEFAULT_USER_NAME != "saumya"


def test_populate_portfolio_removed():
    assert not (BACKEND / "populate_portfolio.py").exists()
