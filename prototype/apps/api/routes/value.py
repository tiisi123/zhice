from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query, HTTPException

from apps.api.utils.contract import wrap_contract
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


def _financial_meta_d004(fin: dict) -> tuple[str, bool, str]:
    """Return (source, sample_mode, base_message) for D004 wrap_contract calls.

    sample_mode=true 表示数据来自样例（sample），对应 status='mock' 且 mock 标志为真；
    sample_mode=false 表示真实源（tushare/eastmoney 等），对应 status='real' 且 mock 标志为假。
    """
    src = fin.get("data_source") or "unknown"
    sample_mode = src == "mock"
    return (
        "sample_financials" if sample_mode else src,
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


def _get_best_financial_with_status(code: str) -> tuple[Optional[dict], bool]:
    """Returns (financial_data, tushare_attempted_failed).

    tushare_attempted_failed=True iff TUSHARE was configured (token set) but the call
    yielded no usable data (network error, bad token, or empty response). Lets the
    caller surface D004 'fallback' instead of silently returning 'mock'.
    """
    fin = get_financial(code)
    if not fin or fin.get("data_source") == "mock":
        try:
            from packages.connectors.registry import get_tushare

            ts = get_tushare()
            if ts.configured:
                ts_fin = _fetch_tushare_financial(code)
                if ts_fin:
                    return ts_fin, False
                return fin, True
        except Exception:
            return fin, True
    return fin, False


def _get_best_financial(code: str) -> Optional[dict]:
    fin, _ = _get_best_financial_with_status(code)
    return fin


@router.get("/financial/{code}")
def financial_detail(code: str):
    try:
        fin, tushare_failed = _get_best_financial_with_status(code)
        if not fin:
            raise HTTPException(status_code=404, detail=f"暂无 {code} 的财务数据")
        src, sample_mode, msg = _financial_meta_d004(fin)
        if tushare_failed and sample_mode:
            return wrap_contract(
                fin,
                source=src,
                status="fallback",
                mock=False,
                message="TUSHARE 数据源不可用（token 失效或网络问题），已降级为样例财务数据",
            )
        return wrap_contract(
            fin,
            source=src,
            status="mock" if sample_mode else "real",
            mock=sample_mode,
            message=msg,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {str(e)}")


@router.get("/expectations/{code}")
def analyst_expectations(code: str):
    try:
        exps = get_expectations(code)
        sample_mode = bool(exps) and not any(item.get("data_source") == "dfcf" for item in exps)
        if sample_mode:
            status = "mock"
            src = "sample_analyst_expectations"
            msg = "东方财富研报不可用，当前为静态卖方预期样例"
        elif exps:
            status = "real"
            src = "dfcf"
            msg = ""
        else:
            status = "empty"
            src = "dfcf"
            msg = ""
        return wrap_contract(
            exps,
            source=src,
            status=status,
            mock=sample_mode,
            message=msg,
            code=code,
            expectations=exps,
            count=len(exps),
        )
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
        base_src, sample_mode, _ = _financial_meta_d004(fin)
        return wrap_contract(
            result,
            source=f"{base_src}+dcf_rule",
            status="mock" if sample_mode else "real",
            mock=sample_mode,
            message="DCF 为规则推演，需结合假设参数使用",
            code=code,
            name=fin["name"],
            dcf=result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DCF计算失败: {str(e)}")


@router.get("/expectation-gap/{code}")
def expectation_gap(code: str, actual_eps: float = Query(0)):
    try:
        result = calc_expectation_gap(code, actual_eps)
        return wrap_contract(
            result,
            source="expectation_gap_rule",
            status="real",
            mock=False,
            message="基于输入 EPS 与卖方预期的规则推演",
            code=code,
        )
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
        return wrap_contract(
            stocks,
            source="sample_financials",
            status="mock" if stocks else "empty",
            mock=bool(stocks),
            message="价值筛选当前仅覆盖样例财务池",
            count=len(stocks),
            stocks=stocks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"筛选失败: {str(e)}")


@router.get("/forecast/{code}")
def financial_forecast(code: str):
    try:
        result = forecast_financials(code)
        sample_mode = "error" not in result
        return wrap_contract(
            result,
            source="sample_financials+forecast_rule",
            status="mock" if sample_mode else "empty",
            mock=sample_mode,
            message="财务预测为固定情景规则推演",
            code=code,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"财务预测失败: {str(e)}")


@router.get("/reports/{code}")
def financial_reports(code: str):
    try:
        reports = get_financial_reports(code)
        return wrap_contract(
            reports,
            source="sample_financial_reports",
            status="mock" if reports else "empty",
            mock=bool(reports),
            message="财报事件为静态样例",
            code=code,
            reports=reports,
            count=len(reports),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财报数据失败: {str(e)}")


@router.get("/research/{code}")
def research_reports(code: str):
    try:
        reports = get_research_reports(code)
        return wrap_contract(
            reports,
            source="sample_research_reports",
            status="mock" if reports else "empty",
            mock=bool(reports),
            message="研报列表为静态样例",
            code=code,
            reports=reports,
            count=len(reports),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取研报数据失败: {str(e)}")


@router.get("/alternative/{code}")
def alternative_data(code: str):
    try:
        data = get_alternative_data(code)
        return wrap_contract(
            data,
            source="sample_alternative_data",
            status="mock" if data else "empty",
            mock=bool(data),
            message="另类数据为静态样例，真实源待接入",
            code=code,
            count=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取另类数据失败: {str(e)}")


@router.get("/expectation-history/{code}")
def expectation_history(code: str):
    try:
        data = get_expectation_history(code)
        return wrap_contract(
            data,
            source="sample_expectation_history",
            status="mock" if data else "empty",
            mock=bool(data),
            message="卖方预期历史为静态样例",
            code=code,
            history=data,
            count=len(data),
        )
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
        base_src, sample_mode, _ = _financial_meta_d004(fin)
        return wrap_contract(
            report,
            source=f"{base_src}+llm",
            status="mock" if sample_mode else "real",
            mock=sample_mode,
            message="AI 分析为基于基础财务与卖方预期的文本推演",
            code=code,
            name=fin["name"],
            analysis=report,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")


@router.get("/diffusion")
def diffusion_index():
    try:
        industries = get_industry_prosperity()
        result = calc_diffusion_index(industries)
        sample_mode = True  # 静态行业景气矩阵 → 样例数据
        extras = {
            k: v for k, v in result.items()
            if k not in ("source", "data_status", "mock", "message", "updated_at")
        }
        return wrap_contract(
            result,
            source="static_industry_prosperity+diffusion_rule",
            status="mock",
            mock=sample_mode,
            message="扩散指数基于静态行业景气矩阵推演",
            **extras,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩散指数计算失败: {str(e)}")


@router.get("/turning-points")
def turning_points(threshold: int = Query(10)):
    try:
        industries = get_industry_prosperity()
        alerts = detect_turning_points(industries, threshold)
        return wrap_contract(
            alerts,
            source="static_industry_prosperity+turning_rule",
            status="mock" if alerts else "empty",
            mock=bool(alerts),
            message="拐点预警基于静态行业景气矩阵推演",
            alerts=alerts,
            count=len(alerts),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"拐点检测失败: {str(e)}")


@router.get("/macro-transmission/{change}")
def macro_transmission(change: str):
    try:
        chain = macro_to_industry_transmission(change)
        return wrap_contract(
            chain,
            source="macro_transmission_rules",
            status="real",
            mock=False,
            message="宏观传导为固定规则推演",
            macro_change=change,
            transmission=chain,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"宏观传导分析失败: {str(e)}")


@router.get("/chain-prosperity/{chain_name}")
def chain_prosperity(chain_name: str):
    try:
        data = chain_prosperity_transmission(chain_name)
        if not data:
            raise HTTPException(status_code=404, detail=f"无 {chain_name} 的景气传导数据")
        sample_mode = True  # chain_prosperity_rules 为静态规则 → 样例数据
        return wrap_contract(
            data,
            source="chain_prosperity_rules",
            status="mock",
            mock=sample_mode,
            message="产业链景气为固定规则推演，真实中观源待接入",
            chain=chain_name,
            streams=data,
        )
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
        sample_mode = True  # static_industry_prosperity → 样例数据
        return wrap_contract(
            report,
            source="static_industry_prosperity+llm",
            status="mock",
            mock=sample_mode,
            message="周报基于静态景气矩阵和 AI 文本推演",
            diffusion=diffusion,
            turning_points=turning,
            report=report,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成周报失败: {str(e)}")
