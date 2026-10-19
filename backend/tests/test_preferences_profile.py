"""user_preferences.preferred_language (en|hi) and the preferences API (I23/I40).

- GET defaults preferred_language to 'en'; PUT 'hi' persists;
- 'hinglish' and profiling fields (experience_level, risk_comfort, horizon) are 422;
- no token is 401; a PUT only touches the caller's row;
- theme and alerts_enabled behave as before;
- revision 5c2e9b7d41af: upgrade adds the column and CHECK, downgrade removes
  them, upgrading again works (temp SQLite).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = Path(__file__).resolve().parents[1]
URL = "/api/v1/preferences"
REVISION = "5c2e9b7d41af"
CHECK = "ck_user_preferences_preferred_language"


def _new_user() -> tuple[int, dict]:
    import database
    from models.db_models import User  # pyright: ignore[reportMissingImports]  (checker resolves `models` to ml-engine/models)

    with database.get_session() as session:
        user = User(username=f"pp_{uuid4().hex[:12]}", password_hash="x", display_name="Prefs Test")
        session.add(user)
        session.commit()
        user_id = int(user.id)  # type: ignore[arg-type]
    return user_id, {"Authorization": f"Bearer {database.create_access_token(user_id)}"}


def test_get_defaults_to_english(client):
    user_id, headers = _new_user()
    resp = client.get(URL, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_id"] == user_id
    assert body["preferred_language"] == "en"


def test_put_hindi_persists(client):
    _, headers = _new_user()
    put = client.put(URL, json={"preferred_language": "hi"}, headers=headers)
    assert put.status_code == 200, put.text
    assert put.json()["preferred_language"] == "hi"
    assert client.get(URL, headers=headers).json()["preferred_language"] == "hi"

    back = client.put(URL, json={"preferred_language": "en"}, headers=headers)
    assert back.status_code == 200, back.text
    assert client.get(URL, headers=headers).json()["preferred_language"] == "en"


@pytest.mark.parametrize("payload", [
    {"preferred_language": "hinglish"},
    {"preferred_language": "HI"},
    {"experience_level": "new"},
    {"risk_comfort": "high"},
    {"horizon": "long"},
    {"alerts_enabled": True, "risk_comfort": "high"},
])
def test_rejected_payloads_are_422_and_write_nothing(client, payload):
    _, headers = _new_user()
    resp = client.put(URL, json=payload, headers=headers)
    assert resp.status_code == 422, resp.text
    after = client.get(URL, headers=headers).json()
    assert after["preferred_language"] == "en"
    assert set(after) == {"user_id", "theme", "alerts_enabled", "preferred_language"}


def test_shared_auth_headers_user_is_validated(client, auth_headers):
    assert client.put(URL, json={"experience_level": "new"}, headers=auth_headers).status_code == 422
    resp = client.get(URL, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["preferred_language"] in {"en", "hi"}


def test_requires_token(client):
    assert client.get(URL).status_code == 401
    assert client.put(URL, json={"preferred_language": "hi"}).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.put(URL, json={"preferred_language": "hi"}, headers=bad).status_code == 401


def test_put_only_changes_the_callers_row(client):
    first_id, first = _new_user()
    _, second = _new_user()
    assert client.put(URL, json={"preferred_language": "en", "alerts_enabled": True}, headers=first).status_code == 200

    # Identity comes from the token only; a user_id in the body is an unknown field.
    assert client.put(URL, json={"user_id": first_id, "preferred_language": "hi"}, headers=second).status_code == 422
    assert client.put(URL, json={"preferred_language": "hi", "alerts_enabled": False}, headers=second).status_code == 200

    mine = client.get(URL, headers=first).json()
    assert mine["user_id"] == first_id
    assert mine["preferred_language"] == "en"
    assert mine["alerts_enabled"] is True
    theirs = client.get(URL, headers=second).json()
    assert theirs["preferred_language"] == "hi"
    assert theirs["alerts_enabled"] is False


def test_theme_and_alerts_unchanged_behaviour(client):
    _, headers = _new_user()
    first = client.get(URL, headers=headers).json()
    assert first["theme"] == "banknote_standard"
    assert first["alerts_enabled"] is True

    put = client.put(URL, json={"theme": "midnight", "alerts_enabled": False}, headers=headers)
    assert put.status_code == 200, put.text
    assert put.json()["theme"] == "midnight"
    assert put.json()["alerts_enabled"] is False
    assert put.json()["preferred_language"] == "en"

    # A language-only PUT leaves theme and alerts alone, and vice versa.
    assert client.put(URL, json={"preferred_language": "hi"}, headers=headers).status_code == 200
    assert client.put(URL, json={"alerts_enabled": True}, headers=headers).status_code == 200
    after = client.get(URL, headers=headers).json()
    assert after["theme"] == "midnight"
    assert after["alerts_enabled"] is True
    assert after["preferred_language"] == "hi"


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path}"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR), capture_output=True, text=True, env=env,
    )


def _prefs_schema(db_path: Path) -> tuple[set, set]:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        insp = sa.inspect(engine)
        return (
            {c["name"] for c in insp.get_columns("user_preferences")},
            {c["name"] for c in insp.get_check_constraints("user_preferences")},
        )
    finally:
        engine.dispose()


def _script():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return ScriptDirectory.from_config(config)


def test_revision_is_chained_to_a_single_head():
    script = _script()
    assert len(script.get_heads()) == 1
    rev = script.get_revision(REVISION)
    assert rev is not None and isinstance(rev.down_revision, str)


def test_migration_upgrade_downgrade_upgrade(tmp_path):
    db = tmp_path / "prefs_language.db"
    up = _alembic(db, "upgrade", "head")
    assert up.returncode == 0, up.stderr
    columns, checks = _prefs_schema(db)
    assert "preferred_language" in columns and CHECK in checks

    engine = sa.create_engine(f"sqlite:///{db}")
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO users (id, username, password_hash, display_name) VALUES (1, 'p1', 'x', 'P')"
            ))
            conn.execute(sa.text("INSERT INTO user_preferences (user_id) VALUES (1)"))
            assert conn.execute(sa.text("SELECT preferred_language FROM user_preferences")).scalar() == "en"
        with pytest.raises(IntegrityError):
            with engine.begin() as conn:
                conn.execute(sa.text("UPDATE user_preferences SET preferred_language = 'hinglish'"))
    finally:
        engine.dispose()

    rev = _script().get_revision(REVISION)
    assert rev is not None
    down = _alembic(db, "downgrade", str(rev.down_revision))
    assert down.returncode == 0, down.stderr
    columns, checks = _prefs_schema(db)
    assert "preferred_language" not in columns and CHECK not in checks

    again = _alembic(db, "upgrade", "head")
    assert again.returncode == 0, again.stderr
    columns, checks = _prefs_schema(db)
    assert "preferred_language" in columns and CHECK in checks
