"""AUTH-01: admin comes only from the persisted users.is_admin flag (never a username),
init_db seeds no accounts, and scripts/manage_users.py grants admin / resets passwords."""
import uuid

import bcrypt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database
from models.db_models import Base, User
from tests.conftest import REGISTER_CONSENT

PASSWORD = "AdminRole!2026"


def _register(client, username):
    """Register via the API: (user_id, auth headers), or (None, None) if the name is taken."""
    resp = client.post("/register", json={"username": username, "password": PASSWORD, "display_name": username, **REGISTER_CONSENT})
    assert resp.status_code in (200, 400), resp.text
    if resp.status_code == 400:
        return None, None
    body = resp.json()
    return body["user_id"], {"Authorization": f"Bearer {body['access_token']}"}


def _set_admin_flag(user_id, value):
    with database.get_session() as s:
        s.query(User).filter(User.id == user_id).update({"is_admin": value})
        s.commit()


def _delete_users(user_ids):
    with database.get_session() as s:
        for uid in user_ids:
            user = s.get(User, uid)
            if user is not None:
                s.delete(user)
        s.commit()


def test_former_admin_usernames_get_no_admin_rights(client):
    created = []
    try:
        for name in (f"nirav_{uuid.uuid4().hex[:8]}", "saumya", "nirav"):
            user_id, headers = _register(client, name)
            if user_id is None:
                continue
            created.append(user_id)
            assert database.is_admin(user_id) is False
            assert client.get("/users", headers=headers).status_code == 403
            assert client.get("/dashboard-data", headers=headers).status_code == 403
        assert created, "could not register any test user"
    finally:
        _delete_users(created)


def test_is_admin_flag_grants_and_revokes_access(client):
    user_id, headers = _register(client, f"admin_{uuid.uuid4().hex[:8]}")
    assert user_id is not None
    try:
        assert client.get("/users", headers=headers).status_code == 403
        _set_admin_flag(user_id, True)
        assert client.get("/users", headers=headers).status_code == 200
        _set_admin_flag(user_id, False)  # read per request, so revocation is immediate
        assert client.get("/users", headers=headers).status_code == 403
    finally:
        _delete_users([user_id])


def test_seed_accounts_and_name_based_promotion_removed(client):
    for name in ("SEED_USERS", "DAD_HOLDINGS", "promote_initial_admins", "set_admin"):
        assert not hasattr(database, name), name
    # init_db ran on an empty test DB (conftest import and app startup) in a non-production
    # ENVIRONMENT, which used to seed these accounts with the published password.
    for username in ("saumya", "nirav", "ankur"):
        resp = client.post("/login", json={"username": username, "password": "123"})
        assert resp.status_code == 401, username


def test_init_db_on_empty_db_creates_no_users(tmp_path, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")  # dev used to mean "seed dev accounts"
    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    try:
        database.init_db()
        with database.get_session() as s:
            assert s.query(User).count() == 0
    finally:
        engine.dispose()


@pytest.fixture
def db():
    """Fresh in-memory SQLite database per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_manage_users_commands(db):
    from scripts.manage_users import accounts_with_published_password, reset_password, set_admin

    weak = bcrypt.hashpw(b"123", bcrypt.gensalt(rounds=4)).decode()
    db.add(User(username="nirav", password_hash=weak, display_name="Nirav"))
    db.commit()
    assert accounts_with_published_password(db) == ["nirav"]

    def flag():
        return db.query(User.is_admin).filter(User.username == "nirav").scalar()

    set_admin(db, "Nirav", True)
    assert flag() is True
    set_admin(db, "nirav", False)
    assert flag() is False
    with pytest.raises(LookupError):
        set_admin(db, "nobody", True)
    with pytest.raises(ValueError):
        reset_password(db, "nirav", "short")

    reset_password(db, "nirav", "a-much-better-passphrase")
    new_hash, version = db.query(User.password_hash, User.token_version).filter(User.username == "nirav").one()
    assert version == 1
    assert database.verify_password("a-much-better-passphrase", new_hash)
    assert accounts_with_published_password(db) == []
