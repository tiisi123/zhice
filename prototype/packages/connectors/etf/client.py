from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_UT_TOKEN = "fa5fd1943c7b386f172d6893dbfba10b"
_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


def _infer_market(code: str) -> int:
    # Eastmoney secid: 1=SH, 0=SZ
    if code.startswith(("5", "6", "9")):
        return 1
    return 0


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


class EastmoneyEtfClient:
    def __init__(self):
        self._client = httpx.Client(timeout=12, verify=False, headers=_HEADERS)

    def get_daily_klines(self, code: str, limit: int = 14) -> list[dict[str, Any]]:
        secid = f"{_infer_market(code)}.{code}"
        params = {
            "secid": secid,
            "ut": _UT_TOKEN,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",  # 日线
            "fqt": "1",
            "lmt": str(limit),
            "beg": "0",
            "end": "20500101",
        }
        try:
            resp = self._client.get(_KLINE_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or {}
            klines = data.get("klines") or []
            result: list[dict[str, Any]] = []
            for row in klines:
                if not isinstance(row, str):
                    continue
                parts = row.split(",")
                if len(parts) < 11:
                    continue
                result.append(
                    {
                        "date": parts[0],
                        "open": _to_float(parts[1]),
                        "close": _to_float(parts[2]),
                        "high": _to_float(parts[3]),
                        "low": _to_float(parts[4]),
                        "volume": _to_float(parts[5]),  # 成交量
                        "amount": _to_float(parts[6]),  # 成交额
                        "amplitude": _to_float(parts[7]),
                        "change_pct": _to_float(parts[8]),
                        "change_abs": _to_float(parts[9]),
                        "turnover": _to_float(parts[10]),  # 换手率（%）
                    }
                )
            return result
        except Exception as e:
            logger.debug("ETF kline request failed for %s: %s", code, e)
            return []

    def close(self):
        self._client.close()
