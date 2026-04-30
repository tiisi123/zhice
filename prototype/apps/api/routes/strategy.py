from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Body, HTTPException

from apps.api.auth import consume_quota
from apps.api.utils.contract import wrap_contract
from packages.backtest.dsl_schema import StrategyDSL, STRATEGY_TEMPLATES
from packages.backtest.engine import BacktestDataUnavailable, BacktestEngine
from apps.ai.agents.agents import BacktestAnalystAgent

router = APIRouter()
_engine = BacktestEngine()
_analyst = BacktestAnalystAgent()


@router.get("/templates")
def list_templates():
    result = {}
    for name, dsl in STRATEGY_TEMPLATES.items():
        result[name] = dsl.model_dump(by_alias=True, exclude_none=True)
    return wrap_contract(
        result,
        source="static_strategy_templates",
        status="real",
        templates=result,
    )


@router.post("/run")
def run_backtest(dsl: dict = Body(...), years: int = Query(3), _user: dict = Depends(consume_quota("backtest"))):
    try:
        strategy = StrategyDSL(**dsl)
        result = _engine.run(strategy, years)
        result_dict = result.to_dict()
        return wrap_contract(
            result_dict,
            source=result.data_source or "tushare",
            status="real",
            mock=False,
            result=result_dict,
        )
    except BacktestDataUnavailable as e:
        return wrap_contract(
            None,
            source="tushare",
            status="unavailable",
            mock=False,
            message=str(e),
            result=None,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回测执行失败: {str(e)}")


@router.post("/run-template")
def run_template(template_name: str = Query(...), years: int = Query(3), _user: dict = Depends(consume_quota("backtest"))):
    dsl = STRATEGY_TEMPLATES.get(template_name)
    if not dsl:
        raise HTTPException(status_code=404, detail=f"模板 '{template_name}' 不存在，可选: {list(STRATEGY_TEMPLATES.keys())}")
    try:
        result = _engine.run(dsl, years)
        result_dict = result.to_dict()
        analysis = _analyst.analyze_result(result_dict)
        return wrap_contract(
            result_dict,
            source=result.data_source or "tushare",
            status="real",
            mock=False,
            result=result_dict,
            analysis=analysis,
        )
    except BacktestDataUnavailable as e:
        return wrap_contract(
            None,
            source="tushare",
            status="unavailable",
            mock=False,
            message=str(e),
            result=None,
            analysis="",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模板回测失败: {str(e)}")


@router.post("/analyze")
def analyze_result(result: dict = Body(...)):
    try:
        analysis = _analyst.analyze_result(result)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
