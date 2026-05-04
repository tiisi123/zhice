from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)

# --- 宏观数据（半静态示例，Phase 5 接入真实数据源 jygs/dfcf） ---

MACRO_INDICATORS: list[dict] = [
    {"name": "PMI", "value": 50.5, "prev": 50.1, "unit": "", "direction": "up", "date": "2026-03"},
    {"name": "CPI", "value": 0.3, "prev": 0.1, "unit": "%", "direction": "up", "date": "2026-03"},
    {"name": "PPI", "value": -2.7, "prev": -2.8, "unit": "%", "direction": "up", "date": "2026-03"},
    {"name": "社融", "value": 5.89, "prev": 5.21, "unit": "万亿", "direction": "up", "date": "2026-03"},
    {"name": "M2", "value": 7.0, "prev": 7.0, "unit": "%", "direction": "flat", "date": "2026-03"},
    {"name": "LPR-1Y", "value": 3.10, "prev": 3.10, "unit": "%", "direction": "flat", "date": "2026-04"},
    {"name": "LPR-5Y", "value": 3.60, "prev": 3.60, "unit": "%", "direction": "flat", "date": "2026-04"},
    {"name": "美元兑人民币", "value": 7.24, "prev": 7.26, "unit": "", "direction": "down", "date": "2026-04"},
]


# --- 行业景气度矩阵 ---

INDUSTRY_PROSPERITY: list[dict] = [
    {"industry": "半导体", "q1": 72, "q2": 78, "q3": 82, "q4": 85, "trend": "up", "level": "high"},
    {"industry": "新能源车", "q1": 80, "q2": 75, "q3": 68, "q4": 65, "trend": "down", "level": "medium"},
    {"industry": "光伏", "q1": 85, "q2": 70, "q3": 55, "q4": 50, "trend": "down", "level": "low"},
    {"industry": "AI/算力", "q1": 65, "q2": 75, "q3": 85, "q4": 90, "trend": "up", "level": "high"},
    {"industry": "医药生物", "q1": 55, "q2": 58, "q3": 60, "q4": 62, "trend": "up", "level": "medium"},
    {"industry": "消费电子", "q1": 50, "q2": 55, "q3": 65, "q4": 70, "trend": "up", "level": "medium"},
    {"industry": "军工", "q1": 60, "q2": 62, "q3": 63, "q4": 65, "trend": "flat", "level": "medium"},
    {"industry": "白酒", "q1": 70, "q2": 68, "q3": 65, "q4": 63, "trend": "down", "level": "medium"},
    {"industry": "地产", "q1": 30, "q2": 35, "q3": 38, "q4": 40, "trend": "up", "level": "low"},
    {"industry": "银行", "q1": 55, "q2": 56, "q3": 57, "q4": 58, "trend": "flat", "level": "medium"},
    {"industry": "电力设备", "q1": 65, "q2": 68, "q3": 72, "q4": 75, "trend": "up", "level": "medium"},
    {"industry": "传媒", "q1": 40, "q2": 50, "q3": 60, "q4": 68, "trend": "up", "level": "medium"},
]


# --- 持仓仪表盘（示例，Phase 5 真实用户持仓） ---

SAMPLE_PORTFOLIO: list[dict] = [
    {"code": "600519", "name": "贵州茅台", "cost": 1680.0, "price": 1720.0, "shares": 100, "pe": 28.5, "pe_percentile": 45, "pb": 10.2, "roe": 32.5, "div_yield": 1.8},
    {"code": "000858", "name": "五粮液", "cost": 145.0, "price": 152.0, "shares": 500, "pe": 22.0, "pe_percentile": 30, "pb": 6.8, "roe": 25.0, "div_yield": 2.5},
    {"code": "601012", "name": "隆基绿能", "cost": 25.0, "price": 22.5, "shares": 2000, "pe": 15.0, "pe_percentile": 20, "pb": 2.8, "roe": 18.0, "div_yield": 1.2},
    {"code": "300750", "name": "宁德时代", "cost": 210.0, "price": 225.0, "shares": 200, "pe": 25.0, "pe_percentile": 35, "pb": 5.5, "roe": 20.0, "div_yield": 0.5},
]


