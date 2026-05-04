from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _safe_float(val, default: float = 0.0) -> float:
    try:
        if val in (None, "", "-"):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


SAMPLE_FINANCIALS: dict[str, dict] = {
    "600519": {
        "code": "600519", "name": "贵州茅台",
        "revenue": 150_000_000_000, "revenue_yoy": 15.2,
        "net_profit": 75_000_000_000, "net_profit_yoy": 16.8,
        "gross_margin": 91.5, "net_margin": 50.0,
        "roe": 32.5, "roa": 22.0,
        "pe": 28.5, "pb": 10.2, "ps": 14.3,
        "pe_percentile": 45, "pb_percentile": 55,
        "div_yield": 1.8, "debt_ratio": 18.5,
        "fcf": 60_000_000_000,
        "highlights": ["直销占比提升", "产品结构升级", "预收款环比回升"],
        "risks": ["动销压力", "政策风险", "社会库存偏高"],
    },
    "300750": {
        "code": "300750", "name": "宁德时代",
        "revenue": 400_000_000_000, "revenue_yoy": 22.0,
        "net_profit": 45_000_000_000, "net_profit_yoy": 30.5,
        "gross_margin": 22.0, "net_margin": 11.2,
        "roe": 20.0, "roa": 10.0,
        "pe": 25.0, "pb": 5.5, "ps": 2.8,
        "pe_percentile": 35, "pb_percentile": 40,
        "div_yield": 0.5, "debt_ratio": 55.0,
        "fcf": 15_000_000_000,
        "highlights": ["海外份额扩张", "储能业务爆发", "新技术降本"],
        "risks": ["材料价格波动", "竞争加剧", "政策补贴退坡"],
    },
}



def get_financial_reports(code: str) -> list[dict]:
    """DFCF announcements (kind='report') → empty list on failure. No mock fallback (D009)."""
    try:
        from packages.connectors.registry import get_dfcf
        dfcf = get_dfcf()
        return dfcf.get_announcements(code, days=365, kind="report")
    except Exception as e:
        logger.warning("DFCF financial_reports fetch failed for %s: %s", code, e)
        return []


def get_research_reports(code: str) -> list[dict]:
    """DFCF research reports → empty list on failure. No mock fallback (D009)."""
    try:
        from packages.connectors.registry import get_dfcf
        dfcf = get_dfcf()
        return dfcf.get_research_reports(code, n=20)
    except Exception as e:
        logger.warning("DFCF research_reports fetch failed for %s: %s", code, e)
        return []


def _fetch_real_financial(code: str) -> Optional[dict]:
    """从 DFCF 拉取真实财务数据并组装为统一格式。"""
    try:
        from packages.connectors.registry import get_dfcf
        dfcf = get_dfcf()
        quote = dfcf.get_quote(code)
        if quote.get("error"):
            return None
        summary = dfcf.get_financial_summary(code, n_periods=4)
        if not summary.get("periods"):
            return None
        rev = summary["revenue"][0] if summary["revenue"] else 0
        np_ = summary["net_profit"][0] if summary["net_profit"] else 0
        roe = summary["roe"][0] if summary["roe"] else 0
        eps = summary["eps"][0] if summary["eps"] else 0
        gm = summary["gross_margin"][0] if summary["gross_margin"] else 0
        yoy_rev = summary["yoy_revenue"][0] if summary["yoy_revenue"] else 0
        yoy_np = summary["yoy_profit"][0] if summary["yoy_profit"] else 0
        pe = quote.get("pe_ttm", 0)
        pb = quote.get("pb", 0)
        mc = quote.get("market_cap", 0)
        return {
            "code": code,
            "name": quote.get("name", code),
            "revenue": rev,
            "revenue_yoy": yoy_rev,
            "net_profit": np_,
            "net_profit_yoy": yoy_np,
            "gross_margin": gm,
            "net_margin": round(np_ / rev * 100, 1) if rev else 0,
            "roe": roe,
            "roa": 0,
            "pe": pe,
            "pb": pb,
            "ps": round(mc / rev, 1) if rev and mc else 0,
            "pe_percentile": 50,
            "pb_percentile": 50,
            "div_yield": 0,
            "debt_ratio": 0,
            "fcf": np_ * 0.8,
            "eps": eps,
            "highlights": [],
            "risks": [],
            "data_source": "dfcf",
        }
    except Exception as e:
        logger.debug("fetch real financial for %s failed: %s", code, e)
        return None


