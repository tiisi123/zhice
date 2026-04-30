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


def _fetch_real_macro(ts) -> list[dict]:
    """从 TuShare 拉取 PMI / CPI / PPI 等。"""
    indicators = []
    for api, name, unit in [
        ("cn_pmi", "PMI", ""),
        ("cn_cpi", "CPI", "%"),
        ("cn_ppi", "PPI", "%"),
        ("cn_m2", "M2", "%"),
    ]:
        try:
            rows = ts._post(api_name=api, params={}, fields="")
            if rows and len(rows) >= 2:
                latest = rows[0]
                prev = rows[1]
                val = float(latest.get(next((k for k in latest if k != "month" and k != "date"), ""), 0))
                prev_val = float(prev.get(next((k for k in prev if k != "month" and k != "date"), ""), 0))
                direction = "up" if val > prev_val else "down" if val < prev_val else "flat"
                indicators.append({
                    "name": name, "value": val, "prev": prev_val,
                    "unit": unit, "direction": direction,
                    "date": latest.get("month", latest.get("date", "")),
                    "data_source": "tushare",
                })
        except Exception:
            continue
    return indicators if len(indicators) >= 2 else []


def get_industry_prosperity() -> list[dict]:
    return INDUSTRY_PROSPERITY


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
    return [i for i in INDUSTRY_PROSPERITY if i["industry"] in names]


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

EXPECTATION_HISTORY: dict[str, list[dict]] = {
    "600519": [
        {"date": "2026-01", "broker": "中信证券", "target": 2000, "eps_e": 60.0, "rating": "买入"},
        {"date": "2026-02", "broker": "华泰证券", "target": 1950, "eps_e": 62.5, "rating": "买入"},
        {"date": "2026-02", "broker": "中信证券", "target": 2050, "eps_e": 63.0, "rating": "买入"},
        {"date": "2026-03", "broker": "国泰君安", "target": 1900, "eps_e": 60.0, "rating": "增持"},
        {"date": "2026-04", "broker": "中信证券", "target": 2100, "eps_e": 65.0, "rating": "买入"},
        {"date": "2026-04", "broker": "华泰证券", "target": 1980, "eps_e": 62.5, "rating": "买入"},
        {"date": "2026-04", "broker": "海通证券", "target": 2050, "eps_e": 63.5, "rating": "优于大市"},
    ],
    "300750": [
        {"date": "2026-01", "broker": "中信证券", "target": 250, "eps_e": 10.0, "rating": "买入"},
        {"date": "2026-02", "broker": "招商证券", "target": 240, "eps_e": 10.5, "rating": "强烈推荐"},
        {"date": "2026-03", "broker": "中金公司", "target": 230, "eps_e": 10.0, "rating": "推荐"},
        {"date": "2026-04", "broker": "中信证券", "target": 280, "eps_e": 11.0, "rating": "买入"},
        {"date": "2026-04", "broker": "招商证券", "target": 260, "eps_e": 10.5, "rating": "买入"},
        {"date": "2026-04", "broker": "国盛证券", "target": 275, "eps_e": 10.8, "rating": "买入"},
    ],
}


def get_meso_data(industry: str | None = None) -> list[dict]:
    if industry:
        return [d for d in MESO_INDUSTRY_DATA if d["industry"] == industry]
    return MESO_INDUSTRY_DATA


def get_alternative_data(code: str) -> list[dict]:
    return ALTERNATIVE_DATA.get(code, [])


def get_expectation_history(code: str) -> list[dict]:
    return EXPECTATION_HISTORY.get(code, [])
