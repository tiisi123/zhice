from __future__ import annotations

from functools import lru_cache

from .kpl.client import KplClient
from .kpl.history_client import KplHistoryClient
from .kpl.realtime_client import KplRealtimeClient
from .xgt.client import XgtClient
from .tushare.client import TushareClient
from .etf.client import EastmoneyEtfClient
from .dfcf.client import DfcfClient


def _read_kpl_cookie() -> str:
    """Best-effort lookup for the c1 shared KPL cookie.

    T03 will introduce `apps.api.cookie_provider.get_kpl_cookie()` backed by
    Fernet-decrypted system_secrets row. Until then this falls back to the
    KPL_COOKIE env var (read via settings if present) or empty string. An
    empty cookie causes the underlying client _post to short-circuit with
    sentinel `{"_error": "cookie_missing"}` instead of hitting upstream.
    """
    try:
        from apps.api.services.cookie_provider import get_kpl_cookie
    except Exception:
        get_kpl_cookie = None
    if get_kpl_cookie is not None:
        try:
            return get_kpl_cookie() or ""
        except Exception:
            return ""
    try:
        from apps.api.config import settings

        return getattr(settings, "kpl_cookie", "") or ""
    except Exception:
        return ""


@lru_cache(maxsize=1)
def get_kpl() -> KplClient:
    from apps.api.config import settings

    return KplClient(
        user_id=settings.kpl_user_id,
        token=settings.kpl_token,
        device_id=settings.kpl_device_id,
        version=settings.kpl_version,
        cookie=_read_kpl_cookie(),
    )


@lru_cache(maxsize=1)
def get_kpl_realtime() -> KplRealtimeClient:
    from apps.api.config import settings

    return KplRealtimeClient(
        cookie=_read_kpl_cookie(),
        user_id=settings.kpl_user_id,
        token=settings.kpl_token,
        device_id=settings.kpl_device_id,
        version=settings.kpl_version,
    )


@lru_cache(maxsize=1)
def get_kpl_history() -> KplHistoryClient:
    from apps.api.config import settings

    return KplHistoryClient(
        cookie=_read_kpl_cookie(),
        user_id=settings.kpl_user_id,
        token=settings.kpl_token,
        device_id=settings.kpl_device_id,
        version=settings.kpl_version,
    )


def clear_kpl_caches() -> None:
    """Evict cached KPL client singletons so the next call picks up a fresh cookie."""
    get_kpl.cache_clear()
    get_kpl_realtime.cache_clear()
    get_kpl_history.cache_clear()


@lru_cache(maxsize=1)
def get_xgt() -> XgtClient:
    return XgtClient()


@lru_cache(maxsize=1)
def get_tushare() -> TushareClient:
    return TushareClient()


@lru_cache(maxsize=1)
def get_etf() -> EastmoneyEtfClient:
    return EastmoneyEtfClient()


@lru_cache(maxsize=1)
def get_dfcf() -> DfcfClient:
    return DfcfClient()
