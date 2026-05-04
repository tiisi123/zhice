from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional

import httpx

from .endpoints import (
    HOST_MAP,
    KPL_HISTORY_HOST,
    KPL_MERGE_HOST,
    KPL_REALTIME_HOST,
)
from .history_client import KplHistoryClient
from .realtime_client import KplRealtimeClient

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


def _is_sentinel(resp) -> bool:
    return isinstance(resp, dict) and bool(resp.get("_error"))


def _extract_list(resp) -> list:
    if not isinstance(resp, dict) or _is_sentinel(resp):
        return []
    return resp.get("list", []) or []


class KplClient:
    """c1 facade: shared DeviceID across realtime/history/merge hosts.

    KPL authenticates via DeviceID in POST body, not HTTP cookies.
    Constructs internal KplRealtimeClient + KplHistoryClient with the same
    credentials. Legacy 9-method signatures are preserved by delegating to
    the appropriate split client based on whether trade_date is today.
    """

    def __init__(
        self,
        user_id: str = "",
        token: str = "",
        device_id: str = "",
        version: str = "5.17.0.0",
        cookie: str = "",
    ):
        self.user_id = user_id
        self.token = token
        self.device_id = device_id
        self.version = version
        self.cookie = cookie or ""
        self._realtime = KplRealtimeClient(
            cookie=self.cookie,
            user_id=user_id,
            token=token,
            device_id=device_id,
            version=version,
        )
        self._history = KplHistoryClient(
            cookie=self.cookie,
            user_id=user_id,
            token=token,
            device_id=device_id,
            version=version,
        )
        # Merge host (LongHuBang + 公开 EM API) keeps its own httpx.Client
        self._client = httpx.Client(timeout=15, verify=False)
        # T07 sentinel surface: routes layer reads `.last_error` /
        # `.last_http_code` after each KPL-touching call to decide whether to
        # short-circuit into wrap_contract status='unavailable'. Cleared on
        # any non-sentinel response so a recovered call drops the unavailable
        # state on the next request.
        self.last_error: Optional[str] = None
        self.last_http_code: Optional[int] = None

    def _headers(self, host_key: str = "merge") -> dict:
        h = _DEFAULT_HEADERS.copy()
        h["Host"] = HOST_MAP.get(host_key, HOST_MAP["merge"])
        return h

    def _post(self, url: str, data: dict, host_key: str = "merge") -> dict:
        try:
            resp = self._client.post(url, data=data, headers=self._headers(host_key))
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            http_code = e.response.status_code if e.response is not None else 0
            logger.warning(
                "KPL merge upstream %s: endpoint=%s a=%s",
                http_code,
                url,
                data.get("a", ""),
            )
            return {"_error": "kpl_upstream_error", "http_code": http_code}
        except Exception as e:
            logger.warning(
                "KPL merge request failed: endpoint=%s a=%s -> %s",
                url,
                data.get("a", ""),
                e,
            )
            return {}

    def _get_public_json(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> dict:
        try:
            resp = self._client.get(
                url, params=params or {}, headers=headers or _EM_HEADERS
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("KPL public GET failed: %s -> %s", url, e)
            return {}

    def _post_public_json(
        self, url: str, json_data: dict, headers: dict | None = None
    ) -> dict:
        try:
            resp = self._client.post(
                url, json=json_data, headers=headers or _EM_HEADERS
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("KPL public POST failed: %s -> %s", url, e)
            return {}

    def _is_today(self, date_str: Optional[str]) -> bool:
        if not date_str:
            return True
        return date_str == datetime.now().strftime("%Y-%m-%d")

    def _record(self, resp):
        """Update ``last_error`` / ``last_http_code`` from a raw sub-client response.

        Sets the attributes when ``resp`` is a sentinel dict (has ``_error``)
        and clears them otherwise. Routes layer reads these to convert the
        latest call into a ``status='unavailable'`` contract response without
        threading raw responses through the legacy 9-method signatures.

        Always returns ``resp`` unchanged so call sites can chain it
        (``resp = self._record(self._history.foo(...))``).
        """
        if isinstance(resp, dict) and resp.get("_error"):
            self.last_error = resp.get("_error")
            self.last_http_code = resp.get("http_code")
        else:
            self.last_error = None
            self.last_http_code = None
        return resp

    # --- legacy 9-method signature delegation ---

    def get_market_statistics(self, trade_date: str) -> list[dict]:
        resp = self._record(self._history.get_market_statistics(trade_date))
        if _is_sentinel(resp):
            return []
        info = resp.get("info") if isinstance(resp, dict) else None
        if not info:
            return []
        row = {f"market_{k.lower()}": v for k, v in info.items()}
        # 二次 DiskReview 拿 strong 字段 (legacy behavior preserved)
        strong_resp = self._history._post(
            KPL_HISTORY_HOST,
            self._history._base_params(
                a="DiskReview",
                c="HisHomeDingPan",
                Day=trade_date,
            ),
            "history",
        )
        if isinstance(strong_resp, dict) and not _is_sentinel(strong_resp):
            row["market_strong"] = (strong_resp.get("info") or {}).get("strong", 0)
        return [row]

    def get_concept_selected(
        self, trade_date: Optional[str] = None, index: int = 0, order: str = "0"
    ) -> list[dict]:
        try:
            order_int = int(order)
        except (TypeError, ValueError):
            order_int = 0
        if self._is_today(trade_date):
            resp = self._realtime.get_concept_selected(index=index, order=order_int)
            if _is_sentinel(resp):
                day = trade_date or datetime.now().strftime("%Y-%m-%d")
                resp = self._history.get_concept_selected_history(day, index=index)
        else:
            resp = self._history.get_concept_selected_history(trade_date, index=index)
        if _is_sentinel(resp):
            fallback = self._sectors_from_ranking(index=index, order=order_int)
            if fallback:
                self._record(None)
                return fallback
        self._record(resp)
        return _extract_list(resp)

    def _sectors_from_ranking(self, index: int = 0, order: int = 0) -> list[dict]:
        """Fallback: convert RealRankingInfo array rows into ConceptSelected-like dicts."""
        resp = self._realtime.get_sectors_realtime(index=index, order=order)
        if _is_sentinel(resp):
            return []
        rows = resp.get("list") or []
        result = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 10:
                continue
            result.append({
                "PlateID": str(row[0]) if row[0] else "",
                "PlateName": str(row[1]) if row[1] else "",
                "concept_name": str(row[1]) if row[1] else "",
                "ChangePercent": float(row[3]) if row[3] is not None else 0.0,
                "concept_increase": float(row[3]) if row[3] is not None else 0.0,
                "Intensity": float(row[9]) if row[9] is not None else 0.0,
                "concept_intensity": float(row[9]) if row[9] is not None else 0.0,
                "Amount": float(row[5]) if row[5] is not None else 0.0,
                "concept_amount": float(row[5]) if row[5] is not None else 0.0,
                "MainForce": float(row[8]) if row[8] is not None else 0.0,
                "concept_net_amount": float(row[8]) if row[8] is not None else 0.0,
            })
        return result

    def get_concept_detail(
        self,
        plate_id: str,
        trade_date: Optional[str] = None,
        index: int = 0,
    ) -> list[dict]:
        if self._is_today(trade_date):
            resp = self._realtime.get_concept_detail(plate_id, index=index)
            if _is_sentinel(resp):
                day = trade_date or datetime.now().strftime("%Y-%m-%d")
                resp = self._history.get_concept_detail_history(
                    plate_id, day, index=index
                )
        else:
            resp = self._history.get_concept_detail_history(
                plate_id, trade_date, index=index
            )
        self._record(resp)
        return _extract_list(resp)

    def get_concept_subsection(
        self, plate_id: str, trade_date: Optional[str] = None
    ) -> list[dict]:
        if self._is_today(trade_date):
            resp = self._realtime.get_concept_subsection(plate_id)
            self._record(resp)
            if _is_sentinel(resp):
                return []
            return _extract_list(resp)
        return []

    def get_limit_performance(
        self, trade_date: str, daily_limit: bool = True, order: str = "0"
    ) -> list[dict]:
        try:
            order_int = int(order)
        except (TypeError, ValueError):
            order_int = 0
        resp = self._record(
            self._history.get_limit_performance(
                trade_date, daily_limit=daily_limit, order=order_int
            )
        )
        return _extract_list(resp)

    def get_theme_list(self, trade_date: str) -> list[dict]:
        resp = self._record(self._history.get_theme_list(trade_date))
        return _extract_list(resp)

    def get_theme_detail(self, theme_id: str) -> dict:
        data = self._realtime._base_params(
            a="HomeThemeDetail",
            c="HomeDingPan",
            ID=theme_id,
            Token=self.token,
            UserID=self.user_id,
        )
        # Theme detail is realtime endpoint — delegate via realtime _post
        resp = self._record(self._realtime._post(KPL_REALTIME_HOST, data, "realtime"))
        if _is_sentinel(resp):
            return {}
        return resp if isinstance(resp, dict) else {}

    def get_market_anomaly(self, trade_date: Optional[str] = None) -> list[dict]:
        if not self._is_today(trade_date):
            # daban_pc historical Radar 不开放，返 [] 安全
            return []
        resp = self._record(self._realtime.get_market_anomaly())
        return _extract_list(resp)

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
            related = [
                x.strip() for x in concepts.replace("、", ",").split(",") if x.strip()
            ]
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
        # Eastmoney public — no cookie path. Clear sentinel state so stale
        # KPL last_error from a prior call does not leak into routes that
        # combine this with KPL data (e.g. replay /summary).
        self._record(None)
        return self._get_em_pool(_EM_ZT_POOL_URL, trade_date)

    def get_broken(self, trade_date: Optional[str] = None) -> list[dict]:
        self._record(None)
        return self._get_em_pool(_EM_ZB_POOL_URL, trade_date)

    def get_hot_stocks(self, trade_date: Optional[str] = None) -> list[dict]:
        self._record(None)
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
            result.append(
                {
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
                }
            )
        result.sort(key=lambda x: x.get("hot_rank") or 9999)
        return result

    def get_longhu_stocks(
        self,
        trade_date: Optional[str] = None,
        index: int = 0,
        size: int = 500,
    ) -> list[dict]:
        """KPL 游资龙虎榜股票列表，含买入/卖出/做 T 席位标签。merge host (applhb)."""
        data = {
            "PhoneOSNew": "1",
            "DeviceID": self.device_id,
            "VerSion": self.version,
            "apiv": "w38",
            "a": "GetStockList",
            "c": "LongHuBang",
            "st": str(size),
            "Index": str(index),
            "Type": "2",
            "Time": trade_date or datetime.now().strftime("%Y-%m-%d"),
            "Token": self.token or "0",
            "UserID": self.user_id or "0",
        }
        raw = self._record(self._post(KPL_MERGE_HOST, data, "merge"))
        if _is_sentinel(raw):
            return []
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
            result.append(
                {
                    "stock_code": code,
                    "stock_name": row.get("Name") or row.get("stock_name") or "",
                    "change_rate": _to_float(row.get("IncreaseAmount")),
                    "net_amount": _to_amount(row.get("BuyIn")),
                    "join_num": _to_float(row.get("JoinNum")),
                    "amount": _to_amount(row.get("Turnover")),
                    "float_mv": _to_amount(row.get("CircPrice")),
                    "turnover_ratio": _to_float(row.get("TurnoverRatio")),
                    "total_mv": _to_amount(row.get("Capitalization")),
                    "buy_seats": (
                        buy_icons.get(code, []) if isinstance(buy_icons, dict) else []
                    ),
                    "sell_seats": (
                        sell_icons.get(code, [])
                        if isinstance(sell_icons, dict)
                        else []
                    ),
                    "t_seats": (
                        t_icons.get(code, []) if isinstance(t_icons, dict) else []
                    ),
                    "concepts": (
                        list((concepts.get(code, {}) or {}).values())
                        if isinstance(concepts, dict)
                        else []
                    ),
                }
            )
        return result

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass
        try:
            self._realtime.close()
        except Exception:
            pass
        try:
            self._history.close()
        except Exception:
            pass


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
