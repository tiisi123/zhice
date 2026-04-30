"""轻量级持久化层：MySQL 8.0 走 SQLAlchemy 2.x，开发态保留 SQLite fallback。

T03 (M001/S01) 把 27 张表的 schema 移交给 SQLAlchemy ORM (packages/shared/db_models.py)
+ Alembic 0001_initial revision，本文件只负责：

1. 维持旧 ``execute / query_one / query_all / get_conn`` API（routes 层不动）
2. 暴露 ``get_engine() / SessionLocal / get_session()`` 标准 SQLAlchemy 入口（新代码用）
3. 强制连接级 ``SET time_zone='+00:00'``（解决 MySQL TIMESTAMP 隐式时区坑）
4. 把 sqlite-style ``?`` 占位转成 pymysql 的 ``%s``（routes 不用学方言）
5. ``DateTime`` 行值在出库时转回 ISO 字符串（auth/service.py 等代码 strptime 需要字符串）
6. 启动时 best-effort seed admin（连不上 DB 则静默跳过，由 ``/api/health`` 暴露 degraded）

`_DB_PATH` 作为 legacy 符号继续导出（routes/recommend.py 直接 import 它读 sqlite 文件做
本地缓存查询；MySQL 环境下文件不存在，``_quick_query_all`` 自带 try/except 退化为返回 ``[]``）。
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, date as date_cls, time as time_cls
from pathlib import Path
from typing import Any, Iterable, Iterator

logger = logging.getLogger("zhice.api.db")

# Legacy file path kept for backward compat with routes/recommend.py:23 which
# imports `_DB_PATH` to open a read-only sqlite cache. In MySQL deployments the
# file simply doesn't exist; the route already swallows missing-file errors.
_DB_PATH: Path = Path(
    os.environ.get(
        "ZHICE_DB_PATH",
        Path(__file__).resolve().parents[2] / "data" / "zhice.db",
    )
)
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Engine / Session — lazy single-instance (settings imports may pre-load this
# module before MySQL is reachable; we want first-query failures, not import
# failures).
# ---------------------------------------------------------------------------

_engine_lock = threading.Lock()
_engine: Any | None = None
_SessionLocal: Any | None = None
_init_done = False
_QMARK_RE = re.compile(r"\?")


def _resolve_database_url() -> str:
    """Return the connection URL the engine should use.

    Priority: ``settings.database_url`` (canonical, prod-validated) →
    ``ZHICE_DATABASE_URL`` env (dev override) → SQLite fallback file path.
    """
    try:
        from .config import settings  # local import: avoid pydantic at module load
        url = settings.database_url.strip()
        if url:
            return url
    except Exception as exc:  # pragma: no cover — happens only when pydantic absent
        logger.debug("config.settings unavailable, falling back to env: %s", exc)

    env_url = os.environ.get("ZHICE_DATABASE_URL", "").strip()
    if env_url:
        return env_url

    return f"sqlite:///{_DB_PATH}"


def get_engine():
    """Return the (lazy-built) SQLAlchemy engine; raise if SQLAlchemy is missing."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine
    with _engine_lock:
        if _engine is not None:
            return _engine
        from sqlalchemy import create_engine, event  # noqa: PLC0415
        from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

        url = _resolve_database_url()
        is_sqlite = url.startswith("sqlite")
        kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
        if not is_sqlite:
            # Production MySQL pool tuning: 50-user (M001) at < 100 RPS sits
            # comfortably under pool_size=10 + max_overflow=20. 10x breakpoint
            # is documented in T03 plan — we exit the slice on M002 with
            # PgBouncer-class middleware planned.
            kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 3600})
        _engine = create_engine(url, **kwargs)

        # Force every MySQL connection into UTC so naive datetimes written by
        # the application layer round-trip without surprise tz conversion.
        if not is_sqlite:
            @event.listens_for(_engine, "connect")
            def _set_utc_timezone(dbapi_conn, _conn_rec):  # type: ignore[no-redef]
                cur = dbapi_conn.cursor()
                try:
                    cur.execute("SET time_zone='+00:00'")
                finally:
                    cur.close()

        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)
        logger.info(
            "DB engine ready (scheme=%s, pool_size=%s)",
            url.split("://", 1)[0],
            kwargs.get("pool_size", "n/a"),
        )
        return _engine


def get_session_factory():
    """Return ``sessionmaker`` bound to the engine."""
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


