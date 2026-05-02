"""Fernet-encrypted KPL Cookie provider — single source of truth for system_secrets.

T03 (M001/S03). Owns the read/write path for the encrypted KPL Cookie persisted
in ``system_secrets``. Every read goes through a 30-second in-memory cache to
avoid hammering the DB on every short-line route call + APScheduler health
probe (≈ 2 reads/min from the scheduler alone).

Threading model
---------------
APScheduler health-probe jobs run on background threads; FastAPI request
handlers run on the ASGI thread. Cache mutations are guarded by
``_CACHE_LOCK`` so a probe and a request never tear the cache mid-write.

Failure modes
-------------
- ``ENCRYPTION_KEY`` empty in DEBUG → ``_fernet`` stays ``None`` so debug-mode
  imports still succeed. ``encrypt()`` raises RuntimeError; ``decrypt()`` and
  ``get_kpl_cookie()`` return '' (routes layer falls back to ``unavailable``).
- ``ENCRYPTION_KEY`` malformed in production → cryptography raises ValueError;
  caught here and re-raised as RuntimeError with a generator hint. Empty key
  in production is already blocked by ``Settings.validate_required_secrets``.
- Fernet ``InvalidToken`` on decrypt → ``logger.exception`` + return ''. Routes
  hit the ``unavailable`` contract path; we never crash a request because of a
  rotated/wrong key.
- DB unreachable → return last cached value (so a transient outage does not
  knock all KPL routes off mid-session); '' on cold cache.

Redaction
---------
``logger.info`` only emits ``user_id`` and ``len(cookie)`` — never the
plaintext or ciphertext secret. ``get_kpl_cookie_metadata()`` returns
``has_cookie`` boolean only; secret_value is *never* serialized to API
responses.
"""
from __future__ import annotations

import logging
import threading
import time

from cryptography.fernet import Fernet, InvalidToken

from apps.api.config import settings

logger = logging.getLogger("zhice.api.services.cookie_provider")

# 30-second TTL: long enough to coalesce burst reads (single short-line page
# load may fan out ~6 KPL calls), short enough that a cookie paste in /admin
# propagates to scheduler probes within one cycle.
_TTL_SECONDS: float = 30.0

_CACHE_LOCK = threading.Lock()
# {secret_key: (plaintext, expires_at_unix)}
_CACHE: dict[str, tuple[str, float]] = {}


def _build_fernet() -> Fernet | None:
    """Initialize Fernet at import time. Empty key + debug → None; bad key → raise."""
    key = settings.encryption_key
    if not key:
        if settings.debug:
            logger.warning(
                "ENCRYPTION_KEY 未设置（DEBUG 模式继续，加密功能不可用）。"
            )
            return None
        # Production: validate_required_secrets should have already raised.
        # If we reach here something bypassed it — still raise to fail fast.
        raise RuntimeError(
            "ENCRYPTION_KEY 未设置，cookie_provider 无法初始化 Fernet。"
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        if settings.debug:
            logger.warning(
                "ENCRYPTION_KEY 格式无效（DEBUG 模式继续，加密功能不可用）：%s", exc
            )
            return None
        raise RuntimeError(
            "ENCRYPTION_KEY 格式无效，无法初始化 Fernet: "
            f"{exc}. 请使用 cryptography.fernet.Fernet.generate_key() 生成 "
            "32-byte url-safe base64 key。"
        ) from exc


_fernet: Fernet | None = _build_fernet()


def encrypt(plain: str) -> str:
    """Encrypt ``plain`` with the module-level Fernet; raise if uninitialized."""
    if _fernet is None:
        raise RuntimeError(
            "Fernet 未初始化（ENCRYPTION_KEY 缺失或格式错），无法加密。"
        )
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(cipher: str) -> str:
    """Decrypt ``cipher``. Empty input or InvalidToken → '' (logged)."""
    if not cipher or _fernet is None:
        return ""
    try:
        return _fernet.decrypt(cipher.encode()).decode()
    except InvalidToken:
        logger.exception("system_secrets decrypt failed (InvalidToken)")
        return ""


def get_kpl_cookie() -> str:
    """Return the decrypted KPL cookie text; '' if missing/unavailable.

    Cache hits short-circuit the DB; misses populate the cache and refresh
    the TTL. On DB error, falls back to the last cached value if any (so a
    transient outage does not knock all KPL routes into ``unavailable``);
    cold cache + DB error returns ''.
    """
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get("kpl_cookie")
    if cached and cached[1] > now:
        return cached[0]

    try:
        from apps.api.db import query_one  # local import: avoid SA at module load

        row = query_one(
            "SELECT secret_value FROM system_secrets WHERE secret_key=?",
            ("kpl_cookie",),
        )
        cipher = str((row or {}).get("secret_value") or "")
    except Exception:
        logger.exception("get_kpl_cookie DB SELECT failed")
        return cached[0] if cached else ""

    plain = decrypt(cipher)
    with _CACHE_LOCK:
        _CACHE["kpl_cookie"] = (plain, time.time() + _TTL_SECONDS)
    return plain


def set_kpl_cookie(cookie: str, updated_by: int | None = None) -> None:
    """Encrypt + UPDATE + invalidate cache. Called by /admin/kpl-cookie POST.

    The migration seeded ``secret_key='kpl_cookie'`` on upgrade so this is
    always a pure UPDATE — no INSERT branch, no race between two admins.
    """
    cipher = encrypt(cookie)
    from apps.api.db import execute  # local import: avoid SA at module load

    execute(
        "UPDATE system_secrets SET secret_value=?, updated_at=CURRENT_TIMESTAMP, "
        "updated_by=? WHERE secret_key='kpl_cookie'",
        (cipher, updated_by),
    )
    with _CACHE_LOCK:
        _CACHE["kpl_cookie"] = (cookie, time.time() + _TTL_SECONDS)
    logger.info(
        "kpl_cookie updated by user_id=%s len=%d", updated_by, len(cookie)
    )
    try:
        from packages.connectors.registry import clear_kpl_caches
        clear_kpl_caches()
    except ImportError:
        pass


def get_kpl_cookie_metadata() -> dict:
    """Non-sensitive metadata for /admin/kpl-cookie GET. Never returns secret_value.

    Returns
    -------
    dict
        ``has_cookie`` — bool, whether ciphertext is non-empty.
        ``last_updated_at`` — ISO string or None.
        ``updated_by`` — admin user_id or None (None for migration seed row).
    """
    try:
        from apps.api.db import query_one  # local import: avoid SA at module load

        row = query_one(
            "SELECT secret_value, updated_at, updated_by FROM system_secrets "
            "WHERE secret_key=?",
            ("kpl_cookie",),
        )
    except Exception:
        logger.exception("get_kpl_cookie_metadata DB failed")
        return {"has_cookie": False, "last_updated_at": None, "updated_by": None}

    if not row:
        return {"has_cookie": False, "last_updated_at": None, "updated_by": None}

    return {
        "has_cookie": bool(row.get("secret_value")),
        "last_updated_at": (str(row.get("updated_at")) if row.get("updated_at") else None),
        "updated_by": row.get("updated_by"),
    }


def _reset_cache_for_tests() -> None:
    """Clear the in-memory cache. Test-only — exposed for fixture isolation."""
    with _CACHE_LOCK:
        _CACHE.clear()
