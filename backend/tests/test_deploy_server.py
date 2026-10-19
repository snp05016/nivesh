"""C5: scripts/deploy_server.py stages the commit in a worktree, gates on a backup,
rehearses migrations on a copy, and only then switches the live tree.

Hermetic: every subprocess goes through a fake _run, urlopen and time.sleep are
replaced, and BACKUP_DIR, HOME and the temp dir all live under tmp_path.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import deploy_server as ds

SHA = "a" * 40
PREV = "b" * 40
LIVE_URL = "postgresql+psycopg2://u:p@h:5432/live"
SCRATCH_URL = "postgresql+psycopg2://u:secret@h:5432/scratch"


class FakeServer:
    """Answers the script's subprocesses; records (kind, where, cmd, env) per call."""

    def __init__(self, backup_dir: Path, pending=False, fail=(), dirty="", backup_suffix=".db"):
        self.backup_dir = backup_dir
        self.pending = pending
        self.fail = list(fail)  # "kind@where"; each entry fails one call
        self.dirty = dirty
        self.backup_suffix = backup_suffix
        self.stage = None
        self.calls = []

    def _kind(self, cmd):
        if cmd[0] == sys.executable and cmd[1] == "-m":
            return f"{cmd[2]} {cmd[3]}"
        if cmd[0] == sys.executable:
            return "backup"
        if cmd[0] == "git":
            return f"git {cmd[1]} {cmd[2]}" if cmd[1] == "worktree" else f"git {cmd[1]}"
        if cmd[0] == "sudo":
            return "restart"
        return cmd[0]

    def __call__(self, cmd, cwd=None, env=None):
        kind = self._kind(cmd)
        if kind == "git worktree add":
            self.stage = Path(cmd[4]) / "backend"
        where = "stage" if cwd is not None and Path(cwd) == self.stage else "live"
        assert where == "stage" or (cwd is not None and Path(cwd) == ds.LIVE), (cmd, cwd)
        self.calls.append((kind, where, list(cmd), env))
        name = f"{kind}@{where}"
        if name in self.fail:
            self.fail.remove(name)
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        out = ""
        if kind == "git status":
            out = self.dirty
        elif kind == "git rev-parse":
            out = PREV + "\n"
        elif kind == "alembic heads":
            out = "new000000001 (head)\n"
        elif kind == "alembic current":
            out = "old000000001\n" if self.pending else "new000000001 (head)\n"
        elif kind == "backup":
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            (self.backup_dir / f"stockapp-20261019T000000Z{self.backup_suffix}").write_bytes(b"backup")
        return subprocess.CompletedProcess(cmd, 0, out, "")

    def kinds(self):
        return [(k, w) for k, w, _, _ in self.calls]

    def index(self, kind, where=None, arg=None):
        for i, (k, w, cmd, _) in enumerate(self.calls):
            if k == kind and (where is None or w == where) and (arg is None or arg in cmd):
                return i
        raise AssertionError(f"{kind}@{where} {arg} not called: {self.kinds()}")

    def ran(self, kind):
        return any(k == kind for k, _, _, _ in self.calls)


class _Ready:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (tmp_path / "tmp").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "bk"))
    monkeypatch.delenv("RESTORE_DRILL_PG_URL", raising=False)
    monkeypatch.setattr(ds.tempfile, "tempdir", str(tmp_path / "tmp"))
    monkeypatch.setattr("core.env.load_backend_env", lambda *a, **k: False)
    sleeps = []
    monkeypatch.setattr(ds.time, "sleep", sleeps.append)
    monkeypatch.setattr(ds.urllib.request, "urlopen", lambda *a, **k: _Ready())

    def install(**kw):
        fake = FakeServer(tmp_path / "bk", **kw)
        monkeypatch.setattr(ds, "_run", fake)
        return fake

    return {"home": home, "install": install, "sleeps": sleeps, "monkeypatch": monkeypatch}


def _log(env):
    return [json.loads(line) for line in (env["home"] / "nivesh-deploys.log").read_text().splitlines()]


def _deploy(*extra):
    return ds.main(["--sha", SHA, *extra])


def test_no_pending_migrations(env):
    fake = env["install"]()
    assert _deploy() == 0

    assert fake.ran("git worktree add") and fake.ran("git worktree remove")
    assert not fake.ran("backup") and not fake.ran("alembic upgrade")
    checkout = fake.index("git checkout", "live", SHA)
    assert fake.index("pip install", "live") > checkout
    assert fake.index("restart") > checkout
    log = _log(env)
    assert len(log) == 1 and log[0]["ts_utc"]
    assert {k: log[0][k] for k in ("sha", "prev_sha", "migrated", "rehearsal", "exit_code")} == {
        "sha": SHA, "prev_sha": PREV, "migrated": False, "rehearsal": "none", "exit_code": 0}