def get_macro_indicators() -> list[dict]:
    """优先从 TuShare 拉取宏观指标，失败时回退到静态数据。"""
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        if ts.configured:
            real = _fetch_real_macro(ts)
            if real:
                return real
    except Exception:
        logger.debug("fetch real macro failed, using mock data")
    return [dict(m, data_source="mock") for m in MACRO_INDICATORS]


_MACRO_API_MAP: list[tuple[str, str, str, str, str]] = [
    # (api_name, display_name, unit, value_field, date_field)
    ("cn_pmi",   "PMI",  "",     "PMI010000", "MONTH"),
    ("cn_cpi",   "CPI",  "%",    "nt_yoy",    "month"),
    ("cn_ppi",   "PPI",  "%",    "ppi_yoy",   "month"),
    ("cn_m",     "M2",   "%",    "m2_yoy",    "month"),
    ("sf_month", "社融",  "万亿", "inc_month",  "month"),
]


def _fetch_real_macro(ts) -> list[dict]:
    """从 TuShare 拉取 PMI / CPI / PPI / M2 / 社融。"""
    indicators = []
    for api, name, unit, val_field, date_field in _MACRO_API_MAP:
        try:
            rows = ts._post(api_name=api, params={}, fields="")
            if not rows or len(rows) < 2:
                continue
            latest, prev = rows[0], rows[1]
            raw_val = latest.get(val_field)
            raw_prev = prev.get(val_field)
            if raw_val is None or raw_prev is None:
                continue
            val = float(raw_val)
            prev_val = float(raw_prev)
            if name == "社融":
                val = round(val / 10000, 2)
                prev_val = round(prev_val / 10000, 2)
            direction = "up" if val > prev_val else "down" if val < prev_val else "flat"
            raw_date = str(latest.get(date_field, ""))
            indicators.append({
                "name": name, "value": val, "prev": prev_val,
                "unit": unit, "direction": direction,
                "date": f"{raw_date[:4]}-{raw_date[4:6]}" if len(raw_date) >= 6 else raw_date,
                "data_source": "tushare",
            })
        except Exception:
            continue
    _append_static_rates(indicators)
    return indicators if len(indicators) >= 2 else []


def _append_static_rates(indicators: list[dict]) -> None:
    """LPR 和汇率 TuShare 未开放，保留静态值但标记来源。"""
    for item in MACRO_INDICATORS:
        if item["name"] in ("LPR-1Y", "LPR-5Y", "美元兑人民币"):
            indicators.append(dict(item, data_source="static"))


def get_industry_prosperity() -> list[dict]:
    """优先从申万行业指数行情拉取景气度，失败时回退到静态数据。"""
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        if ts.configured:
            real = _fetch_real_prosperity(ts)
            if real:
                return real
    except Exception:
        logger.debug("fetch real prosperity failed, using static data")
    return [dict(i, data_source="mock") for i in INDUSTRY_PROSPERITY]


_QUARTER_BOUNDARIES = [
    ("Q1", "0101", "0331"),
    ("Q2", "0401", "0630"),
    ("Q3", "0701", "0930"),
    ("Q4", "1001", "1231"),
]


def _quarter_return(rows: list[dict], year: int, q_start: str, q_end: str) -> float | None:
    """Calculate quarter return from sw_daily rows."""
    start_d = f"{year}{q_start}"
    end_d = f"{year}{q_end}"
    period = [r for r in rows if start_d <= str(r.get("trade_date", "")) <= end_d]
    if len(period) < 2:
        return None
    period.sort(key=lambda r: str(r.get("trade_date", "")))
    open_price = float(period[0].get("close", 0))
    close_price = float(period[-1].get("close", 0))
    if open_price <= 0:
        return None
    return round((close_price - open_price) / open_price * 100, 1)


