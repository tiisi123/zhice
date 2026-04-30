from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query, HTTPException

from packages.features.valuation import (
    get_financial, get_expectations, calc_dcf,
    calc_expectation_gap, screen_value_stocks, forecast_financials,
    get_financial_reports, get_research_reports,
)
from packages.features.macro.advanced import (
    calc_diffusion_index, detect_turning_points,
    macro_to_industry_transmission, chain_prosperity_transmission,
)
from packages.features.macro.data import get_industry_prosperity, get_alternative_data, get_expectation_history
from apps.ai.agents.agents import BacktestAnalystAgent

router = APIRouter()
_analyst = BacktestAnalystAgent()


def _meta(source: str, data_status: str, sample_mode: bool, message: str = "") -> dict:
    return {
        "source": source,
        "data_status": data_status,
        "mock": sample_mode,
        "message": message,
    }


def _financial_meta(fin: dict) -> dict:
    source = fin.get("data_source") or "unknown"
    sample_mode = source == "mock"
    return _meta(
        "sample_financials" if sample_mode else source,
        "stale" if sample_mode else "ok",
        sample_mode,
        "东方财富不可用或无覆盖，当前为样例财务数据" if sample_mode else "",
    )


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fetch_tushare_financial(code: str) -> Optional[dict]:
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

        revenue = _to_float(income.get("total_revenue") or income.get("revenue"))
        net_profit = _to_float(income.get("n_income_attr_p") or income.get("n_income"))
        market_cap = _to_float(daily.get("total_mv")) * 10000
        fcf = _to_float(indicator.get("fcff") or indicator.get("fcfe"))
        if fcf <= 0 and net_profit:
            fcf = net_profit * 0.8

        return {
            "code": code,
            "name": basic.get("name") or daily.get("ts_code") or code,
            "industry": basic.get("industry", ""),
            "revenue": revenue,
            "revenue_yoy": _to_float(indicator.get("or_yoy")),
            "net_profit": net_profit,
            "net_profit_yoy": _to_float(indicator.get("netprofit_yoy")),
            "gross_margin": _to_float(indicator.get("grossprofit_margin")),
            "net_margin": _to_float(indicator.get("netprofit_margin")),
            "roe": _to_float(indicator.get("roe_dt") or indicator.get("roe")),
            "roa": _to_float(indicator.get("roa")),
            "pe": _to_float(daily.get("pe_ttm") or daily.get("pe")),
            "pb": _to_float(daily.get("pb")),
            "ps": _to_float(daily.get("ps_ttm") or daily.get("ps")),
            "pe_percentile": 50,
            "pb_percentile": 50,
            "div_yield": _to_float(daily.get("dv_ttm") or daily.get("dv_ratio")),
            "debt_ratio": _to_float(indicator.get("debt_to_assets")),
            "fcf": fcf,
            "eps": _to_float(indicator.get("dt_eps") or indicator.get("eps")),
            "market_cap": market_cap,
            "latest_trade_date": daily.get("trade_date", ""),
            "latest_report_date": indicator.get("end_date") or income.get("end_date") or "",
            "highlights": [],
            "risks": [],
            "data_source": "tushare",
        }
    except Exception:
        return None


def _get_best_financial(code: str) -> Optional[dict]:
    fin = get_financial(code)
    if not fin or fin.get("data_source") == "mock":
        ts_fin = _fetch_tushare_financial(code)
        if ts_fin:
            return ts_fin
    return fin


