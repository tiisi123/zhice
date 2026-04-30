"""DEV-ONLY: copy data from the legacy SQLite file into a fresh MySQL 8.0 schema.

T03 (M001/S01) ships a fresh-MySQL deployment to staging; this script exists
purely for local developers who want to keep their existing ``data/zhice.db``
contents after the migration. Production / staging deploys should NOT run it.

Usage::

    cd prototype
    DATABASE_URL=mysql+pymysql://root:test@localhost:13306/zhice \\
        python scripts/migrate_sqlite_to_mysql.py [--sqlite-path data/zhice.db]

Behavior
--------
- Iterates every table defined in ``packages.shared.db_models.ALL_MODELS``.
- For each table: reads all rows from SQLite, inserts them into MySQL with
  ``ON DUPLICATE KEY UPDATE id=id`` (so re-runs are idempotent).
- Failures are logged per-row and counted; the script keeps going so a single
  schema mismatch (e.g. column-renamed-since-this-snapshot) does not abort
  everything. Final report prints ``OK`` rows and ``FAIL`` rows per table.
- Empty SQLite file → exit 0 with "no rows to migrate" message.

This script must NOT be wired into deployment automation. The slice plan
mandates a fresh DB on staging (``staging 起 fresh DB 不需要``).
"""
from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("zhice.migrate_sqlite_to_mysql")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROTOTYPE_ROOT = Path(__file__).resolve().parent.parent


def _maybe_skip_for_missing_deps() -> bool:
    """Return True iff sqlalchemy/pymysql aren't importable (sandbox path)."""
    try:
        import sqlalchemy  # noqa: F401
        import pymysql  # noqa: F401
        return False
    except ImportError as exc:
        logger.info("[SKIP] required deps missing in current interpreter: %s", exc)
        logger.info("       This script needs sqlalchemy + pymysql; install via")
        logger.info("       `pip install -e .` from prototype/.")
        return True


def _build_engine() -> Any:
    """Lazy import + build the SQLAlchemy engine (after the deps probe)."""
    from sqlalchemy import create_engine

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        # Fallback to settings.database_url if pydantic is available.
        try:
            sys.path.insert(0, str(PROTOTYPE_ROOT))
            from apps.api.config import settings  # type: ignore[import-not-found]
            url = settings.database_url.strip()
        except Exception:
            pass
    if not url:
        raise RuntimeError("DATABASE_URL env not set and settings.database_url empty")
    return create_engine(url, future=True, pool_pre_ping=True)


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return the column names a SQLite table actually has (defensive)."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _migrate_one(
    table: str, sqlite_conn: sqlite3.Connection, mysql_engine: Any
) -> tuple[int, int]:
    """Copy rows from one sqlite table to its mysql counterpart.

    Returns ``(ok_count, fail_count)``.
    """
    try:
        cols = _table_columns(sqlite_conn, table)
    except sqlite3.OperationalError as exc:
        logger.warning("[%s] sqlite table missing — skipping (%s)", table, exc)
        return 0, 0

    if not cols:
        return 0, 0

    rows = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    if not rows:
        logger.info("[%s] empty — nothing to migrate", table)
        return 0, 0

    placeholders = ", ".join(["%s"] * len(cols))
    cols_sql = ", ".join(cols)
    insert_sql = (
        f"INSERT INTO {table} ({cols_sql}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {cols[0]}={cols[0]}"
    )

    ok, fail = 0, 0
    with mysql_engine.begin() as conn:
        for row in rows:
            try:
                conn.exec_driver_sql(insert_sql, tuple(row))
                ok += 1
            except Exception as exc:
                fail += 1
                logger.warning("[%s] row failed: %s | row=%r", table, exc, dict(zip(cols, row)))
    return ok, fail


def main() -> int:
    if _maybe_skip_for_missing_deps():
        return 0

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        default=str(PROTOTYPE_ROOT / "data" / "zhice.db"),
        help="Path to legacy zhice.db (default: data/zhice.db).",
    )
    args = parser.parse_args()

    sqlite_file = Path(args.sqlite_path)
    if not sqlite_file.exists():
        logger.info("SQLite file %s not found — nothing to migrate, exiting 0.", sqlite_file)
        return 0

    sys.path.insert(0, str(PROTOTYPE_ROOT))
    from packages.shared.db_models import ALL_MODELS  # type: ignore[import-not-found]

    mysql_engine = _build_engine()
    logger.info("Source: %s", sqlite_file)
    logger.info("Target: %s", mysql_engine.url)

    sqlite_conn = sqlite3.connect(str(sqlite_file))
    sqlite_conn.row_factory = sqlite3.Row

    totals: dict[str, tuple[int, int]] = {}
    try:
        for model in ALL_MODELS:
            table = model.__tablename__
            ok, fail = _migrate_one(table, sqlite_conn, mysql_engine)
            totals[table] = (ok, fail)
            logger.info("[%s] OK=%d FAIL=%d", table, ok, fail)
    finally:
        sqlite_conn.close()

    grand_ok = sum(v[0] for v in totals.values())
    grand_fail = sum(v[1] for v in totals.values())
    logger.info("=" * 60)
    logger.info(
        "Migration done. Tables=%d OK=%d FAIL=%d",
        len(totals), grand_ok, grand_fail,
    )
    return 0 if grand_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
