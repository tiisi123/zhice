from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import httpx

from .endpoints import (
    KPL_HISTORY_HOST,
    KPL_MERGE_HOST,
    KPL_REALTIME_HOST,
    HOST_MAP,
)

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 6.0.1; MI 6 Build/V417IR)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}

_EM_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://quote.eastmoney.com/ztb/detail",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/109.0.0.0 Safari/537.36"
    ),
}

_EM_ZT_POOL_URL = "https://push2ex.eastmoney.com/getTopicZTPool"
_EM_ZB_POOL_URL = "https://push2ex.eastmoney.com/getTopicZBPool"
_EM_HOT_RANK_URL = "https://emappdata.eastmoney.com/stockrank/getAllCurrentList"
_EM_QUOTE_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get"


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        text = str(value).strip().replace("%", "").replace(",", "")
        if not text or text == "--":
            return 0.0
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _to_amount(value) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "")
    if not text or text == "--":
        return 0.0
    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 1e8
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 1e4
        text = text[:-1]
    try:
        return float(text) * multiplier
    except ValueError:
        return 0.0


def _format_em_date(date_str: Optional[str]) -> str:
    if not date_str:
        return datetime.now().strftime("%Y%m%d")
    text = str(date_str).strip()
    if len(text) == 8 and text.isdigit():
        return text
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y%m%d")
    except ValueError:
        return datetime.now().strftime("%Y%m%d")


def _em_time(value) -> str | None:
    if value in (None, "", "--"):
        return None
    text = str(value).split(".")[0].zfill(6)
    if not text.isdigit():
        return None
    return f"{text[:2]}:{text[2:4]}:{text[4:6]}"


def _em_price(value) -> float:
    price = _to_float(value)
    return round(price / 1000, 2) if price > 1000 else price


