from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "https://api.tushare.pro"


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_token_from_env_file() -> str:
    env_token = os.getenv("TUSHARE_TOKEN", "").strip()
    if env_token:
        return env_token

    try:
        from apps.api.config import settings
        settings_token = (settings.tushare_token or "").strip()
        if settings_token:
            return settings_token
    except Exception:
        pass

    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return ""

    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().upper() == "TUSHARE_TOKEN":
                return value.strip().strip("'").strip('"')
    except Exception:
        return ""
    return ""


class TushareClient:
    _MAX_RETRIES = 2

    def __init__(self, token: str = "", host: str = _DEFAULT_HOST):
        self.token = (token or _load_token_from_env_file()).strip()
        self.host = host
        self._client = httpx.Client(timeout=15, verify=False)
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._cache_ttl = 300.0

    @property
    def configured(self) -> bool:
        return bool(self.token)

    def _post(self, api_name: str, params: dict[str, Any], fields: str) -> list[dict[str, Any]]:
        if not self.token:
            return []

        import time
        cache_key = f"{api_name}:{hash(frozenset(params.items()))}:{fields}"
        cached = self._cache.get(cache_key)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1]

        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params,
            "fields": fields,
        }
        last_err = None
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                resp = self._client.post(self.host, json=payload)
                resp.raise_for_status()
                body = resp.json()
                if body.get("code", -1) != 0:
                    logger.debug("Tushare API error: %s %s", api_name, body.get("msg", ""))
                    return cached[1] if cached else []
                table = body.get("data") or {}
                cols = table.get("fields") or []
                items = table.get("items") or []
                result = []
                for row in items:
                    if isinstance(row, (list, tuple)):
                        result.append(dict(zip(cols, row)))
                self._cache[cache_key] = (time.time(), result)
                return result
            except Exception as e:
                last_err = e
                if attempt < self._MAX_RETRIES:
                    time.sleep(1.0 * attempt)
        logger.warning("Tushare request failed after %d retries: %s -> %s",
                       self._MAX_RETRIES, api_name, last_err)
        return cached[1] if cached else []

    def get_daily(self, ts_code: str, start_date: str = "", end_date: str = "", limit: int = 0) -> list[dict[str, Any]]:
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y%m%d")
        fields = "ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount"
        rows = self._post(api_name="daily", params={"ts_code": ts_code, "start_date": start_date, "end_date": end_date}, fields=fields)
        parsed: list[dict[str, Any]] = []
        for row in rows:
            td = str(row.get("trade_date", ""))
            if len(td) != 8:
                continue
            parsed.append({
                "date": f"{td[:4]}-{td[4:6]}-{td[6:8]}",
                "open": _to_float(row.get("open")),
                "high": _to_float(row.get("high")),
                "low": _to_float(row.get("low")),
                "close": _to_float(row.get("close")),
                "pre_close": _to_float(row.get("pre_close")),
                "pct_chg": _to_float(row.get("pct_chg")),
                "volume": _to_float(row.get("vol")),
                "amount": _to_float(row.get("amount")) * 1000,
            })
        parsed.sort(key=lambda x: x["date"])
        return parsed[-limit:] if limit > 0 else parsed

    def get_fund_daily(self, ts_code: str, limit: int = 20) -> list[dict[str, Any]]:
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        fields = "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
        rows = self._post(
            api_name="fund_daily",
            params={"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            fields=fields,
        )
        parsed: list[dict[str, Any]] = []
        for row in rows:
            trade_date = str(row.get("trade_date", ""))
            if len(trade_date) != 8:
                continue
            parsed.append(
                {
                    "date": f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}",
                    "open": _to_float(row.get("open")),
                    "high": _to_float(row.get("high")),
                    "low": _to_float(row.get("low")),
                    "close": _to_float(row.get("close")),
                    "pct_chg": _to_float(row.get("pct_chg")),
                    "volume": _to_float(row.get("vol")),
                    # Tushare amount unit通常为千元，统一折算为元
                    "amount": _to_float(row.get("amount")) * 1000,
                    "turnover": 0.0,
                }
            )
        parsed.sort(key=lambda x: x["date"])
        return parsed[-limit:] if limit > 0 else parsed

    @staticmethod
    def to_ts_code(code: str) -> str:
        normalized = (code or "").strip().upper()
        if "." in normalized:
            return normalized
        suffix = "SH" if normalized.startswith(("5", "6", "9")) else "SZ"
        return f"{normalized}.{suffix}"

    def get_stock_basic(self, code: str) -> dict[str, Any]:
        ts_code = self.to_ts_code(code)
        fields = "ts_code,symbol,name,area,industry,market,list_date"
        rows = self._post(api_name="stock_basic", params={"ts_code": ts_code}, fields=fields)
        return rows[0] if rows else {}

    def get_daily_basic_latest(self, code: str) -> dict[str, Any]:
        ts_code = self.to_ts_code(code)
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=45)).strftime("%Y%m%d")
        fields = (
            "ts_code,trade_date,close,turnover_rate,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,"
            "dv_ratio,dv_ttm,total_share,float_share,total_mv,circ_mv"
        )
        rows = self._post(
            api_name="daily_basic",
            params={"ts_code": ts_code, "start_date": start_date, "end_date": end_date},
            fields=fields,
        )
        rows.sort(key=lambda x: str(x.get("trade_date", "")), reverse=True)
        return rows[0] if rows else {}

    def get_fina_indicator_latest(self, code: str) -> dict[str, Any]:
        ts_code = self.to_ts_code(code)
        fields = (
            "ts_code,end_date,eps,dt_eps,total_revenue_ps,revenue_ps,capital_rese_ps,"
            "roe,roe_dt,roa,grossprofit_margin,netprofit_margin,profit_to_gr,"
            "or_yoy,netprofit_yoy,debt_to_assets,fcff,fcfe"
        )
        rows = self._post(api_name="fina_indicator", params={"ts_code": ts_code}, fields=fields)
        rows.sort(key=lambda x: str(x.get("end_date", "")), reverse=True)
        return rows[0] if rows else {}

    def get_income_latest(self, code: str) -> dict[str, Any]:
        ts_code = self.to_ts_code(code)
        fields = "ts_code,end_date,total_revenue,revenue,n_income,n_income_attr_p"
        rows = self._post(api_name="income", params={"ts_code": ts_code}, fields=fields)
        rows.sort(key=lambda x: str(x.get("end_date", "")), reverse=True)
        return rows[0] if rows else {}

    def get_financial_summary(self, code: str, n_periods: int = 8) -> dict[str, Any]:
        ts_code = self.to_ts_code(code)
        income_fields = "ts_code,end_date,total_revenue,revenue,n_income,n_income_attr_p"
        indicator_fields = "ts_code,end_date,eps,roe,roe_dt,grossprofit_margin,or_yoy,netprofit_yoy"
        income_rows = self._post(api_name="income", params={"ts_code": ts_code}, fields=income_fields)
        indicator_rows = self._post(api_name="fina_indicator", params={"ts_code": ts_code}, fields=indicator_fields)
        income_rows.sort(key=lambda x: str(x.get("end_date", "")), reverse=True)
        indicator_map = {str(x.get("end_date", "")): x for x in indicator_rows}

        rows = []
        seen_periods: set[str] = set()
        for item in income_rows:
            end_date = str(item.get("end_date", ""))
            if not end_date or end_date in seen_periods:
                continue
            seen_periods.add(end_date)
            rows.append(item)
            if len(rows) >= max(1, n_periods):
                break
        periods: list[str] = []
        revenue: list[float] = []
        net_profit: list[float] = []
        yoy_revenue: list[float] = []
        yoy_profit: list[float] = []
        roe: list[float] = []
        eps: list[float] = []
        gross_margin: list[float] = []

        for row in rows:
            end_date = str(row.get("end_date", ""))
            ind = indicator_map.get(end_date, {})
            periods.append(end_date)
            revenue.append(_to_float(row.get("total_revenue") or row.get("revenue")))
            net_profit.append(_to_float(row.get("n_income_attr_p") or row.get("n_income")))
            yoy_revenue.append(_to_float(ind.get("or_yoy")))
            yoy_profit.append(_to_float(ind.get("netprofit_yoy")))
            roe.append(_to_float(ind.get("roe_dt") or ind.get("roe")))
            eps.append(_to_float(ind.get("eps")))
            gross_margin.append(_to_float(ind.get("grossprofit_margin")))

        return {
            "code": code,
            "periods": periods,
            "revenue": revenue,
            "net_profit": net_profit,
            "yoy_revenue": yoy_revenue,
            "yoy_profit": yoy_profit,
            "roe": roe,
            "eps": eps,
            "gross_margin": gross_margin,
            "data_source": "tushare",
        }

    def close(self):
        self._client.close()
