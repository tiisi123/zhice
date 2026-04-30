from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_BASE_HOST = "https://flash-api.xuangubao.com.cn"

_HEADERS = {
    "authority": "flash-api.xuangubao.com.cn",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://xuangutong.com.cn",
    "sec-ch-ua-platform": '"Windows"',
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.5845.97 Safari/537.36"
    ),
}

_POOL_URL = f"{_BASE_HOST}/api/pool/detail"
_HOT_STOCKS_URL = f"{_BASE_HOST}/api/surge_stock/stocks"
_HOT_PLATES_URL = f"{_BASE_HOST}/api/surge_stock/plates"


def _ts_to_time(ts: int | float | None) -> str | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    except (ValueError, OSError):
        return None


class XgtClient:
    _MAX_RETRIES = 2

    def __init__(self):
        self._client = httpx.Client(timeout=15, verify=False, headers=_HEADERS)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 60.0

    def _get(self, url: str, params: dict | None = None) -> dict:
        import time
        cache_key = f"{url}:{sorted((params or {}).items())}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1]
        last_err = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                resp = self._client.get(url, params=params or {})
                resp.raise_for_status()
                result = resp.json()
                self._cache[cache_key] = (time.time(), result)
                return result
            except Exception as e:
                last_err = e
                if attempt < self._MAX_RETRIES:
                    time.sleep(0.5 * attempt)
        logger.warning("XGT request failed after %d retries: %s -> %s",
                       self._MAX_RETRIES, url.split("/")[-1], last_err)
        return cached[1] if cached else {}

    def _get_pool(self, pool_name: str, trade_date: Optional[str] = None) -> list[dict]:
        params = {"pool_name": pool_name}
        if trade_date:
            params["date"] = trade_date
        data = self._get(_POOL_URL, params)
        result = self._parse_pool(data)
        if not result and trade_date:
            data = self._get(_POOL_URL, {"pool_name": pool_name})
            result = self._parse_pool(data)
        return result

    def get_limit_up(self, trade_date: Optional[str] = None) -> list[dict]:
        return self._get_pool("limit_up", trade_date)

    def get_broken(self, trade_date: Optional[str] = None) -> list[dict]:
        return self._get_pool("limit_up_broken", trade_date)

    def get_hot_stocks(self, trade_date: Optional[str] = None) -> list[dict]:
        params = {"normal": "true", "uplimit": "true"}
        if trade_date:
            params["date"] = trade_date
        raw = self._get(_HOT_STOCKS_URL, params)
        container = raw.get("data") or {}
        if isinstance(container, list):
            rows, fields = container, []
        else:
            fields = container.get("fields") or []
            rows = container.get("items") or []
        result = []
        for row in rows:
            if isinstance(row, list):
                item = dict(zip(fields, row)) if fields else {}
            elif isinstance(row, dict):
                item = row
            else:
                continue
            symbol = str(item.get("code") or item.get("symbol", ""))
            code = symbol.split(".")[0] if "." in symbol else symbol[:6]
            plates = item.get("plates") or []
            first_plate = ""
            if plates and isinstance(plates[0], dict):
                first_plate = plates[0].get("name") or plates[0].get("plate_name", "")
            result.append({
                "stock_code": code,
                "stock_name": item.get("prod_name") or item.get("stock_chi_name", ""),
                "plate_name": first_plate,
                "reason": item.get("description") or (item.get("surge_reason") or {}).get("stock_reason", ""),
                "change_rate": round((item.get("px_change_rate") or item.get("change_percent", 0) or 0) * 100, 2),
                "turnover_ratio": round((item.get("turnover_ratio", 0) or 0) * 100, 2),
                "time": _ts_to_time(item.get("enter_time")),
            })
        return result

    def get_hot_plates(self, trade_date: Optional[str] = None) -> list[dict]:
        params = {}
        if trade_date:
            params["date"] = trade_date
        data = self._get(_HOT_PLATES_URL, params)
        return data.get("data") or []

    @staticmethod
    def _parse_pool(data: dict) -> list[dict]:
        items = data.get("data") or []
        result = []
        for item in items:
            symbol = str(item.get("symbol") or item.get("stock_code", ""))
            code = symbol.split(".")[0] if "." in symbol else symbol[:6]
            surge = item.get("surge_reason") or {}
            related = surge.get("related_plates") or []
            plate_names = [p.get("plate_name", "") for p in related if isinstance(p, dict)]
            time_ts = (
                item.get("last_limit_up")
                or item.get("last_break_limit_up")
                or surge.get("last_limit_up_time")
                or surge.get("open_limit_down_time")
            )
            result.append({
                "stock_code": code,
                "stock_name": item.get("stock_chi_name", ""),
                "change_rate": round((item.get("change_percent") or item.get("px_change_rate", 0) or 0) * 100, 2),
                "turnover_ratio": round((item.get("turnover_ratio", 0) or 0) * 100, 2),
                "reason": surge.get("stock_reason", ""),
                "combined_reason": surge.get("stock_reason", ""),
                "related_plates": plate_names,
                "first_plate_name": plate_names[0] if plate_names else "",
                "time": _ts_to_time(time_ts),
                "board_count": item.get("limit_up_days", 0),
                "non_restricted_capital": item.get("non_restricted_capital", 0),
                "total_capital": item.get("total_capital", 0),
            })
        return result

    def close(self):
        self._client.close()


if __name__ == "__main__":
    client = XgtClient()
    broken = client.get_broken()
    print(f"broken: {len(broken)} stocks")
    if broken:
        print(broken[0])

    limit_up = client.get_limit_up()
    print(f"limit_up: {len(limit_up)} stocks")

    hot = client.get_hot_stocks()
    print(f"hot_stocks: {len(hot)} stocks")
    client.close()
