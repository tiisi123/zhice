from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from packages.backtest.dsl_schema import StrategyDSL, STRATEGY_TEMPLATES
from packages.backtest.engine import BacktestDataUnavailable
from packages.backtest.optimizer import ParameterOptimizer, SimulatedTrader

router = APIRouter()
_optimizer = ParameterOptimizer()
_traders: dict[str, SimulatedTrader] = {}
_MAX_SESSIONS = 50


@router.post("/optimize")
def optimize_strategy(template_name: str = Query("涨停次日高开"), years: int = Query(3)):
    dsl = STRATEGY_TEMPLATES.get(template_name)
    if not dsl:
        raise HTTPException(status_code=404, detail=f"模板 '{template_name}' 不存在")
    try:
        results = _optimizer.grid_search(dsl, years=years)
        return {
            "template": template_name,
            "total_combinations": len(results),
            "best_5": results[:5],
            "worst_3": results[-3:],
            "source": "tushare",
            "data_status": "ok",
        }
    except BacktestDataUnavailable as e:
        return {
            "template": template_name,
            "total_combinations": 0,
            "best_5": [],
            "worst_3": [],
            "source": "tushare",
            "data_status": "unavailable",
            "message": str(e),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"参数优化失败: {str(e)}")


@router.post("/sim/create")
def create_sim(capital: float = Query(1_000_000)):
    import uuid
    # 清理过多的会话
    if len(_traders) >= _MAX_SESSIONS:
        oldest_key = next(iter(_traders))
        del _traders[oldest_key]
    sid = str(uuid.uuid4())[:8]
    _traders[sid] = SimulatedTrader(capital)
    return {"session_id": sid, "status": _traders[sid].status()}


@router.post("/sim/{sid}/buy")
def sim_buy(sid: str, code: str = Query(...), name: str = Query(""), price: float = Query(...), amount: float = Query(100000)):
    trader = _traders.get(sid)
    if not trader:
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        result = trader.buy(code, name, price, amount)
        return {"trade": result, "status": trader.status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"买入失败: {str(e)}")


@router.post("/sim/{sid}/sell")
def sim_sell(sid: str, code: str = Query(...), price: float = Query(...)):
    trader = _traders.get(sid)
    if not trader:
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        result = trader.sell(code, price)
        return {"trade": result, "status": trader.status()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"卖出失败: {str(e)}")


@router.post("/sim/{sid}/next-day")
def sim_next_day(sid: str):
    trader = _traders.get(sid)
    if not trader:
        raise HTTPException(status_code=404, detail="会话不存在")
    trader.next_day()
    return {"status": trader.status()}


@router.get("/sim/{sid}/status")
def sim_status(sid: str):
    trader = _traders.get(sid)
    if not trader:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": trader.status()}


@router.delete("/sim/{sid}")
def delete_sim(sid: str):
    if sid not in _traders:
        raise HTTPException(status_code=404, detail="会话不存在")
    del _traders[sid]
    return {"message": "会话已删除"}
