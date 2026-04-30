from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class ConditionRule(BaseModel):
    gte: Optional[float] = None
    lte: Optional[float] = None
    eq: Optional[str] = None
    rank: Optional[str] = None


class SelectConditions(BaseModel):
    board_count: Optional[ConditionRule] = Field(None, alias="连板次数")
    theme_hot: Optional[ConditionRule] = Field(None, alias="题材热度")
    is_leader: Optional[bool] = Field(None, alias="龙头标签")
    limit_reason: Optional[str] = Field(None, alias="涨停原因")
    sector: Optional[str] = Field(None, alias="板块")
    turnover_rate: Optional[ConditionRule] = Field(None, alias="换手率")
    seal_amount: Optional[ConditionRule] = Field(None, alias="封单金额")
    market_cap: Optional[ConditionRule] = Field(None, alias="市值")

    model_config = {"populate_by_name": True}


class EntryConditions(BaseModel):
    condition: str = ""
    open_change: Optional[ConditionRule] = Field(None, alias="开盘涨幅")
    volume: Optional[ConditionRule] = Field(None, alias="成交额")

    model_config = {"populate_by_name": True}


class ExitConditions(BaseModel):
    take_profit: float = Field(15, alias="止盈")
    stop_loss: float = Field(-5, alias="止损")
    max_hold_days: int = Field(3, alias="持有天数上限")

    model_config = {"populate_by_name": True}


class PositionConfig(BaseModel):
    per_stock: float = Field(20, alias="单票仓位")
    max_total: float = Field(60, alias="总仓位上限")

    model_config = {"populate_by_name": True}


class EnvironmentConditions(BaseModel):
    sentiment: Optional[ConditionRule] = Field(None, alias="情绪评级")
    market_change: Optional[ConditionRule] = Field(None, alias="大盘涨幅")

    model_config = {"populate_by_name": True}


class StrategyDSL(BaseModel):
    name: str = ""
    select: Optional[SelectConditions] = None
    entry: Optional[EntryConditions] = None
    exit: ExitConditions = ExitConditions()
    position: PositionConfig = PositionConfig()
    environment: Optional[EnvironmentConditions] = None


STRATEGY_TEMPLATES = {
    "涨停次日高开": StrategyDSL(
        name="涨停次日高开卖出",
        select=SelectConditions(**{"连板次数": ConditionRule(gte=1)}),
        entry=EntryConditions(condition="涨停买入", **{"开盘涨幅": ConditionRule(gte=0)}),
        exit=ExitConditions(**{"止盈": 8, "止损": -3, "持有天数上限": 1}),
        position=PositionConfig(**{"单票仓位": 10, "总仓位上限": 30}),
    ),
    "连板龙头低吸": StrategyDSL(
        name="连板龙头首次分歧低吸",
        select=SelectConditions(**{"连板次数": ConditionRule(gte=3), "龙头标签": True}),
        entry=EntryConditions(condition="分歧转一致", **{"开盘涨幅": ConditionRule(lte=3)}),
        exit=ExitConditions(**{"止盈": 15, "止损": -5, "持有天数上限": 3}),
        position=PositionConfig(**{"单票仓位": 20, "总仓位上限": 60}),
    ),
    "题材轮动跟随": StrategyDSL(
        name="题材轮动跟随",
        select=SelectConditions(**{"题材热度": ConditionRule(rank="top3")}),
        entry=EntryConditions(condition="题材启动首日"),
        exit=ExitConditions(**{"止盈": 10, "止损": -5, "持有天数上限": 5}),
    ),
    "首阴低吸": StrategyDSL(
        name="强势股首阴低吸",
        select=SelectConditions(**{"连板次数": ConditionRule(gte=2), "换手率": ConditionRule(lte=15)}),
        entry=EntryConditions(condition="首次收阴低开", **{"开盘涨幅": ConditionRule(lte=-2)}),
        exit=ExitConditions(**{"止盈": 10, "止损": -4, "持有天数上限": 2}),
        position=PositionConfig(**{"单票仓位": 15, "总仓位上限": 45}),
        environment=EnvironmentConditions(**{"情绪评级": ConditionRule(gte=2)}),
    ),
    "趋势突破放量": StrategyDSL(
        name="趋势突破放量追涨",
        select=SelectConditions(**{"换手率": ConditionRule(gte=5), "市值": ConditionRule(gte=50)}),
        entry=EntryConditions(condition="突破前高放量", **{"成交额": ConditionRule(gte=3)}),
        exit=ExitConditions(**{"止盈": 12, "止损": -5, "持有天数上限": 5}),
        position=PositionConfig(**{"单票仓位": 15, "总仓位上限": 60}),
    ),
    "炸板反包": StrategyDSL(
        name="炸板次日反包",
        select=SelectConditions(**{"连板次数": ConditionRule(gte=1), "封单金额": ConditionRule(gte=5000)}),
        entry=EntryConditions(condition="炸板次日低开后拉升", **{"开盘涨幅": ConditionRule(lte=0)}),
        exit=ExitConditions(**{"止盈": 8, "止损": -4, "持有天数上限": 1}),
        position=PositionConfig(**{"单票仓位": 10, "总仓位上限": 30}),
    ),
}
