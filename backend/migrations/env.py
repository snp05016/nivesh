from logging.config import fileConfig
import os
import sys
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Same configuration as the app (DB-14): backend/.env, except that an explicitly
# exported DATABASE_URL still wins. load_backend_env is a no-op under pytest.
from core.env import load_backend_env  # noqa: E402

_explicit_url = os.environ.get("DATABASE_URL")
load_backend_env()
database_url = _explicit_url or os.getenv("DATABASE_URL")
if not database_url:
    if os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("DATABASE_URL must be set for migrations in production")
    # The app's own default (database.py), not alembic.ini's cwd-relative file.
    database_url = f"sqlite:///{BACKEND_DIR / 'stockapp.db'}"
# Escape "%" (URL-encoded passwords) for the ConfigParser behind set_main_option.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
from models.db_models import Base  # noqa: E402
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # SQLite can't reliably introspect FK/unique constraints and reports
        # type-affinity aliases (REAL/TEXT vs Float/JSON) as drift, so those
        # comparisons are skipped there. Postgres (prod + CI) compares them all.
        is_sqlite = connection.dialect.name == "sqlite"

        def _include_object(obj, name, type_, reflected, compare_to):
            if is_sqlite and type_ in ("foreign_key_constraint", "unique_constraint"):
                return False
            return True

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,          # SQLite doesn't support ALTER, use batch mode
            compare_type=not is_sqlite,
            compare_server_default=False,  # Server default rendering differs per dialect; not actionable
            include_object=_include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