def _score_from_return(pct: float | None) -> int:
    """Map quarterly return to 0-100 prosperity score."""
    if pct is None:
        return 50
    if pct > 15:
        return 90
    if pct > 8:
        return 80
    if pct > 3:
        return 70
    if pct > 0:
        return 60
    if pct > -5:
        return 45
    if pct > -10:
        return 35
    return 25


def _fetch_real_prosperity(ts) -> list[dict]:
    """从 TuShare 申万一级行业指数拉取景气度矩阵。"""
    from datetime import datetime

    industries = ts._post(api_name="index_classify", params={"level": "L1", "src": "SW2021"}, fields="")
    if not industries:
        return []

    now = datetime.now()
    year = now.year
    start_date = f"{year - 1}0701"
    end_date = now.strftime("%Y%m%d")

    result = []
    for ind in industries:
        code = ind.get("index_code", "")
        name = ind.get("industry_name", "")
        if not code or not name:
            continue

        rows = ts._post(api_name="sw_daily", params={"ts_code": code, "start_date": start_date, "end_date": end_date}, fields="")
        if not rows:
            continue

        scores = {}
        for q_label, q_start, q_end in _QUARTER_BOUNDARIES:
            for y in (year - 1, year):
                ret = _quarter_return(rows, y, q_start, q_end)
                if ret is not None:
                    scores[q_label] = _score_from_return(ret)

        if len(scores) < 2:
            continue

        latest = rows[0]
        vals = list(scores.values())
        if len(vals) >= 2:
            trend = "up" if vals[-1] > vals[0] + 5 else "down" if vals[-1] < vals[0] - 5 else "flat"
        else:
            trend = "flat"
        avg = sum(vals) / len(vals)
        level = "high" if avg >= 70 else "low" if avg < 40 else "medium"

        result.append({
            "industry": name,
            "q1": scores.get("Q1", 50),
            "q2": scores.get("Q2", 50),
            "q3": scores.get("Q3", 50),
            "q4": scores.get("Q4", 50),
            "trend": trend,
            "level": level,
            "pe": round(float(latest.get("pe") or 0), 1),
            "pb": round(float(latest.get("pb") or 0), 2),
            "pct_change": round(float(latest.get("pct_change") or 0), 2),
            "data_source": "tushare",
        })

    result.sort(key=lambda x: x.get("q4", 0) if x.get("q4", 0) != 50 else x.get("q3", 0), reverse=True)
    return result


def get_portfolio() -> list[dict]:
    result = []
    for s in SAMPLE_PORTFOLIO:
        item = dict(s)
        item["market_value"] = round(item["price"] * item["shares"], 2)
        item["pnl"] = round((item["price"] - item["cost"]) * item["shares"], 2)
        item["pnl_rate"] = round((item["price"] - item["cost"]) / item["cost"] * 100, 2)
        result.append(item)
    return result


def compare_industries(names: list[str]) -> list[dict]:
    all_data = get_industry_prosperity()
    return [i for i in all_data if i["industry"] in names]


# --- 轮动推演 ---

ROTATION_HISTORY: dict[str, list[str]] = {
    "半导体": ["消费电子", "AI/算力", "光伏"],
    "AI/算力": ["半导体", "传媒", "消费电子"],
    "新能源车": ["电力设备", "光伏", "有色金属"],
    "军工": ["半导体", "新材料"],
    "医药生物": ["消费", "CXO"],
}


def simulate_rotation(source: str) -> list[dict]:
    targets = ROTATION_HISTORY.get(source, [])
    result = []
    for i, t in enumerate(targets):
        prob = max(20, 70 - i * 20)
        result.append({"target": t, "probability": prob, "lag_days": (i + 1) * 2})
    return result


