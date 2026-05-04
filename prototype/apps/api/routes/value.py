from __future__ import annotations

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


@router.get("/financial/{code}")
def financial_detail(code: str):
    try:
        fin = get_financial(code)
        if not fin:
            return wrap_contract(
                {},
                source="dfcf",
                status="unavailable",
                mock=False,
                message=f"DFCF 和 TuShare 均无法获取 {code} 的财务数据",
            )
        src = fin.get("data_source") or "unknown"
        return wrap_contract(
            fin,
            source=src,
            status="real",
            mock=False,
            message="",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取财务数据失败: {str(e)}")


@router.get("/expectations/{code}")
def analyst_expectations(code: str):
    try:
        exps = get_expectations(code)
        return wrap_contract(
            exps,
            source="dfcf",
            status="real" if exps else "unavailable",
            mock=False,
            message="" if exps else f"DFCF 无法获取 {code} 的卖方预期",
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
        fin = get_financial(code)
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
    max_pb: float = Query(0),
    min_market_cap: float = Query(0),
):
    try:
        from packages.connectors.registry import get_tushare
        ts = get_tushare()
        tushare_configured = ts.configured
    except Exception:
        tushare_configured = False

    try:
        stocks = screen_value_stocks(
            max_pe=max_pe, min_roe=min_roe, min_div=min_div,
            max_pb=max_pb, min_market_cap=min_market_cap,
        )
        if not tushare_configured:
            return wrap_contract(
                [],
                source="tushare",
                status="unavailable",
                mock=False,
                message="TuShare 未配置（缺少 TUSHARE_TOKEN），价值筛选不可用",
                count=0,
                stocks=[],
            )
        if stocks:
            return wrap_contract(
                stocks,
                source="tushare",
                status="real",
                mock=False,
                message="",
                count=len(stocks),
                stocks=stocks,
            )
        return wrap_contract(
            [],
            source="tushare",
            status="empty",
            mock=False,
            message="TuShare 全A筛选无匹配结果（条件过严或数据缺失）",
            count=0,
            stocks=[],
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
            source="dfcf",
            status="real" if reports else "unavailable",
            mock=False,
            message="" if reports else f"DFCF 无法获取 {code} 的财报公告",
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
            source="dfcf",
            status="real" if reports else "unavailable",
            mock=False,
            message="" if reports else f"DFCF 无法获取 {code} 的研报数据",
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
            source="dfcf",
            status="real" if data else "unavailable",
            mock=False,
            message="" if data else f"DFCF 无法获取 {code} 的预期历史",
            code=code,
            history=data,
            count=len(data),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预期历史失败: {str(e)}")


@router.get("/ai-analysis/{code}")
def ai_financial_analysis(code: str):
    try:
        fin = get_financial(code)
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
        is_real = bool(industries) and industries[0].get("data_source") == "tushare"
        extras = {
            k: v for k, v in result.items()
            if k not in ("source", "data_status", "mock", "message", "updated_at")
        }
        return wrap_contract(
            result,
            source="tushare+diffusion_rule" if is_real else "static_industry_prosperity+diffusion_rule",
            status="real" if is_real else "mock",
            mock=not is_real,
            message="扩散指数基于申万行业指数实时数据" if is_real else "扩散指数基于静态行业景气矩阵推演",
            **extras,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扩散指数计算失败: {str(e)}")


@router.get("/turning-points")
def turning_points(threshold: int = Query(10)):
    try:
        industries = get_industry_prosperity()
        alerts = detect_turning_points(industries, threshold)
        is_real = bool(industries) and industries[0].get("data_source") == "tushare"
        if not alerts:
            tp_status = "empty"
        elif is_real:
            tp_status = "real"
        else:
            tp_status = "mock"
        return wrap_contract(
            alerts,
            source="tushare+turning_rule" if is_real else "static_industry_prosperity+turning_rule",
            status=tp_status,
            mock=(tp_status == "mock"),
            message="拐点预警基于申万行业指数实时数据" if is_real else "拐点预警基于静态行业景气矩阵推演",
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
        is_real = bool(industries) and industries[0].get("data_source") == "tushare"

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
        return wrap_contract(
            report,
            source="tushare+llm" if is_real else "static_industry_prosperity+llm",
            status="real" if is_real else "mock",
            mock=not is_real,
            message="周报基于申万行业指数实时数据和 AI 推演" if is_real else "周报基于静态景气矩阵和 AI 文本推演",
            diffusion=diffusion,
            turning_points=turning,
            report=report,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成周报失败: {str(e)}")
