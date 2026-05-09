from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from apps.api.utils.contract import wrap_contract
from packages.backtest.engine import BacktestDataUnavailable
from packages.features.backtest import run_board_backtest, run_etf_backtest

router = APIRouter()

_MODE_TO_D004: dict[str, tuple[str, bool]] = {
    "live": ("real", False),
    "hybrid": ("fallback", False),
    "sample": ("mock", True),
}

_VALID_SUB_STRATEGIES = ("首板", "二板", "龙头")


@router.get("/board-strategy")
def board_strategy(
    mode: str = Query("auto", description="auto/live/sample"),
    sub_strategy: str = Query("首板"),
    years: int = Query(1),
):
    if sub_strategy not in _VALID_SUB_STRATEGIES:
        raise HTTPException(
            status_code=400,
            detail=f"无效子策略 '{sub_strategy}'，可选: {list(_VALID_SUB_STRATEGIES)}",
        )
    try:
        data = run_board_backtest(sub_strategy=sub_strategy, mode=mode, years=years)
        status, mock_flag = _MODE_TO_D004.get(data.get("data_mode", "sample"), ("mock", True))
        return wrap_contract(
            data,
            source=data.get("data_source", "sample_engine"),
            status=status,
            mock=mock_flag,
            data_source=data.get("data_source", "sample_engine"),
            data_mode=data.get("data_mode", "sample"),
            as_of=data.get("as_of", ""),
            fallback_reason=data.get("fallback_reason", ""),
        )
    except BacktestDataUnavailable as e:
        return wrap_contract(
            None,
            source="kpl_limit_up",
            status="unavailable",
            mock=False,
            message=str(e),
            data_source="kpl_limit_up",
            data_mode="unavailable",
            as_of="",
            fallback_reason="live_data_unavailable",
        )


@router.get("/etf-rotation")
def etf_rotation_backtest(
    mode: str = Query("auto", description="auto/live/sample"),
    years: int = Query(1),
):
    try:
        data = run_etf_backtest(mode=mode, years=years)
        status, mock_flag = _MODE_TO_D004.get(data.get("data_mode", "sample"), ("mock", True))
        return wrap_contract(
            data,
            source=data.get("data_source", "sample_engine"),
            status=status,
            mock=mock_flag,
            data_source=data.get("data_source", "sample_engine"),
            data_mode=data.get("data_mode", "sample"),
            as_of=data.get("as_of", ""),
            fallback_reason=data.get("fallback_reason", ""),
        )
    except BacktestDataUnavailable as e:
        return wrap_contract(
            None,
            source="tushare_fund_daily",
            status="unavailable",
            mock=False,
            message=str(e),
            data_source="tushare_fund_daily",
            data_mode="unavailable",
            as_of="",
            fallback_reason="live_data_unavailable",
        )