@contextmanager
def get_session() -> Iterator[Any]:
    """Yield a SQLAlchemy session; commits on clean exit, rolls back on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Legacy sqlite-shaped API — preserved so routes/* / scheduler.py / auth/* keep
# working without changes. Translates qmark (?) placeholders to pymysql's %s
# and unwraps datetime objects back to ISO strings (auth.service uses strptime
# on the wire format, so we cannot leak datetime objects through the dict).
# ---------------------------------------------------------------------------


def _convert_qmark_sql(sql: str, params: tuple) -> tuple[str, tuple]:
    """Translate ``?`` placeholders → engine-native paramstyle.

    For pymysql, the cursor uses ``pyformat`` (``%s``). For sqlite (dev
    fallback) we leave ``?`` alone. ``%`` characters in literals are escaped
    so MySQL's ``%`` formatter does not mis-parse them.

    The codebase audited at T03 has zero ``?`` inside string literals, so a
    naive replace is safe; we still validate the count to surface mismatches.
    """
    if not params:
        return sql, ()

    expected = len(_QMARK_RE.findall(sql))
    if expected != len(params):
        raise ValueError(
            f"SQL placeholder count {expected} does not match params length {len(params)}: {sql!r}"
        )

    url_scheme = _resolve_database_url().split("://", 1)[0].lower()
    if url_scheme.startswith("sqlite"):
        # SQLite + qmark — pass through unchanged.
        return sql, tuple(params)

    # pymysql pyformat: every literal % must be escaped to %%.
    sql_pct_safe = sql.replace("%", "%%")
    new_sql = _QMARK_RE.sub("%s", sql_pct_safe)
    return new_sql, tuple(params)


def _normalize_value(value: Any) -> Any:
    """Convert driver-native types back to the wire shape that SQLite returned.

    - ``datetime`` / ``date`` / ``time`` → ISO-style string (auth.service does
      ``datetime.strptime(value, "%Y-%m-%d %H:%M:%S")``; FastAPI also serializes
      either form, but routes' string ops (e.g. trade_date prefix) need text).
    - ``bytes`` (rare; some drivers return TEXT as bytes) → utf-8 string.
    - Other primitives pass through unchanged.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date_cls):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, time_cls):
        return value.strftime("%H:%M:%S")
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return bytes(value)
    return value


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Normalize a SQLAlchemy ``Row`` (or sqlite Row) into a plain ``dict``."""
    if hasattr(row, "_mapping"):  # SQLAlchemy 2.x Row
        return {k: _normalize_value(v) for k, v in row._mapping.items()}
    if isinstance(row, sqlite3.Row):
        return {k: _normalize_value(row[k]) for k in row.keys()}
    if isinstance(row, dict):
        return {k: _normalize_value(v) for k, v in row.items()}
    raise TypeError(f"Unsupported row type: {type(row)!r}")


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Run a write query; return ``lastrowid`` for INSERTs or ``rowcount`` otherwise."""
    engine = get_engine()
    payload = tuple(params)
    new_sql, new_params = _convert_qmark_sql(sql, payload)
    with engine.begin() as conn:
        result = conn.exec_driver_sql(new_sql, new_params)
        last_id = result.lastrowid if hasattr(result, "lastrowid") else None
        if last_id:
            return int(last_id)
        try:
            return int(result.rowcount or 0)
        except Exception:
            return 0


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    engine = get_engine()
    payload = tuple(params)
    new_sql, new_params = _convert_qmark_sql(sql, payload)
    with engine.connect() as conn:
        result = conn.exec_driver_sql(new_sql, new_params)
        row = result.fetchone()
        return _row_to_dict(row) if row else None


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    engine = get_engine()
    payload = tuple(params)
    new_sql, new_params = _convert_qmark_sql(sql, payload)
    with engine.connect() as conn:
        result = conn.exec_driver_sql(new_sql, new_params)
        return [_row_to_dict(r) for r in result.fetchall()]


# ---------------------------------------------------------------------------
# get_conn() — legacy helper that hands routes a "DBAPI-cursor-like" handle.
# Backed by SQLAlchemy raw_connection so callers using ``conn.execute(...)``
# + ``cur.fetchone()`` keep working. The wrapper close() returns the underlying
# connection to the pool instead of physically closing it.
# ---------------------------------------------------------------------------


