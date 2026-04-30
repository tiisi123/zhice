from __future__ import annotations

from datetime import datetime, date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Stock(BaseModel):
    code: str = Field(description="6位股票代码")
    name: str = ""
    price: float = 0.0
    change_rate: float = Field(0.0, description="涨跌幅(%)")
    turnover_rate: float = Field(0.0, description="换手率(%)")
    volume: float = Field(0.0, description="成交额(元)")
    market_cap: float = Field(0.0, description="流通市值(元)")
    limit_type: Optional[str] = Field(None, description="涨停/跌停/炸板")
    limit_reason: Optional[str] = Field(None, description="涨停原因")
    board_count: int = Field(0, description="连板次数")
    seal_amount: float = Field(0.0, description="封单金额(元)")
    theme_ids: list[str] = Field(default_factory=list)


class LimitUpStock(Stock):
    seal_time: Optional[str] = Field(None, description="最后封板时间 HH:MM:SS")
    first_seal_time: Optional[str] = Field(None, description="首次封板时间")
    open_count: int = Field(0, description="开板次数")
    seal_ratio: float = Field(0.0, description="封单比")
    first_plate_name: Optional[str] = Field(None, description="首个涨停板块")
    non_restricted_capital: float = 0.0
    total_capital: float = 0.0


class BrokenStock(Stock):
    broken_time: Optional[str] = Field(None, description="炸板时间 HH:MM:SS")
    broken_reason: Optional[str] = None
    combined_reason: Optional[str] = None
    related_plates: list[str] = Field(default_factory=list)


class Theme(BaseModel):
    id: str
    name: str = ""
    hot_num: float = Field(0.0, description="题材总热度")
    limit_up_count: int = Field(0, description="题材内涨停数")
    stage: Optional[str] = Field(None, description="发酵/启动/高潮/退潮")
    create_time: Optional[datetime] = None


class Sector(BaseModel):
    id: str
    name: str = ""
    intensity: float = Field(0.0, description="概念强度")
    change_rate: float = 0.0
    net_inflow: float = Field(0.0, description="主力净流入")
    stock_count: int = 0


class MarketSummary(BaseModel):
    trade_date: date
    up_count: int = 0
    down_count: int = 0
    limit_up_count: int = 0
    limit_down_count: int = 0
    broken_count: int = 0
    broken_rate: float = 0.0
    sentiment_score: float = Field(0.0, description="市场情绪分")
    total_volume: float = 0.0
    north_flow: float = 0.0


class Alert(BaseModel):
    stock_code: str
    stock_name: str = ""
    alert_type: str = Field(description="radar/multiple/severe")
    content: str = ""
    deviate_value: float = 0.0
    time: Optional[str] = None


class HotStock(BaseModel):
    code: str
    name: str = ""
    plate_name: Optional[str] = None
    reason: Optional[str] = None
    change_rate: float = 0.0
    turnover_ratio: float = 0.0
    time: Optional[str] = None


class ConnectorResponse(BaseModel):
    source: str
    trade_date: Optional[str] = None
    pulled_at: datetime = Field(default_factory=datetime.now)
    data: list[dict] = Field(default_factory=list)
    raw: Optional[dict] = None


# M001/S02 D004 数据契约 SSOT —— 28 路由响应统一 enum + meta 模型
# 参见 .gsd/DECISIONS.md::D004，前端 apps/web/src/api/types.ts 同名导出保持对齐
DataStatus = Literal["real", "mock", "fallback", "unavailable", "empty", "error"]


class ApiMeta(BaseModel):
    data_status: DataStatus
    source: str
    mock: bool = False
    message: str = ""
