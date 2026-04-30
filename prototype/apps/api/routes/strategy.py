from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Body, HTTPException

from apps.api.auth import consume_quota
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
    return {"templates": result}


@router.post("/run")
def run_backtest(dsl: dict = Body(...), years: int = Query(3), _user: dict = Depends(consume_quota("backtest"))):
    try:
        strategy = StrategyDSL(**dsl)
        result = _engine.run(strategy, years)
        return {"result": result.to_dict(), "data_status": "ok", "source": result.data_source}
    except BacktestDataUnavailable as e:
        return {
            "result": None,
            "data_status": "unavailable",
            "source": "tushare",
            "message": str(e),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"回测执行失败: {str(e)}")


@router.post("/run-template")
def run_template(template_name: str = Query(...), years: int = Query(3), _user: dict = Depends(consume_quota("backtest"))):
    dsl = STRATEGY_TEMPLATES.get(template_name)
    if not dsl:
        raise HTTPException(status_code=404, detail=f"模板 '{template_name}' 不存在，可选: {list(STRATEGY_TEMPLATES.keys())}")
    try:
        result = _engine.run(dsl, years)
        analysis = _analyst.analyze_result(result.to_dict())
        return {"result": result.to_dict(), "analysis": analysis, "data_status": "ok", "source": result.data_source}
    except BacktestDataUnavailable as e:
        return {
            "result": None,
            "analysis": "",
            "data_status": "unavailable",
            "source": "tushare",
            "message": str(e),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模板回测失败: {str(e)}")


@router.post("/analyze")
def analyze_result(result: dict = Body(...)):
    try:
        analysis = _analyst.analyze_result(result)
        return {"analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
