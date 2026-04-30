from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

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

ANALYST_EXPECTATIONS: dict[str, list[dict]] = {
    "600519": [
        {"broker": "中信证券", "rating": "买入", "target": 2100, "eps_2026e": 65.0},
        {"broker": "华泰证券", "rating": "买入", "target": 1980, "eps_2026e": 62.5},
        {"broker": "国泰君安", "rating": "增持", "target": 1900, "eps_2026e": 60.0},
    ],
    "300750": [
        {"broker": "中信证券", "rating": "买入", "target": 280, "eps_2026e": 11.0},
        {"broker": "招商证券", "rating": "买入", "target": 260, "eps_2026e": 10.5},
        {"broker": "中金公司", "rating": "推荐", "target": 250, "eps_2026e": 10.0},
    ],
}


FINANCIAL_REPORTS: dict[str, list[dict]] = {
    "600519": [
        {
            "title": "贵州茅台2025年年度报告",
            "date": "2026-03-29",
            "type": "年报",
            "period": "2025",
            "revenue": "1505亿",
            "net_profit": "750亿",
            "eps": "59.7",
            "yoy": "+16.8%",
            "highlight": "直销收入占比提升至42%，产品均价环比上行",
            "sentiment": "positive",
        },
        {
            "title": "贵州茅台2025年三季报",
            "date": "2025-10-28",
            "type": "季报",
            "period": "2025Q3",
            "revenue": "1089亿",
            "net_profit": "548亿",
            "eps": "43.6",
            "yoy": "+15.5%",
            "highlight": "三季度末合同负债大幅回升，四季度发货预期较好",
            "sentiment": "positive",
        },
        {
            "title": "关于2025年度利润分配预案的公告",
            "date": "2026-03-29",
            "type": "公告",
            "period": "2025",
            "revenue": None,
            "net_profit": None,
            "eps": None,
            "yoy": None,
            "highlight": "拟每股派息30.876元（含税），分红率51.7%",
            "sentiment": "positive",
        },
    ],
    "300750": [
        {
            "title": "宁德时代2025年年度报告",
            "date": "2026-04-15",
            "type": "年报",
            "period": "2025",
            "revenue": "4010亿",
            "net_profit": "452亿",
            "eps": "10.32",
            "yoy": "+30.5%",
            "highlight": "海外收入占比突破40%，储能业务同比翻倍",
            "sentiment": "positive",
        },
        {
            "title": "宁德时代2025年三季报",
            "date": "2025-10-25",
            "type": "季报",
            "period": "2025Q3",
            "revenue": "2905亿",
            "net_profit": "322亿",
            "eps": "7.35",
            "yoy": "+28.0%",
            "highlight": "动力电池全球市占率37.1%，麒麟电池放量",
            "sentiment": "positive",
        },
        {
            "title": "关于签署战略合作框架协议的公告",
            "date": "2026-04-08",
            "type": "公告",
            "period": None,
            "revenue": None,
            "net_profit": None,
            "eps": None,
            "yoy": None,
            "highlight": "与某欧洲车企签署5年长期供货协议，预计金额超200亿欧元",
            "sentiment": "positive",
        },
    ],
}

RESEARCH_REPORTS: dict[str, list[dict]] = {
    "600519": [
        {"broker": "中信证券", "date": "2026-04-10", "rating": "买入", "prev_rating": "买入", "target": 2100, "prev_target": 2000, "title": "年报点评：直销加速兑现，上调目标价", "summary": "2025年报超预期。直销占比提升推动毛利率改善，上调2026E EPS至65元。"},
        {"broker": "华泰证券", "date": "2026-04-05", "rating": "买入", "prev_rating": "买入", "target": 1980, "prev_target": 1950, "title": "基本面坚实，分红提高凸显配置价值", "summary": "分红率提升至51.7%，股息率2.0%+。预收款回升指向Q1发货向好。"},
        {"broker": "国泰君安", "date": "2026-03-30", "rating": "增持", "prev_rating": "增持", "target": 1900, "prev_target": 1900, "title": "年报符合预期，维持增持", "summary": "收入/利润增速与预期基本一致。社会库存仍偏高，关注终端动销节奏。"},
        {"broker": "海通证券", "date": "2026-04-18", "rating": "优于大市", "prev_rating": "优于大市", "target": 2050, "prev_target": 1880, "title": "渠道改革深化，产品矩阵扩展", "summary": "i茅台持续贡献增量，系列酒增速超30%。上调目标价至2050元。"},
    ],
    "300750": [
        {"broker": "中信证券", "date": "2026-04-20", "rating": "买入", "prev_rating": "买入", "target": 280, "prev_target": 250, "title": "海外订单超预期，上调盈利预测", "summary": "欧洲车企大单锁定5年需求。上调2026E净利至480亿，目标价280元。"},
        {"broker": "招商证券", "date": "2026-04-16", "rating": "买入", "prev_rating": "强烈推荐", "target": 260, "prev_target": 240, "title": "年报高增长，储能成第二曲线", "summary": "储能收入同比+105%，占比升至18%。全球份额稳固，盈利韧性超预期。"},
        {"broker": "中金公司", "date": "2026-04-12", "rating": "推荐", "prev_rating": "推荐", "target": 250, "prev_target": 230, "title": "技术领先驱动溢价，维持推荐", "summary": "神行/麒麟电池放量，CTP3.0降本5%+。看好固态电池中期突破。"},
        {"broker": "国盛证券", "date": "2026-04-22", "rating": "买入", "prev_rating": "增持", "target": 275, "prev_target": 220, "title": "上调至买入，海外拐点已现", "summary": "欧洲匈牙利工厂投产在即，北美产能规划加速。评级上调至买入。"},
    ],
}


def get_financial_reports(code: str) -> list[dict]:
    return FINANCIAL_REPORTS.get(code, [])


def get_research_reports(code: str) -> list[dict]:
    return RESEARCH_REPORTS.get(code, [])


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


def get_financial(code: str) -> Optional[dict]:
    real = _fetch_real_financial(code)
    if real:
        return real
    mock = SAMPLE_FINANCIALS.get(code)
    if mock:
        mock["data_source"] = "mock"
    return mock


def get_expectations(code: str) -> list[dict]:
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
    except Exception:
        pass
    return ANALYST_EXPECTATIONS.get(code, [])


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
) -> list[dict]:
    result = []
    for code, fin in SAMPLE_FINANCIALS.items():
        if min_pe <= fin["pe"] <= max_pe and fin["roe"] >= min_roe and fin["div_yield"] >= min_div:
            result.append(fin)
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
