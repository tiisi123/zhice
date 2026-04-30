from __future__ import annotations

from enum import Enum


class LimitType(str, Enum):
    LIMIT_UP = "涨停"
    LIMIT_DOWN = "跌停"
    BROKEN = "炸板"


class AlertType(str, Enum):
    RADAR = "radar"
    MULTIPLE = "multiple"
    SEVERE = "severe"


class ThemeStage(str, Enum):
    FERMENT = "发酵"
    START = "启动"
    CLIMAX = "高潮"
    DECLINE = "退潮"
    END = "结束"


class SentimentLevel(str, Enum):
    FREEZING = "冰点"
    LOW = "低迷"
    NEUTRAL = "中性"
    WARM = "回暖"
    HOT = "高潮"