class _ConnWrapper:
    """Thin pymysql/sqlite3-compatible facade over ``engine.raw_connection()``."""

    def __init__(self, raw: Any, dialect: str) -> None:
        self._raw = raw
        self._dialect = dialect
        self.row_factory: Any = None  # ignored, kept for api parity

    def execute(self, sql: str, params: tuple | list = ()) -> "_CursorWrapper":
        new_sql, new_params = _convert_qmark_sql(sql, tuple(params))
        cur = self._raw.cursor()
        cur.execute(new_sql, new_params)
        return _CursorWrapper(cur)

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        # raw_connection.close() returns the conn to the pool (does NOT close
        # the underlying socket) — matches sqlite3.Connection.close() ergonomics.
        try:
            self._raw.close()
        except Exception:  # pragma: no cover
            pass

    def __enter__(self) -> "_ConnWrapper":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


class _CursorWrapper:
    """Cursor facade returning dict rows + exposing ``lastrowid``/``rowcount``."""

    def __init__(self, cur: Any) -> None:
        self._cur = cur

    def fetchone(self) -> dict | None:
        row = self._cur.fetchone()
        if row is None:
            return None
        return self._coerce_row(row)

    def fetchall(self) -> list[dict]:
        return [self._coerce_row(r) for r in self._cur.fetchall()]

    @property
    def lastrowid(self) -> int | None:
        return self._cur.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def _coerce_row(self, row: Any) -> dict:
        # pymysql cursor: tuple of values; description gives column names.
        if isinstance(row, dict):
            return {k: _normalize_value(v) for k, v in row.items()}
        if isinstance(row, sqlite3.Row):
            return {k: _normalize_value(row[k]) for k in row.keys()}
        cols = [c[0] for c in (self._cur.description or [])]
        return {col: _normalize_value(val) for col, val in zip(cols, row)}


def get_conn() -> "_ConnWrapper":
    """Return a sqlite-flavored connection wrapper backed by the SA pool."""
    engine = get_engine()
    raw = engine.raw_connection()
    return _ConnWrapper(raw, dialect=engine.dialect.name)


# ---------------------------------------------------------------------------
# init_db() — historical sqlite path used to create tables on import. With
# Alembic owning DDL we keep a no-op shell, plus a best-effort admin seed so
# fresh staging deployments still get a usable login. Errors stay non-fatal:
# /api/health surfaces DB outages, init_db() must not crash module import.
# ---------------------------------------------------------------------------


def init_db() -> None:
    """No-op for schema (Alembic owns it); best-effort seed admin user."""
    global _init_done
    if _init_done:
        return
    _init_done = True

    # Skip seed completely when the engine cannot be built (e.g. SQLAlchemy
    # not installed in current interpreter — sandbox path). Routes that don't
    # touch DB still load; auth routes will surface 5xx until DB is up.
    try:
        engine = get_engine()
    except Exception as exc:
        logger.warning("init_db: engine unavailable, skipping admin seed: %s", exc)
        return

    try:
        _seed_admin(engine)
    except Exception as exc:
        # Common during fresh deploys when Alembic hasn't run yet — log and move on.
        logger.warning("init_db: admin seed deferred (%s)", exc)


def _seed_admin(engine: Any) -> None:
    """Insert default admin user iff the table exists and admin is missing."""
    import secrets  # noqa: PLC0415

    with engine.connect() as conn:
        try:
            existing = conn.exec_driver_sql(
                "SELECT id FROM users WHERE phone = %s"
                if engine.dialect.name != "sqlite"
                else "SELECT id FROM users WHERE phone = ?",
                ("admin",),
            ).fetchone()
        except Exception as exc:
            logger.warning("admin seed skipped (users table not ready?): %s", exc)
            return
        if existing:
            return

    password = os.environ.get("ZHICE_ADMIN_PASSWORD", "").strip()
    if not password:
        password = secrets.token_urlsafe(16)
        logger.warning(
            "首次启动已创建管理员账户 admin，随机密码: %s  "
            "请立即登录后修改。或在 .env 中设置 ZHICE_ADMIN_PASSWORD 指定初始密码。",
            password,
        )

    from apps.api.auth.password import hash_password  # noqa: PLC0415

    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql(
                "INSERT INTO users(phone, password_hash, nickname, vip_level) VALUES (?,?,?,?)",
                ("admin", hash_password(password), "管理员", "pro"),
            )
        else:
            conn.exec_driver_sql(
                "INSERT INTO users(phone, password_hash, nickname, vip_level) VALUES (%s,%s,%s,%s)",
                ("admin", hash_password(password), "管理员", "pro"),
            )


# Trigger seed at import time (mirrors the legacy sqlite path); errors swallowed.
init_db()
