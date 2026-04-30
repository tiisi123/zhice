"""
东方财富（dfcf）数据连接器
覆盖能力：
  - get_financial_summary(code)  关键财务指标（营收/净利/毛利/ROE/EPS/PE/PB...）
  - get_company_profile(code)    公司简介
  - get_announcements(code, days=180, kind=None)  公告列表（财报/业绩预告/重大合同等）
  - get_research_reports(code, n=20)              券商研报列表
  - get_quote(code)              快照行情（价格/PE/PB/总市值/流通市值）

数据源公开 endpoint（无需 token）：
  push2.eastmoney.com / datacenter-web.eastmoney.com / np-anotice-stock.eastmoney.com
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "referer": "https://data.eastmoney.com/",
}

_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
# 财务摘要（数据中心）：经营指标/利润表/财务摘要等
_REPORT_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
# 公告（精简列表）
_ANN_URL = "https://np-anotice-stock.eastmoney.com/api/security/ann"
# 公司简介
_PROFILE_URL = "https://emweb.securities.eastmoney.com/PC_HSF10/CompanyProfile/PageAjax"


def _infer_market(code: str) -> str:
    """A 股市场判断：1=SH, 0=SZ；返回 secid 字符串。"""
    if code.startswith(("60", "68", "9", "5")):
        return f"1.{code}"
    return f"0.{code}"


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v in (None, "", "-"):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


class DfcfClient:
    def __init__(self, timeout: float = 12.0):
        self._client = httpx.Client(timeout=timeout, verify=False, headers=_HEADERS)

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    # ---------------- 行情快照 ----------------
    def get_quote(self, code: str) -> dict:
        """快照：价格 / 涨跌幅 / PE-TTM / PB / 总市值 / 流通市值。"""
        secid = _infer_market(code)
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f57,f58,f60,f162,f167,f116,f117,f168,f169,f170",
            "fltt": "2",
            "invt": "2",
        }
        try:
            r = self._client.get(_QUOTE_URL, params=params)
            r.raise_for_status()
            d = (r.json() or {}).get("data") or {}
            return {
                "code": code,
                "name": d.get("f58"),
                "price": _safe_float(d.get("f43")),
                "open": _safe_float(d.get("f46")),
                "high": _safe_float(d.get("f44")),
                "low": _safe_float(d.get("f45")),
                "prev_close": _safe_float(d.get("f60")),
                "change_rate": _safe_float(d.get("f170")),
                "pe_ttm": _safe_float(d.get("f162")),
                "pb": _safe_float(d.get("f167")),
                "market_cap": _safe_float(d.get("f116")),       # 总市值
                "circ_cap": _safe_float(d.get("f117")),         # 流通市值
                "turnover_rate": _safe_float(d.get("f168")),
                "amount": _safe_float(d.get("f48")),
                "volume": _safe_float(d.get("f47")),
                "industry": d.get("f57"),
            }
        except Exception as e:
            logger.warning("dfcf get_quote(%s) failed: %s", code, e)
            return {"code": code, "error": str(e)}

    # ---------------- 财务摘要 ----------------
    def get_financial_summary(self, code: str, n_periods: int = 8) -> dict:
        """
        关键财务指标近 n 期（按最新报告期倒序）。
        返回：{ periods: [...], revenue: [...], net_profit: [...], roe: [...], eps: [...],
                gross_margin: [...], yoy_revenue: [...], yoy_profit: [...] }
        """
        market = "SH" if code.startswith(("60", "68", "9")) else "SZ"
        sec_full = f"{code}.{market}"
        params = {
            "reportName": "RPT_LICO_FN_CPD",
            "columns": "ALL",
            "filter": f'(SECUCODE="{sec_full}")',
            "pageNumber": "1",
            "pageSize": str(n_periods),
            "sortColumns": "REPORT_DATE",
            "sortTypes": "-1",
            "source": "HSF10",
            "client": "PC",
        }
        try:
            r = self._client.get(_REPORT_URL, params=params)
            r.raise_for_status()
            payload = r.json() or {}
            rows = ((payload.get("result") or {}).get("data")) or []
            periods, revenue, net_profit, roe, eps, gm, yoy_rev, yoy_np = [], [], [], [], [], [], [], []
            for row in rows:
                periods.append((row.get("REPORT_DATE") or "")[:10])
                revenue.append(_safe_float(row.get("TOTAL_OPERATE_INCOME")))
                net_profit.append(_safe_float(row.get("PARENT_NETPROFIT")))
                roe.append(_safe_float(row.get("WEIGHTAVG_ROE")))
                eps.append(_safe_float(row.get("BASIC_EPS")))
                gm.append(_safe_float(row.get("XSMLL")))           # 销售毛利率
                yoy_rev.append(_safe_float(row.get("YSTZ")))       # 营收同比
                yoy_np.append(_safe_float(row.get("SJLTZ")))       # 净利同比
            return {
                "code": code,
                "periods": periods,
                "revenue": revenue,
                "net_profit": net_profit,
                "roe": roe,
                "eps": eps,
                "gross_margin": gm,
                "yoy_revenue": yoy_rev,
                "yoy_profit": yoy_np,
                "raw_count": len(rows),
            }
        except Exception as e:
            logger.warning("dfcf get_financial_summary(%s) failed: %s", code, e)
            return {"code": code, "periods": [], "error": str(e)}

    # ---------------- 公司简介 ----------------
    def get_company_profile(self, code: str) -> dict:
        market = "SH" if code.startswith(("60", "68", "9")) else "SZ"
        sec_full = f"{code}.{market}"
        params = {"code": sec_full}
        try:
            r = self._client.get(_PROFILE_URL, params=params)
            r.raise_for_status()
            j = r.json() or {}
            base = (j.get("jbzl") or [{}])[0]
            return {
                "code": code,
                "name": base.get("ORG_NAME_ABBR") or base.get("ORG_NAME"),
                "industry": base.get("EM2016"),
                "main_business": base.get("MAIN_BUSINESS"),
                "business_scope": base.get("BUSINESS_SCOPE"),
                "list_date": base.get("LIST_DATE"),
                "chairman": base.get("CHAIRMAN"),
                "address": base.get("REG_ADDRESS"),
                "website": base.get("ORG_WEB"),
            }
        except Exception as e:
            logger.warning("dfcf get_company_profile(%s) failed: %s", code, e)
            return {"code": code, "error": str(e)}

    # ---------------- 公告列表 ----------------
    _ANN_KIND_MAP = {
        "report": "1",        # 财报
        "earnings": "11",     # 业绩预告/快报
        "contract": "5",      # 合同
        "shareholder": "3",   # 股东
        "all": "0",
    }

    def get_announcements(self, code: str, days: int = 180, kind: Optional[str] = None, n: int = 50) -> list[dict]:
        """近 N 天公告列表。kind 可选 report/earnings/contract/shareholder/all。"""
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        params = {
            "stock_list": code,
            "page_size": str(n),
            "page_index": "1",
            "ann_type": "A",  # A 股
            "client_source": "web",
            "f_node": "0",
            "s_node": "0",
            "begin_time": start_date,
            "end_time": end_date,
        }
        try:
            r = self._client.get(_ANN_URL, params=params)
            r.raise_for_status()
            j = r.json() or {}
            data = ((j.get("data") or {}).get("list")) or []
            kind_code = self._ANN_KIND_MAP.get(kind or "all", "0")
            out: list[dict] = []
            for x in data:
                title = x.get("title") or ""
                code_main = ((x.get("codes") or [{}])[0].get("inner_code")) or code
                col_codes = [c.get("column_code") for c in (x.get("columns") or [])]
                # 简单关键字过滤：财报/业绩
                if kind == "report" and not re.search(r"年度报告|半年度报告|季度报告|审计报告", title):
                    continue
                if kind == "earnings" and not re.search(r"业绩预|业绩快报|业绩预告|业绩快讯", title):
                    continue
                out.append({
                    "code": code_main,
                    "title": title,
                    "art_code": x.get("art_code"),
                    "notice_date": x.get("notice_date"),
                    "url": f"https://data.eastmoney.com/notices/detail/{code_main}/{x.get('art_code')}.html",
                    "columns": col_codes,
                })
            return out
        except Exception as e:
            logger.warning("dfcf get_announcements(%s) failed: %s", code, e)
            return []

    # ---------------- 7x24 财经快讯 ----------------
    def get_news_flash(self, n: int = 50, club_id: int = 1) -> list[dict]:
        """
        7x24 快讯（东财财经导读）。
        club_id=1: 全部；2: A股；3: 公司新闻；4: 全球
        """
        url = "https://np-listapi.eastmoney.com/comm/wap/getListInfo"
        params = {
            "client": "wap",
            "biz": "web_724",
            "fastColumn": "102",
            "sortEnd": "",
            "pageSize": str(n),
            "req_trace": str(int(__import__("time").time() * 1000)),
        }
        try:
            r = self._client.get(url, params=params)
            r.raise_for_status()
            j = r.json() or {}
            data = (((j.get("data") or {}).get("fastNewsList")) or [])
            out: list[dict] = []
            for x in data:
                out.append({
                    "id": x.get("code"),
                    "title": x.get("title") or x.get("digest") or "",
                    "summary": x.get("digest") or "",
                    "publish_time": x.get("showTime") or x.get("publishTime"),
                    "source": x.get("mediaName"),
                    "url": x.get("commonUrl"),
                    "tags": x.get("tagInfo") or [],
                    "stocks": [
                        {"code": s.get("stockCode"), "name": s.get("stockName")}
                        for s in (x.get("stocks") or [])
                    ],
                    "is_red": bool(x.get("isImportant")),
                })
            return out
        except Exception as e:
            logger.warning("dfcf get_news_flash failed: %s", e)
            return []

    # ---------------- 研报 ----------------
    def get_research_reports(self, code: str, n: int = 20) -> list[dict]:
        params = {
            "reportName": "RPT_RESEARCH_RESREPORT",
            "columns": "ALL",
            "filter": f'(SECURITY_CODE="{code}")',
            "pageNumber": "1",
            "pageSize": str(n),
            "sortColumns": "PUBLISH_DATE",
            "sortTypes": "-1",
        }
        try:
            r = self._client.get(_REPORT_URL, params=params)
            r.raise_for_status()
            rows = ((r.json() or {}).get("result") or {}).get("data") or []
            return [{
                "code": code,
                "title": x.get("TITLE"),
                "org": x.get("ORG_NAME"),
                "rating": x.get("EM_RATING_NAME") or x.get("RATING_NAME"),
                "target_price": _safe_float(x.get("TARGET_PRICE")),
                "publish_date": (x.get("PUBLISH_DATE") or "")[:10],
                "url": x.get("REPORT_URL") or x.get("REPORT_DETAIL_URL"),
            } for x in rows]
        except Exception as e:
            logger.warning("dfcf get_research_reports(%s) failed: %s", code, e)
            return []