def _fetch_tushare_financial(code: str) -> Optional[dict]:
    """TuShare 降级源：per-stock fina_indicator + daily_basic + income."""
    try:
        from packages.connectors.registry import get_tushare

        ts = get_tushare()
        if not ts.configured:
            return None

        basic = ts.get_stock_basic(code)
        daily = ts.get_daily_basic_latest(code)
        indicator = ts.get_fina_indicator_latest(code)
        income = ts.get_income_latest(code)
        if not daily and not indicator and not income:
            return None

        revenue = _safe_float(income.get("total_revenue") or income.get("revenue"))
        net_profit = _safe_float(income.get("n_income_attr_p") or income.get("n_income"))
        market_cap = _safe_float(daily.get("total_mv")) * 10000
        fcf = _safe_float(indicator.get("fcff") or indicator.get("fcfe"))
        if fcf <= 0 and net_profit:
            fcf = net_profit * 0.8

        return {
            "code": code,
            "name": basic.get("name") or daily.get("ts_code") or code,
            "industry": basic.get("industry", ""),
            "revenue": revenue,
            "revenue_yoy": _safe_float(indicator.get("or_yoy")),
            "net_profit": net_profit,
            "net_profit_yoy": _safe_float(indicator.get("netprofit_yoy")),
            "gross_margin": _safe_float(indicator.get("grossprofit_margin")),
            "net_margin": _safe_float(indicator.get("netprofit_margin")),
            "roe": _safe_float(indicator.get("roe_dt") or indicator.get("roe")),
            "roa": _safe_float(indicator.get("roa")),
            "pe": _safe_float(daily.get("pe_ttm") or daily.get("pe")),
            "pb": _safe_float(daily.get("pb")),
            "ps": _safe_float(daily.get("ps_ttm") or daily.get("ps")),
            "pe_percentile": 50,
            "pb_percentile": 50,
            "div_yield": _safe_float(daily.get("dv_ttm") or daily.get("dv_ratio")),
            "debt_ratio": _safe_float(indicator.get("debt_to_assets")),
            "fcf": fcf,
            "eps": _safe_float(indicator.get("dt_eps") or indicator.get("eps")),
            "market_cap": market_cap,
            "latest_trade_date": daily.get("trade_date", ""),
            "latest_report_date": indicator.get("end_date") or income.get("end_date") or "",
            "highlights": [],
            "risks": [],
            "data_source": "tushare",
        }
    except Exception as e:
        logger.debug("fetch tushare financial for %s failed: %s", code, e)
        return None


def get_financial(code: str) -> Optional[dict]:
    """DFCF primary → TuShare fallback → None. No SAMPLE_FINANCIALS fallback (D009)."""
    real = _fetch_real_financial(code)
    if real:
        return real
    logger.info("DFCF failed for %s, trying TuShare fallback", code)
    ts_fin = _fetch_tushare_financial(code)
    if ts_fin:
        logger.info("TuShare fallback succeeded for %s", code)
        return ts_fin
    logger.warning("Both DFCF and TuShare failed for %s — returning None", code)
    return None


def get_expectations(code: str) -> list[dict]:
    """DFCF research reports → analyst expectations. No mock fallback (D009)."""
    try:
        from packages.connectors.registry import get_dfcf
        dfcf = get_dfcf()
        reports = dfcf.get_research_reports(code, n=10)
        if reports:
            return [
                {
                    "broker": r.get("org", ""),
                    "rating": r.get("rating", ""),
                    "target": r.get("target_price", 0),
                    "eps_2026e": 0,
                    "data_source": "dfcf",
                }
                for r in reports if r.get("rating")
            ]
    except Exception as e:
        logger.warning("DFCF expectations fetch failed for %s: %s", code, e)
    return []


def calc_dcf(fcf: float, growth_rate: float = 0.1, discount_rate: float = 0.08, years: int = 10, terminal_growth: float = 0.03) -> dict:
    pv_sum = 0.0
    projected = []
    cf = fcf
    for y in range(1, years + 1):
        cf *= (1 + growth_rate)
        pv = cf / (1 + discount_rate) ** y
        pv_sum += pv
        projected.append({"year": y, "fcf": round(cf / 1e8, 1), "pv": round(pv / 1e8, 1)})
    terminal = cf * (1 + terminal_growth) / (discount_rate - terminal_growth)
    terminal_pv = terminal / (1 + discount_rate) ** years
    enterprise_value = pv_sum + terminal_pv
    return {
        "enterprise_value_billion": round(enterprise_value / 1e8, 1),
        "terminal_value_billion": round(terminal_pv / 1e8, 1),
        "projected_fcf": projected,
        "assumptions": {
            "growth_rate": growth_rate,
            "discount_rate": discount_rate,
            "terminal_growth": terminal_growth,
            "years": years,
        },
    }