def test_pending_migrations_rehearsed_then_applied(env):
    fake = env["install"](pending=True)
    assert _deploy() == 0

    backup = fake.index("backup", "live")
    upgrade = fake.index("alembic upgrade", "stage")
    check = fake.index("alembic check", "stage")
    assert backup < upgrade < check
    copy_url = fake.calls[upgrade][3]["DATABASE_URL"]
    assert copy_url.startswith("sqlite:///") and copy_url.endswith("stockapp-20261019T000000Z.db")
    assert str(Path(env["home"]).parent / "bk") not in copy_url  # a copy, never the backup itself
    assert fake.calls[check][3]["DATABASE_URL"] == copy_url

    checkout = fake.index("git checkout", "live", SHA)
    assert checkout > check
    assert fake.index("git worktree remove") < checkout
    prod = fake.index("alembic upgrade", "live")
    assert checkout < prod < fake.index("restart")
    entry = _log(env)[0]
    assert entry["migrated"] is True and entry["rehearsal"] == "sqlite" and entry["exit_code"] == 0


def test_backup_failure_exits_3_without_touching_live(env):
    fake = env["install"](pending=True, fail=["backup@live"])
    assert _deploy() == 3
    assert not fake.ran("git checkout")
    assert fake.ran("git worktree remove")
    assert _log(env)[0]["exit_code"] == 3


def test_rehearsal_failure_exits_4(env):
    fake = env["install"](pending=True, fail=["alembic check@stage"])
    assert _deploy() == 4
    assert not fake.ran("git checkout")
    assert not fake.ran("restart")
    assert fake.ran("git worktree remove")


def test_skip_rehearsal(env):
    fake = env["install"](pending=True)
    assert _deploy("--skip-rehearsal") == 0
    assert not any(w == "stage" and k != "alembic heads" for k, w in fake.kinds())
    assert _log(env)[0]["rehearsal"] == "skipped"


def test_pip_failure_exits_5_and_reinstalls_prev(env):
    fake = env["install"](fail=["pip install@live"])
    assert _deploy() == 5
    tail = [(k, c[-1]) for k, _, c, _ in fake.calls[fake.index("git checkout", "live", SHA):]]
    assert tail == [("git checkout", SHA), ("pip install", "requirements.txt"),
                    ("git checkout", PREV), ("pip install", "requirements.txt")]
    assert not fake.ran("restart")


def test_prod_migration_failure_exits_6_without_restart(env, capsys):
    fake = env["install"](pending=True, fail=["alembic upgrade@live"])
    assert _deploy() == 6
    failed = fake.index("alembic upgrade", "live")
    after = [(k, c[-1]) for k, _, c, _ in fake.calls[failed + 1:]]
    assert after == [("git checkout", PREV), ("pip install", "requirements.txt")]
    assert not fake.ran("restart")
    assert "stockapp-20261019T000000Z.db" in capsys.readouterr().err
    assert _log(env)[0]["migrated"] is False


def test_postgres_scratch_equal_to_live_exits_4_before_pg_restore(env):
    env["monkeypatch"].setenv("DATABASE_URL", LIVE_URL)
    env["monkeypatch"].setenv("RESTORE_DRILL_PG_URL", "postgresql+psycopg2://other:x@h:5432/live")
    fake = env["install"](pending=True, backup_suffix=".dump")
    assert _deploy() == 4
    assert not fake.ran("pg_restore")
    assert not fake.ran("git checkout")


def test_postgres_rehearsal_uses_libpq_dsn_and_pgpassword(env, capsys):
    env["monkeypatch"].setenv("DATABASE_URL", LIVE_URL)
    env["monkeypatch"].setenv("RESTORE_DRILL_PG_URL", SCRATCH_URL)
    fake = env["install"](pending=True, backup_suffix=".dump")
    assert _deploy() == 0

    _, _, argv, pg_env = fake.calls[fake.index("pg_restore")]
    i = argv.index("--dbname")
    assert argv[i + 1] == "postgresql://u@h:5432/scratch"
    assert not any("secret" in a or "+psycopg2" in a for a in argv)
    assert pg_env["PGPASSWORD"] == "secret"
    upgrade = fake.index("alembic upgrade", "stage")
    assert fake.index("pg_restore") < upgrade
    assert fake.calls[upgrade][3]["DATABASE_URL"] == SCRATCH_URL
    printed = capsys.readouterr()
    assert "secret" not in printed.out + printed.err
    assert _log(env)[0]["rehearsal"] == "postgres"


def test_dirty_tracked_tree_exits_2(env):
    fake = env["install"](dirty=" M backend/main.py\n")
    assert _deploy() == 2
    _, _, status, _ = fake.calls[0]
    assert status[:3] == ["git", "status", "--porcelain"] and "--untracked-files=no" in status
    assert not fake.ran("git worktree add") and not fake.ran("git checkout")
    assert _log(env)[0]["exit_code"] == 2


def test_health_timeout_exits_7_with_rollback(env, capsys):
    def down(*_a, **_k):
        raise OSError("connection refused")

    env["monkeypatch"].setattr(ds.urllib.request, "urlopen", down)
    env["install"]()
    assert _deploy() == 7
    err = capsys.readouterr().err
    assert f"git checkout --detach {PREV}" in err
    assert "pip install -r requirements.txt" in err
    assert "restore" not in err  # nothing was migrated
    assert env["sleeps"] and set(env["sleeps"]) == {2} and len(env["sleeps"]) == ds.READY_POLLS - 1
    assert _log(env)[0]["exit_code"] == 7


def test_rejects_short_sha(env):
    env["install"]()
    with pytest.raises(SystemExit):
        ds.main(["--sha", "abc123"])
    assert not (env["home"] / "nivesh-deploys.log").exists()
