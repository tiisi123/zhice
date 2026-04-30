"""Alembic environment — T03 (M001/S01).

Wires Alembic's autogenerate to ``packages.shared.db_models.Base.metadata`` and
overrides the URL with the value validated by ``apps.api.config.Settings`` so
the same env-var contract used by the FastAPI runtime drives migrations.

Path notes
----------
We add ``prototype/`` to ``sys.path`` first so ``apps.api`` and ``packages``
import without an editable install (Alembic's CLI runs from inside this dir).
``alembic.ini`` keeps a placeholder URL for offline mode; the real URL is
``settings.database_url`` (production) or ``ZHICE_DATABASE_URL`` (dev override).
"""
from __future__ import annotations

import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

PROTOTYPE_ROOT = Path(__file__).resolve().parent.parent
if str(PROTOTYPE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_ROOT))

from packages.shared.db_models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _resolve_url() -> str:
    """Pick the connection URL with the same priority as apps.api.db.

    1. ``settings.database_url`` — pydantic-validated (prod gate)
    2. ``ZHICE_DATABASE_URL`` env — dev override
    3. ``alembic.ini`` placeholder (offline mode only)
    """
    try:
        from apps.api.config import settings

        url = (settings.database_url or "").strip()
        if url:
            return url
    except Exception as exc:  # pragma: no cover
        logger.debug("settings unavailable, falling back to env: %s", exc)

    env_url = os.environ.get("ZHICE_DATABASE_URL", "").strip()
    if env_url:
        return env_url

    return config.get_main_option("sqlalchemy.url", "")


def run_migrations_offline() -> None:
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_url()
    ini_section = config.get_section(config.config_ini_section, {}) or {}
    ini_section["sqlalchemy.url"] = url

    # Force MySQL connections into UTC at the engine level so any
    # ``CURRENT_TIMESTAMP`` evaluated during DDL/DML matches the runtime
    # engine convention. Done as a connect-event listener (NOT a one-shot
    # ``exec_driver_sql`` from inside ``run_migrations_online``) — that hack
    # leaves the SA connection mid-transaction and prevents alembic from
    # committing the ``alembic_version`` insert. (Diagnosed empirically against
    # MySQL 8.0.36 + SQLAlchemy 2.0.49 + alembic 1.18.4 during T03 verification.)
    from sqlalchemy import event  # local import: stays inside this function

    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    @event.listens_for(connectable, "connect")
    def _set_utc_timezone(dbapi_conn, _conn_rec):  # type: ignore[no-redef]
        if connectable.dialect.name in {"sqlite"}:
            return
        cur = dbapi_conn.cursor()
        try:
            cur.execute("SET time_zone='+00:00'")
        finally:
            cur.close()

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
