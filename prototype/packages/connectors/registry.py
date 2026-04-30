from __future__ import annotations

from functools import lru_cache

from .kpl.client import KplClient
from .xgt.client import XgtClient
from .tushare.client import TushareClient
from .etf.client import EastmoneyEtfClient
from .dfcf.client import DfcfClient


@lru_cache(maxsize=1)
def get_kpl() -> KplClient:
    from apps.api.config import settings

    return KplClient(
        user_id=settings.kpl_user_id,
        token=settings.kpl_token,
        device_id=settings.kpl_device_id,
        version=settings.kpl_version,
    )


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