def calc_expectation_gap(code: str, actual_eps: float) -> dict:
    exps = get_expectations(code)
    if not exps:
        return {"code": code, "gap": 0, "interpretation": "无预期数据"}
    avg_eps = sum(e["eps_2026e"] for e in exps) / len(exps)
    gap = round((actual_eps - avg_eps) / avg_eps * 100, 2)
    if gap > 5:
        interp = "超预期"
    elif gap < -5:
        interp = "低于预期"
    else:
        interp = "符合预期"
    return {"code": code, "actual_eps": actual_eps, "consensus_eps": round(avg_eps, 2), "gap_pct": gap, "interpretation": interp}


def screen_value_stocks(
    min_pe: float = 0, max_pe: float = 30,
    min_roe: float = 15, min_div: float = 1.0,
    max_pb: float = 0, min_market_cap: float = 0,
) -> list[dict]:
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        if not ts.configured:
            return []
    except Exception:
        return []

    daily_rows = ts.get_daily_basic_all()
    if not daily_rows:
        return []

    fina_rows = ts.get_fina_indicator_all()
    fina_map: dict[str, dict] = {}
    for row in fina_rows:
        code = row.get("ts_code", "")
        if code and code not in fina_map:
            fina_map[code] = row

    has_fina = bool(fina_map)
    if not has_fina and min_roe > 0:
        logger.warning("fina_indicator_all returned 0 rows; ROE filter (min_roe=%.1f) skipped", min_roe)

    result = []
    for row in daily_rows:
        ts_code = row.get("ts_code", "")
        if not ts_code:
            continue

        pe = _safe_float(row.get("pe_ttm") or row.get("pe"))
        pb = _safe_float(row.get("pb"))
        dv = _safe_float(row.get("dv_ttm") or row.get("dv_ratio"))
        total_mv = _safe_float(row.get("total_mv"))
        close = _safe_float(row.get("close"))

        if pe <= 0 or pe < min_pe or pe > max_pe:
            continue
        if dv < min_div:
            continue
        if max_pb > 0 and pb > max_pb:
            continue
        if min_market_cap > 0 and total_mv * 10000 < min_market_cap:
            continue

        fina = fina_map.get(ts_code, {})
        roe = _safe_float(fina.get("roe_dt") or fina.get("roe"))
        if has_fina and roe < min_roe:
            continue

        raw_code = ts_code.split(".")[0] if "." in ts_code else ts_code
        result.append({
            "code": raw_code,
            "ts_code": ts_code,
            "name": "",
            "pe": round(pe, 2),
            "pb": round(pb, 2),
            "ps": _safe_float(row.get("ps_ttm") or row.get("ps")),
            "div_yield": round(dv, 2),
            "roe": round(roe, 2),
            "roa": _safe_float(fina.get("roa")),
            "gross_margin": _safe_float(fina.get("grossprofit_margin")),
            "net_margin": _safe_float(fina.get("netprofit_margin")),
            "eps": _safe_float(fina.get("dt_eps") or fina.get("eps")),
            "debt_ratio": _safe_float(fina.get("debt_to_assets")),
            "market_cap": total_mv * 10000,
            "close": close,
            "data_source": "tushare",
        })

    result.sort(key=lambda x: x.get("roe", 0), reverse=True)
    return result


def forecast_financials(code: str) -> dict:
    fin = SAMPLE_FINANCIALS.get(code)
    if not fin:
        return {"error": "个股不存在"}
    base_rev = fin["revenue"]
    base_profit = fin["net_profit"]
    scenarios = {}
    for label, rev_g, profit_g in [("乐观", 0.20, 0.25), ("基准", 0.12, 0.15), ("悲观", 0.05, 0.05)]:
        scenarios[label] = {
            "revenue": round(base_rev * (1 + rev_g) / 1e8, 1),
            "net_profit": round(base_profit * (1 + profit_g) / 1e8, 1),
            "revenue_growth": f"{rev_g*100}%",
            "profit_growth": f"{profit_g*100}%",
        }
    return {"code": code, "name": fin["name"], "scenarios": scenarios}
