"""
Alembic environment — reads DATABASE_URL from app.core.config
(alembic.ini leaves sqlalchemy.url blank on purpose, so the same .env
drives both the app and the migrations).

The import block below is the one line everyone forgets: every module's
models.py must be imported before ``target_metadata = Base.metadata`` is
evaluated, or ``--autogenerate`` compares against an empty schema and
produces a migration with nothing in it.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.db import Base

# --- import every models module so Base.metadata is complete ---------- #
from app.auth import models as _auth_models          # noqa: F401
from app.core import models as _core_models          # noqa: F401
# as modules are added later:
# from app.modules.inventory import models as _inv_models   # noqa: F401
# from app.modules.expiry import models as _exp_models      # noqa: F401
# from app.modules.reorder import models as _ror_models     # noqa: F401
# from app.modules.notification import models as _ntf_models # noqa: F401
# from app.modules.clinic import models as _cln_models      # noqa: F401
# from app.modules.reporting import models as _rpt_models   # noqa: F401
# ---------------------------------------------------------------------- #

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Fail loudly if the metadata is empty — an empty migration is worse than
# an error because it applies silently.
if not Base.metadata.tables:
    raise RuntimeError(
        "Base.metadata is empty. The model imports above did not take — "
        "check the `from app... import models` lines."
    )

target_metadata = Base.metadata

# Read the URL from settings rather than alembic.ini. ``ConfigParser``
# treats ``%`` as the start of an interpolation, and URL-encoded Supabase
# passwords contain ``%40``, ``%3A`` etc., so any ``%`` must be doubled
# before being handed to config.set_main_option.
_url = get_settings().DATABASE_URL.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _url)


def run_migrations_offline() -> None:
    """Render SQL without a live connection (alembic upgrade --sql)."""
    context.configure(
        url=_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the DB and apply migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