@router.get("/financial/{code}")
def financial_detail(code: str):
    try:
        fin = _get_best_financial(code)
        if not fin:
            raise HTTPException(status_code=404, detail=f"暂无 {code} 的财务数据")
        return {"data": fin, **_financial_meta(fin)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {str(e)}")


@router.get("/expectations/{code}")
def analyst_expectations(code: str):
    try:
        exps = get_expectations(code)
        sample_mode = bool(exps) and not any(item.get("data_source") == "dfcf" for item in exps)
        return {
            "code": code,
            "expectations": exps,
            "count": len(exps),
            **_meta(
                "sample_analyst_expectations" if sample_mode else "dfcf",
                "stale" if sample_mode else ("empty" if not exps else "ok"),
                sample_mode,
                "东方财富研报不可用，当前为静态卖方预期样例" if sample_mode else "",
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预期数据失败: {str(e)}")


@router.get("/dcf/{code}")
def dcf_valuation(
    code: str,
    growth: float = Query(0.1),
    discount: float = Query(0.08),
    terminal: float = Query(0.03),
):
    try:
        fin = _get_best_financial(code)
        if not fin:
            raise HTTPException(status_code=404, detail="个股不存在")
        result = calc_dcf(fin["fcf"], growth, discount, terminal_growth=terminal)
        base_meta = _financial_meta(fin)
        return {
            "code": code,
            "name": fin["name"],
            "dcf": result,
            **_meta(
                f"{base_meta['source']}+dcf_rule",
                "stale" if base_meta["mock"] else "ok",
                base_meta["mock"],
                "DCF 为规则推演，需结合假设参数使用",
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DCF计算失败: {str(e)}")


@router.get("/expectation-gap/{code}")
def expectation_gap(code: str, actual_eps: float = Query(0)):
    try:
        result = calc_expectation_gap(code, actual_eps)
        return {
            "code": code,
            "data": result,
            **_meta("expectation_gap_rule", "ok", sample_mode := False, "基于输入 EPS 与卖方预期的规则推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预期差计算失败: {str(e)}")


@router.get("/screen")
def value_screen(
    max_pe: float = Query(30),
    min_roe: float = Query(15),
    min_div: float = Query(1.0),
):
    try:
        stocks = screen_value_stocks(max_pe=max_pe, min_roe=min_roe, min_div=min_div)
        sample_mode = True
        return {
            "count": len(stocks),
            "stocks": stocks,
            **_meta("sample_financials", "stale", sample_mode, "价值筛选当前仅覆盖样例财务池"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")


@router.get("/forecast/{code}")
def financial_forecast(code: str):
    try:
        result = forecast_financials(code)
        sample_mode = "error" not in result
        return {
            "code": code,
            "data": result,
            **_meta("sample_financials+forecast_rule", "stale" if sample_mode else "empty", sample_mode, "财务预测为固定情景规则推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"财务预测失败: {str(e)}")


@router.get("/reports/{code}")
def financial_reports(code: str):
    try:
        reports = get_financial_reports(code)
        sample_mode = bool(reports)
        return {
            "code": code,
            "reports": reports,
            "count": len(reports),
            **_meta("sample_financial_reports", "stale" if sample_mode else "empty", sample_mode, "财报事件为静态样例"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财报数据失败: {str(e)}")


@router.get("/research/{code}")
def research_reports(code: str):
    try:
        reports = get_research_reports(code)
        sample_mode = bool(reports)
        return {
            "code": code,
            "reports": reports,
            "count": len(reports),
            **_meta("sample_research_reports", "stale" if sample_mode else "empty", sample_mode, "研报列表为静态样例"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取研报数据失败: {str(e)}")


@router.get("/alternative/{code}")
def alternative_data(code: str):
    try:
        data = get_alternative_data(code)
        sample_mode = bool(data)
        return {
            "code": code,
            "data": data,
            "count": len(data),
            **_meta("sample_alternative_data", "stale" if sample_mode else "empty", sample_mode, "另类数据为静态样例，真实源待接入"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取另类数据失败: {str(e)}")


@router.get("/expectation-history/{code}")
def expectation_history(code: str):
    try:
        data = get_expectation_history(code)
        sample_mode = bool(data)
        return {
            "code": code,
            "history": data,
            "count": len(data),
            **_meta("sample_expectation_history", "stale" if sample_mode else "empty", sample_mode, "卖方预期历史为静态样例"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预期历史失败: {str(e)}")


@router.get("/ai-analysis/{code}")
def ai_financial_analysis(code: str):
    try:
        fin = _get_best_financial(code)
        if not fin:
            raise HTTPException(status_code=404, detail=f"暂无 {code} 的财务数据")
        exps = get_expectations(code)
        context = f"""个股: {fin['name']}({fin['code']})
核心指标: PE={fin['pe']}, PB={fin['pb']}, ROE={fin['roe']}%, 毛利率={fin['gross_margin']}%, 净利率={fin['net_margin']}%
增长: 营收YoY={fin['revenue_yoy']}%, 净利YoY={fin['net_profit_yoy']}%
估值分位: PE={fin['pe_percentile']}%, PB={fin['pb_percentile']}%
股息率: {fin['div_yield']}%, 资产负债率: {fin['debt_ratio']}%
亮点: {', '.join(fin.get('highlights', []))}
风险: {', '.join(fin.get('risks', []))}
券商预期: {', '.join(f"{e['broker']}目标价{e['target']}" for e in exps)}"""
        from apps.ai.agents.llm_client import llm
        report = llm.chat(
            f"请对以下个股的基本面做深度分析，输出300字以内的结构化报告（包含：核心逻辑、估值判断、风险提示、操作建议）：\n{context}"
        )
        base_meta = _financial_meta(fin)
        return {
            "code": code,
            "name": fin["name"],
            "analysis": report,
            **_meta(
                f"{base_meta['source']}+llm",
                "stale" if base_meta["mock"] else "ok",
                base_meta["mock"],
                "AI 分析为基于基础财务与卖方预期的文本推演",
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.get("/diffusion")
def diffusion_index():
    try:
        industries = get_industry_prosperity()
        sample_mode = True
        return {
            **calc_diffusion_index(industries),
            **_meta("static_industry_prosperity+diffusion_rule", "stale", sample_mode, "扩散指数基于静态行业景气矩阵推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩散指数计算失败: {str(e)}")


@router.get("/turning-points")
def turning_points(threshold: int = Query(10)):
    try:
        industries = get_industry_prosperity()
        alerts = detect_turning_points(industries, threshold)
        sample_mode = True
        return {
            "alerts": alerts,
            "count": len(alerts),
            **_meta("static_industry_prosperity+turning_rule", "stale", sample_mode, "拐点预警基于静态行业景气矩阵推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拐点检测失败: {str(e)}")


@router.get("/macro-transmission/{change}")
def macro_transmission(change: str):
    try:
        chain = macro_to_industry_transmission(change)
        return {
            "macro_change": change,
            "transmission": chain,
            **_meta("macro_transmission_rules", "ok", sample_mode := False, "宏观传导为固定规则推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"宏观传导分析失败: {str(e)}")


@router.get("/chain-prosperity/{chain_name}")
def chain_prosperity(chain_name: str):
    try:
        data = chain_prosperity_transmission(chain_name)
        if not data:
            raise HTTPException(status_code=404, detail=f"无 {chain_name} 的景气传导数据")
        sample_mode = True
        return {
            "chain": chain_name,
            "streams": data,
            **_meta("chain_prosperity_rules", "stale", sample_mode, "产业链景气为固定规则推演，真实中观源待接入"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"产业链景气分析失败: {str(e)}")


@router.get("/weekly-report")
def generate_weekly_report():
    try:
        industries = get_industry_prosperity()
        diffusion = calc_diffusion_index(industries)
        turning = detect_turning_points(industries)

        context = f"""景气扩散指数: {diffusion['diffusion_index']} ({diffusion['interpretation']})
上行行业: {diffusion['up_count']}个, 下行: {diffusion['down_count']}个
拐点预警: {len(turning)}个行业出现拐点
"""
        for t in turning:
            industry = t.get('industry', '未知')
            direction = t.get('direction', '未知')
            q3 = t.get('q3', t.get('prev', 'N/A'))
            q4 = t.get('q4', t.get('current', 'N/A'))
            context += f"  - {industry}: {direction} (前值={q3}→现值={q4})\n"

        from apps.ai.agents.llm_client import llm
        report = llm.chat(f"根据以下行业景气度数据生成本周景气度周报摘要:\n{context}\n要求200字以内，结构化输出。")
        sample_mode = True
        return {
            "diffusion": diffusion,
            "turning_points": turning,
            "report": report,
            **_meta("static_industry_prosperity+llm", "stale", sample_mode, "周报基于静态景气矩阵和 AI 文本推演"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成周报失败: {str(e)}")
