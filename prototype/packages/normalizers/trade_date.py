from __future__ import annotations

from datetime import datetime, time


def ts_to_datetime(ts: int | float | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts)
    except (ValueError, OSError):
        return None


def ts_to_time_str(ts: int | float | None) -> str | None:
    dt = ts_to_datetime(ts)
    return dt.strftime("%H:%M:%S") if dt else None


def align_to_5min(dt: datetime) -> datetime:
    minute = (dt.minute // 5) * 5
    aligned = dt.replace(minute=minute, second=0, microsecond=0)
    market_close = dt.replace(hour=15, minute=0, second=0, microsecond=0)
    return min(aligned, market_close)


def parse_trade_date(s: str | None) -> str:
    if not s:
        return datetime.now().strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s