class KplClient:
    def __init__(
        self,
        user_id: str = "",
        token: str = "",
        device_id: str = "",
        version: str = "10.1.1",
    ):
        self.user_id = user_id
        self.token = token
        self.device_id = device_id
        self.version = version
        self._client = httpx.Client(timeout=15, verify=False)

    def _headers(self, host_key: str = "realtime") -> dict:
        h = _DEFAULT_HEADERS.copy()
        h["Host"] = HOST_MAP.get(host_key, HOST_MAP["realtime"])
        return h

    def _post(self, url: str, data: dict, host_key: str = "realtime") -> dict:
        if not self.user_id and not self.device_id:
            logger.warning("KPL credentials not configured, returning empty data")
            return {}
        try:
            resp = self._client.post(url, data=data, headers=self._headers(host_key))
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("KPL request failed: %s %s -> %s", url, data.get("a", ""), e)
            return {}

    def _get_public_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        try:
            resp = self._client.get(url, params=params or {}, headers=headers or _EM_HEADERS)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("KPL public GET failed: %s -> %s", url, e)
            return {}

    def _post_public_json(self, url: str, json_data: dict, headers: dict | None = None) -> dict:
        try:
            resp = self._client.post(url, json=json_data, headers=headers or _EM_HEADERS)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("KPL public POST failed: %s -> %s", url, e)
            return {}

    def _base_params(self, **extra) -> dict:
        params = {
            "PhoneOSNew": "1",
            "DeviceID": self.device_id,
            "VerSion": self.version,
            "apiv": "w38",
        }
        params.update(extra)
        return params

    def _is_today(self, date_str: Optional[str]) -> bool:
        if not date_str:
            return True
        return date_str == datetime.now().strftime("%Y-%m-%d")

    # --- Phase 1 核心接口 ---

    def get_market_statistics(self, trade_date: str) -> list[dict]:
        data = self._base_params(
            a="MarketStatistics",
            c="HisHomeDingPan",
            Day=trade_date,
        )
        result = self._post(KPL_HISTORY_HOST, data, "history")
        info = result.get("info")
        if not info:
            return []

        row = {f"market_{k.lower()}": v for k, v in info.items()}

        strong_data = self._base_params(
            a="DiskReview",
            c="HisHomeDingPan",
            Day=trade_date,
        )
        strong_resp = self._post(KPL_HISTORY_HOST, strong_data, "history")
        strong_info = strong_resp.get("info", {})
        row["market_strong"] = strong_info.get("strong", 0)
        return [row]

    def get_concept_selected(
        self, trade_date: Optional[str] = None, index: int = 0, order: str = "0"
    ) -> list[dict]:
        is_today = self._is_today(trade_date)
        data = self._base_params(
            a="ConceptSelected",
            c="HomeDingPan" if is_today else "HisHomeDingPan",
            Order=order,
            st="20",
            Index=str(index),
        )
        if not is_today and trade_date:
            data["Date"] = trade_date
        host = "realtime" if is_today else "history"
        return self._post(
            KPL_REALTIME_HOST if is_today else KPL_HISTORY_HOST, data, host
        ).get("list", [])

    def get_concept_detail(
        self,
        plate_id: str,
        trade_date: Optional[str] = None,
        index: int = 0,
    ) -> list[dict]:
        is_today = self._is_today(trade_date)
        data = self._base_params(
            a="ConceptDetail",
            c="HomeDingPan" if is_today else "HisHomeDingPan",
            PlateID=plate_id,
            Order="0",
            st="60",
            Index=str(index),
        )
        if not is_today and trade_date:
            data["Date"] = trade_date
        host = "realtime" if is_today else "history"
        return self._post(
            KPL_REALTIME_HOST if is_today else KPL_HISTORY_HOST, data, host
        ).get("list", [])

    def get_concept_subsection(
        self, plate_id: str, trade_date: Optional[str] = None
    ) -> list[dict]:
        is_today = self._is_today(trade_date)
        data = self._base_params(
            a="ConceptSubsection",
            c="HomeDingPan" if is_today else "HisHomeDingPan",
            PlateID=plate_id,
            IsShow="1",
        )
        if not is_today and trade_date:
            data["Date"] = trade_date
        host = "realtime" if is_today else "history"
        return self._post(
            KPL_REALTIME_HOST if is_today else KPL_HISTORY_HOST, data, host
        ).get("list", [])

    def get_limit_performance(
        self, trade_date: str, daily_limit: bool = True, order: str = "0"
    ) -> list[dict]:
        data = self._base_params(
            a="DailyLimitPerformance" if daily_limit else "DailyLimitPerformance2",
            c="HisHomeDingPan",
            Order=order,
            st="20",
            Day=trade_date,
        )
        return self._post(KPL_HISTORY_HOST, data, "history").get("list", [])

    def get_theme_list(self, trade_date: str) -> list[dict]:
        data = self._base_params(
            a="HomeThemeList",
            c="HisHomeDingPan",
        )
        result = self._post(KPL_HISTORY_HOST, data, "history")
        return result.get("list", [])

    def get_theme_detail(self, theme_id: str) -> dict:
        data = self._base_params(
            a="HomeThemeDetail",
            c="HomeDingPan",
            ID=theme_id,
            Token=self.token,
            UserID=self.user_id,
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    def get_market_anomaly(self, trade_date: Optional[str] = None) -> list[dict]:
        is_today = self._is_today(trade_date)
        data = self._base_params(
            a="MarketAnomaly",
            c="HomeDingPan" if is_today else "HisHomeDingPan",
            Index="0",
            st="100",
        )
        if not is_today and trade_date:
            data["Date"] = trade_date
        host = "realtime" if is_today else "history"
        return self._post(
            KPL_REALTIME_HOST if is_today else KPL_HISTORY_HOST, data, host
        ).get("list", [])

    def _get_em_pool(self, url: str, trade_date: Optional[str] = None) -> list[dict]:
        params = {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": "0",
            "pagesize": "170",
            "sort": "fbt:asc",
            "date": _format_em_date(trade_date),
            "_": int(time.time() * 1000),
        }
        raw = self._get_public_json(url, params)
        pool = (raw.get("data") or {}).get("pool") or []
        return [self._parse_em_pool_item(row) for row in pool if isinstance(row, dict)]

    @staticmethod
    def _parse_em_pool_item(row: dict) -> dict:
        industry = row.get("hybk") or row.get("industry") or ""
        concepts = row.get("gn") or row.get("concepts") or row.get("related_plates") or []
        if isinstance(concepts, str):
            related = [x.strip() for x in concepts.replace("、", ",").split(",") if x.strip()]
        elif isinstance(concepts, list):
            related = [
                str(x.get("name") or x.get("plate_name") or x).strip()
                for x in concepts
                if x
            ]
        else:
            related = []
        if industry and industry not in related:
            related.insert(0, str(industry))

        reason = (
            row.get("reason")
            or row.get("ztly")
            or row.get("ztyy")
            or row.get("brief")
            or row.get("desc")
            or ""
        )
        board_count = row.get("lbc") or row.get("board_count") or 0
        try:
            board_count = int(float(board_count))
        except (TypeError, ValueError):
            board_count = 0

        return {
            "stock_code": str(row.get("c") or row.get("stock_code") or "")[:6],
            "stock_name": row.get("n") or row.get("stock_name") or "",
            "price": _em_price(row.get("p") or row.get("price")),
            "change_rate": _to_float(row.get("zdp") or row.get("change_rate")),
            "turnover_ratio": _to_float(row.get("hs") or row.get("turnover_ratio")),
            "reason": reason,
            "combined_reason": reason,
            "related_plates": related,
            "first_plate_name": related[0] if related else "",
            "time": _em_time(row.get("lbt") or row.get("fbt") or row.get("time")),
            "first_limit_time": _em_time(row.get("fbt")),
            "last_limit_time": _em_time(row.get("lbt")),
            "board_count": board_count,
            "open_count": int(_to_float(row.get("zbc") or 0)),
            "seal_amount": _to_amount(row.get("fund")),
            "non_restricted_capital": _to_amount(row.get("ltsz")),
            "total_capital": _to_amount(row.get("tshare") or row.get("total_capital")),
        }

    def get_limit_up(self, trade_date: Optional[str] = None) -> list[dict]:
        return self._get_em_pool(_EM_ZT_POOL_URL, trade_date)

    def get_broken(self, trade_date: Optional[str] = None) -> list[dict]:
        return self._get_em_pool(_EM_ZB_POOL_URL, trade_date)

    def get_hot_stocks(self, trade_date: Optional[str] = None) -> list[dict]:
        rank_headers = {
            **_EM_HEADERS,
            "Content-Type": "application/json",
            "Origin": "https://vipmoney.eastmoney.com",
            "Referer": "https://vipmoney.eastmoney.com/",
        }
        rank_raw = self._post_public_json(
            _EM_HOT_RANK_URL,
            {
                "appId": "appId01",
                "globalId": "786e4c21-70dc-435a-93bb-38",
                "marketType": "",
                "pageNo": 1,
                "pageSize": 100,
            },
            rank_headers,
        )
        rank_rows = rank_raw.get("data") or []
        secids: list[str] = []
        rank_by_code: dict[str, int] = {}
        for idx, row in enumerate(rank_rows, start=1):
            sc = str((row or {}).get("sc") or "")
            if sc.startswith("SZ"):
                code = sc[2:8]
                secid = f"0.{code}"
            elif sc.startswith("SH"):
                code = sc[2:8]
                secid = f"1.{code}"
            else:
                continue
            secids.append(secid)
            rank_by_code[code] = idx
        if not secids:
            return []

        quote_raw = self._get_public_json(
            _EM_QUOTE_URL,
            {
                "ut": "f057cbcbce2a86e2866ab8877db1d059",
                "fltt": "2",
                "invt": "2",
                "fields": "f14,f148,f3,f12,f2,f13,f29",
                "secids": ",".join(secids),
            },
            rank_headers,
        )
        rows = (quote_raw.get("data") or {}).get("diff") or []
        result: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = str(row.get("f12") or "")[:6]
            if not code:
                continue
            result.append({
                "stock_code": code,
                "stock_name": row.get("f14") or "",
                "plate_name": "",
                "reason": "",
                "combined_reason": "",
                "related_plates": [],
                "first_plate_name": "",
                "change_rate": _to_float(row.get("f3")),
                "turnover_ratio": _to_float(row.get("f148")),
                "price": _to_float(row.get("f2")),
                "hot_rank": rank_by_code.get(code),
                "time": None,
            })
        result.sort(key=lambda x: x.get("hot_rank") or 9999)
        return result

    def get_longhu_stocks(
        self,
        trade_date: Optional[str] = None,
        index: int = 0,
        size: int = 500,
    ) -> list[dict]:
        """KPL 游资龙虎榜股票列表，含买入/卖出/做 T 席位标签。"""
        data = self._base_params(
            a="GetStockList",
            c="LongHuBang",
            st=str(size),
            Index=str(index),
            Type="2",
            Time=trade_date or datetime.now().strftime("%Y-%m-%d"),
            Token=self.token,
            UserID=self.user_id,
        )
        raw = self._post(KPL_MERGE_HOST, data, "merge")
        rows = raw.get("list") or []
        buy_icons = raw.get("BIcon") or {}
        sell_icons = raw.get("SIcon") or {}
        t_icons = raw.get("TIcon") or {}
        concepts = raw.get("fkgn") or {}

        result: list[dict] = []
        for row in rows:
            code = str(row.get("ID") or row.get("stock_code") or "")[:6]
            if not code:
                continue
            result.append({
                "stock_code": code,
                "stock_name": row.get("Name") or row.get("stock_name") or "",
                "change_rate": _to_float(row.get("IncreaseAmount")),
                "net_amount": _to_amount(row.get("BuyIn")),
                "join_num": _to_float(row.get("JoinNum")),
                "amount": _to_amount(row.get("Turnover")),
                "float_mv": _to_amount(row.get("CircPrice")),
                "turnover_ratio": _to_float(row.get("TurnoverRatio")),
                "total_mv": _to_amount(row.get("Capitalization")),
                "buy_seats": buy_icons.get(code, []) if isinstance(buy_icons, dict) else [],
                "sell_seats": sell_icons.get(code, []) if isinstance(sell_icons, dict) else [],
                "t_seats": t_icons.get(code, []) if isinstance(t_icons, dict) else [],
                "concepts": list((concepts.get(code, {}) or {}).values()) if isinstance(concepts, dict) else [],
            })
        return result

    def close(self):
        self._client.close()


if __name__ == "__main__":
    import os, sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
    client = KplClient()
    today = datetime.now().strftime("%Y-%m-%d")
    result = client.get_market_statistics(today)
    print(f"market_statistics: {len(result)} rows")
    if result:
        print(list(result[0].keys())[:10])
    client.close()
