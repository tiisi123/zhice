from __future__ import annotations

import datetime
import logging
from typing import Optional

import httpx

from .endpoints import HOST_MAP, KPL_REALTIME_HOST

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 6.0.1; MI 6 Build/V417IR)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
}


def _recent_5min(now: Optional[datetime.datetime] = None) -> str:
    """Replicates daban_pc kpl_server.py:29-48 exactly.

    Lunch 11:30-13:00 forces 1130; pre-open before 09:25 raises ValueError;
    upper bound capped at 1500.
    """
    if now is None:
        now = datetime.datetime.now()
    if now.time() < datetime.time(9, 25):
        raise ValueError(
            f"_recent_5min called before market open (09:25): {now.time().isoformat()}"
        )
    recent = now - datetime.timedelta(
        minutes=now.minute % 5,
        seconds=now.second,
        microseconds=now.microsecond,
    )
    max_time = recent.replace(hour=15, minute=0, second=0, microsecond=0)
    if recent > max_time:
        recent = max_time
    if datetime.time(11, 30) < recent.time() < datetime.time(13, 0):
        recent = recent.replace(hour=11, minute=30, second=0, microsecond=0)
    return recent.strftime("%H%M")


class KplRealtimeClient:
    """KPL realtime endpoint (apphwhq) client.

    KPL realtime calls require both DeviceID form data and the operator-managed
    mobile Cookie captured from daban_pc.
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

    def _headers(self, host_key: str = "realtime") -> dict:
        h = _DEFAULT_HEADERS.copy()
        h["Host"] = HOST_MAP.get(host_key, HOST_MAP["realtime"])
        if self.cookie:
            h["Cookie"] = self.cookie
        return h

    def _has_credentials(self) -> bool:
        return bool(self.cookie or (self.token and self.user_id))

    def _post(self, url: str, data: dict, host_key: str = "realtime") -> dict:
        if not self._has_credentials():
            return {"_error": "cookie_missing"}
        try:
            resp = self._client.post(url, data=data, headers=self._headers(host_key))
            resp.raise_for_status()
            if not resp.text.strip():
                log = logger.info if data.get("a") in {"ConceptSelected"} else logger.warning
                log(
                    "KPL realtime empty body: endpoint=%s a=%s",
                    url,
                    data.get("a", ""),
                )
                return {"_error": "kpl_upstream_error", "http_code": 200}
            try:
                return resp.json()
            except Exception:
                logger.warning(
                    "KPL realtime malformed JSON: endpoint=%s a=%s",
                    url,
                    data.get("a", ""),
                )
                return {"_error": "kpl_upstream_error", "http_code": 200}
        except httpx.HTTPStatusError as e:
            http_code = e.response.status_code if e.response is not None else 0
            logger.warning(
                "KPL realtime upstream %s: endpoint=%s a=%s",
                http_code,
                url,
                data.get("a", ""),
            )
            return {"_error": "kpl_upstream_error", "http_code": http_code}
        except Exception as e:
            logger.warning(
                "KPL realtime request failed: endpoint=%s a=%s -> %s",
                url,
                data.get("a", ""),
                e,
            )
            return {}

    def _recent_5min(self) -> str:
        return _recent_5min()

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

    # 板块强度（实时）— daban_pc 实测 a=RealRankingInfo c=ZhiShuRanking
    def get_sectors_realtime(self, index: int = 0, order: int = 0) -> dict:
        try:
            rend = self._recent_5min()
        except ValueError as exc:
            logger.info("KPL realtime skipped before market open: %s", exc)
            return {"_error": "kpl_market_closed", "http_code": 0}
        data = self._base_params(
            a="RealRankingInfo",
            c="ZhiShuRanking",
            RStart="0925",
            REnd=rend,
            Type="-4",
            old="1",
            ZSType="7",
            filterType="",
            Order=str(order),
            Index=str(index),
            st="30",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # 市场异动 — daban_pc 实测 a=Radar c=HomeDingPan (T01 Spike Deviation #4 corrected)
    def get_market_anomaly(self, index: int = 0) -> dict:
        data = self._base_params(
            a="Radar",
            c="HomeDingPan",
            st="30",
            Index=str(index),
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # 概念精选（实时）
    def get_concept_selected(self, index: int = 0, order: int = 0) -> dict:
        try:
            rend = self._recent_5min()
        except ValueError as exc:
            logger.info("KPL realtime skipped before market open: %s", exc)
            return {"_error": "kpl_market_closed", "http_code": 0}
        data = self._base_params(
            a="ConceptSelected",
            c="HomeDingPan",
            RStart="0925",
            REnd=rend,
            IsZZ="0",
            TSZB="0",
            IsKZZType="0",
            TSZB_Type="0",
            filterType="",
            Order=str(order),
            Index=str(index),
            st="20",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    def get_stock_ranking(
        self,
        index: int = 0,
        page_size: int = 26,
        *,
        order: str = "1",
        ranking_type: str = "1",
        ratio: str = "6",
        date: str = "",
    ) -> dict:
        data = self._base_params(
            a="RealRankingInfo_W8",
            c="NewStockRanking",
            Order=str(order),
            st=str(page_size),
            RStart="0925",
            REnd="1500",
            Isst="0",
            index=str(index),
            Date=date,
            Type=str(ranking_type),
            FilterMotherboard="0",
            Filter="0",
            Ratio=str(ratio),
            FilterBJS="0",
            FilterTIB="0",
            FilterGem="0",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # 概念详情（实时）— daban_pc 实测 a=ZhiShuStockList_W8
    def get_concept_detail(self, plate_id: str, index: int = 0) -> dict:
        try:
            rend = self._recent_5min()
        except ValueError as exc:
            logger.info("KPL realtime skipped before market open: %s", exc)
            return {"_error": "kpl_market_closed", "http_code": 0}
        data = self._base_params(
            a="ZhiShuStockList_W8",
            c="HomeDingPan",
            PlateID=plate_id,
            RStart="0925",
            REnd=rend,
            Type="-4",
            old="1",
            ZSType="7",
            filterType="",
            Order="0",
            Index=str(index),
            st="60",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # 子板块（实时）— daban_pc 实测 a=SonPlate_Info
    def get_concept_subsection(self, plate_id: str) -> dict:
        data = self._base_params(
            a="SonPlate_Info",
            c="HomeDingPan",
            PlateID=plate_id,
            IsShow="1",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # 题材库详情 — daban_pc HomeThemeDetailPage uses a=InfoGet, c=Theme, ID=<theme_id>
    def get_theme_info(self, theme_id: str) -> dict:
        data = self._base_params(
            a="InfoGet",
            c="Theme",
            ID=str(theme_id),
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    # T05 health probe — minimal payload to confirm realtime endpoint reachable
    def get_market_statistics_lite(self) -> dict:
        data = self._base_params(
            a="RealRankingInfo",
            c="ZhiShuRanking",
            Index="0",
            st="1",
        )
        return self._post(KPL_REALTIME_HOST, data, "realtime")

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
