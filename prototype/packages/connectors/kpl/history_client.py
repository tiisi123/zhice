from __future__ import annotations

import datetime
import logging
from typing import Optional

import httpx

from .endpoints import HOST_MAP, KPL_HISTORY_HOST

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 6.0.1; MI 6 Build/V417IR)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


class KplHistoryClient:
    """KPL history endpoint (apphis) client.

    Cookie injection: cookie='' triggers _post sentinel return without HTTP call.
    """

    def __init__(
        self,
        cookie: str = "",
        user_id: str = "",
        token: str = "",
        device_id: str = "",
        version: str = "5.17.0.0",
    ):
        self.cookie = cookie or ""
        self.user_id = user_id or ""
        self.token = token or ""
        self.device_id = device_id or ""
        self.version = version or "5.17.0.0"
        self._client = httpx.Client(timeout=15, verify=False)

    def _headers(self, host_key: str = "history") -> dict:
        h = _DEFAULT_HEADERS.copy()
        h["Host"] = HOST_MAP.get(host_key, HOST_MAP["history"])
        if self.cookie:
            h["Cookie"] = self.cookie
        return h

    def _post(self, url: str, data: dict, host_key: str = "history") -> dict:
        if not self.cookie:
            logger.info(
                "KPL history _post short-circuit: cookie_missing endpoint=%s a=%s",
                url,
                data.get("a", ""),
            )
            return {"_error": "cookie_missing"}
        try:
            resp = self._client.post(url, data=data, headers=self._headers(host_key))
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                logger.warning(
                    "KPL history malformed JSON: endpoint=%s a=%s",
                    url,
                    data.get("a", ""),
                )
                return {}
        except httpx.HTTPStatusError as e:
            http_code = e.response.status_code if e.response is not None else 0
            logger.warning(
                "KPL history upstream %s: endpoint=%s a=%s",
                http_code,
                url,
                data.get("a", ""),
            )
            return {"_error": "kpl_upstream_error", "http_code": http_code}
        except Exception as e:
            logger.warning(
                "KPL history request failed: endpoint=%s a=%s -> %s",
                url,
                data.get("a", ""),
                e,
            )
            return {}

    def _base_params(self, **extra) -> dict:
        params = {
            "PhoneOSNew": "1",
            "DeviceID": self.device_id,
            "VerSion": self.version,
            "apiv": "w38",
            "Token": self.token or "0",
            "UserID": self.user_id or "0",
        }
        params.update(extra)
        return params

    # 市场情绪/市值 — daban_pc 实测 a=HisZhangFuDetail (差异 #5)
    def get_market_statistics(self, trade_date: str) -> dict:
        data = self._base_params(
            a="HisZhangFuDetail",
            c="HisHomeDingPan",
            Day=trade_date,
        )
        return self._post(KPL_HISTORY_HOST, data, "history")

    # 概念精选（历史）
    def get_concept_selected_history(self, trade_date: str, index: int = 0) -> dict:
        data = self._base_params(
            a="ConceptSelected",
            c="HisHomeDingPan",
            Day=trade_date,
            IsZZ="0",
            TSZB="0",
            IsKZZType="0",
            TSZB_Type="0",
            filterType="",
            Order="0",
            Index=str(index),
            st="20",
        )
        return self._post(KPL_HISTORY_HOST, data, "history")

    # 概念详情（历史）— daban_pc 实测 a=ZhiShuStockList_W8
    def get_concept_detail_history(
        self, plate_id: str, trade_date: str, index: int = 0
    ) -> dict:
        data = self._base_params(
            a="ZhiShuStockList_W8",
            c="HisHomeDingPan",
            PlateID=plate_id,
            Day=trade_date,
            Type="-4",
            old="1",
            ZSType="7",
            filterType="",
            Order="0",
            Index=str(index),
            st="60",
        )
        return self._post(KPL_HISTORY_HOST, data, "history")

    # 涨停表现（历史）
    def get_limit_performance(
        self, trade_date: str, daily_limit: bool = True, order: int = 0
    ) -> dict:
        data = self._base_params(
            a="DailyLimitPerformance" if daily_limit else "DailyLimitPerformance2",
            c="HisHomeDingPan",
            Day=trade_date,
            Order=str(order),
            st="20",
        )
        return self._post(KPL_HISTORY_HOST, data, "history")

    # 主题列表（历史）
    def get_theme_list(self, trade_date: Optional[str] = None) -> dict:
        data = self._base_params(
            a="HomeThemeList",
            c="HisHomeDingPan",
        )
        if trade_date:
            data["Day"] = trade_date
        return self._post(KPL_HISTORY_HOST, data, "history")

    # T05 health probe — yesterday's market statistics
    def get_history_lite(self) -> dict:
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        data = self._base_params(
            a="HisZhangFuDetail",
            c="HisHomeDingPan",
            Day=yesterday,
        )
        return self._post(KPL_HISTORY_HOST, data, "history")

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