MESO_INDUSTRY_DATA: list[dict] = [
    {"industry": "半导体", "metric": "晶圆产能利用率", "unit": "%", "values": [72, 75, 80, 85], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "半导体", "metric": "存储芯片均价", "unit": "美元/GB", "values": [3.2, 3.0, 2.8, 2.6], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "半导体", "metric": "设备订单额", "unit": "亿元", "values": [280, 310, 350, 400], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "新能源车", "metric": "月均销量", "unit": "万辆", "values": [88, 95, 102, 108], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "新能源车", "metric": "碳酸锂价格", "unit": "万元/吨", "values": [12.5, 11.0, 10.2, 9.8], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "新能源车", "metric": "电池库存周期", "unit": "天", "values": [35, 32, 28, 25], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "AI/算力", "metric": "GPU出货量", "unit": "万片", "values": [120, 160, 210, 280], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "AI/算力", "metric": "算力租赁价格", "unit": "元/卡时", "values": [2.5, 2.2, 1.9, 1.7], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "AI/算力", "metric": "数据中心新开工", "unit": "万平米", "values": [85, 110, 140, 175], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "光伏", "metric": "组件出货量", "unit": "GW", "values": [60, 55, 48, 42], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "光伏", "metric": "硅料价格", "unit": "万元/吨", "values": [6.5, 5.8, 5.2, 4.8], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "医药生物", "metric": "CDE受理数", "unit": "件", "values": [320, 350, 380, 410], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
    {"industry": "医药生物", "metric": "集采降幅", "unit": "%", "values": [52, 48, 45, 42], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "白酒", "metric": "批价指数", "unit": "点", "values": [102, 100, 98, 96], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "down"},
    {"industry": "白酒", "metric": "渠道库存", "unit": "月", "values": [2.8, 3.1, 3.5, 3.8], "quarters": ["Q1","Q2","Q3","Q4"], "trend": "up"},
]

ALTERNATIVE_DATA: dict[str, list[dict]] = {
    "600519": [
        {"source": "物流", "metric": "茅台镇日均发货车次", "value": 285, "prev": 260, "change": "+9.6%", "signal": "positive", "date": "2026-04"},
        {"source": "电商", "metric": "飞天茅台电商搜索指数", "value": 8520, "prev": 8100, "change": "+5.2%", "signal": "positive", "date": "2026-04"},
        {"source": "招聘", "metric": "茅台集团招聘岗位数", "value": 45, "prev": 38, "change": "+18.4%", "signal": "positive", "date": "2026-04"},
    ],
    "300750": [
        {"source": "物流", "metric": "宁德时代工厂周边货运量", "value": 12500, "prev": 11200, "change": "+11.6%", "signal": "positive", "date": "2026-04"},
        {"source": "用电", "metric": "福建宁德工业用电量(亿kWh)", "value": 4.2, "prev": 3.8, "change": "+10.5%", "signal": "positive", "date": "2026-04"},
        {"source": "招聘", "metric": "宁德时代招聘岗位数", "value": 320, "prev": 280, "change": "+14.3%", "signal": "positive", "date": "2026-04"},
        {"source": "专利", "metric": "月度专利申请量", "value": 185, "prev": 150, "change": "+23.3%", "signal": "positive", "date": "2026-04"},
    ],
}



def get_meso_data(industry: str | None = None) -> list[dict]:
    if industry:
        return [d for d in MESO_INDUSTRY_DATA if d["industry"] == industry]
    return MESO_INDUSTRY_DATA


def get_alternative_data(code: str) -> list[dict]:
    return ALTERNATIVE_DATA.get(code, [])


def get_expectation_history(code: str) -> list[dict]:
    """DFCF research reports bucketed by publish_date month. No mock fallback (D009)."""
    try:
        from packages.connectors.registry import get_dfcf
        dfcf = get_dfcf()
        reports = dfcf.get_research_reports(code, n=50)
        if not reports:
            return []
        result = []
        for r in reports:
            pub_date = r.get("publish_date", "")
            date_bucket = pub_date[:7] if len(pub_date) >= 7 else pub_date
            result.append({
                "date": date_bucket,
                "broker": r.get("org", ""),
                "target": r.get("target_price", 0),
                "rating": r.get("rating", ""),
                "title": r.get("title", ""),
            })
        result.sort(key=lambda x: x["date"])
        return result
    except Exception as e:
        logger.warning("DFCF expectation_history fetch failed for %s: %s", code, e)
        return []
