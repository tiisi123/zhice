from __future__ import annotations

from collections import Counter
from math import sqrt
import time
from typing import Any

from packages.connectors.tushare import TushareClient
from packages.features.etf.cache import load_cached_bundle, save_cached_bundle

TRADE_DATES = [
    "2026-04-17",
    "2026-04-20",
    "2026-04-21",
    "2026-04-22",
    "2026-04-23",
    "2026-04-24",
]

# 样例口径：
# - flows: 日净流入（亿元，样例）
# - turnover: 日换手率（%）
ETF_SERIES: list[dict[str, Any]] = [
    {
        "code": "588000",
        "name": "科创50ETF",
        "theme": "科技成长",
        "prices": [0.912, 0.918, 0.925, 0.936, 0.948, 0.961],
        "flows": [2.1, 2.8, 3.5, 4.1, 5.2, 5.9],
        "turnover": [1.8, 1.9, 2.1, 2.4, 2.6, 2.8],
    },
    {
        "code": "512480",
        "name": "半导体ETF",
        "theme": "硬科技",
        "prices": [0.865, 0.872, 0.88, 0.897, 0.914, 0.926],
        "flows": [1.2, 2.0, 2.8, 4.6, 6.1, 6.8],
        "turnover": [2.3, 2.5, 2.7, 3.1, 3.4, 3.7],
    },
    {
        "code": "159819",
        "name": "人工智能ETF",
        "theme": "AI算力",
        "prices": [1.023, 1.031, 1.044, 1.066, 1.089, 1.108],
        "flows": [1.8, 2.9, 4.0, 5.7, 7.2, 8.1],
        "turnover": [2.0, 2.2, 2.6, 3.1, 3.8, 4.2],
    },
    {
        "code": "159770",
        "name": "机器人ETF",
        "theme": "智能制造",
        "prices": [0.774, 0.779, 0.786, 0.803, 0.821, 0.836],
        "flows": [0.5, 1.1, 1.9, 3.6, 4.8, 5.4],
        "turnover": [1.7, 1.8, 2.0, 2.6, 2.9, 3.2],
    },
    {
        "code": "515030",
        "name": "新能源车ETF",
        "theme": "新能源",
        "prices": [1.231, 1.225, 1.218, 1.212, 1.209, 1.206],
        "flows": [-0.8, -1.1, -1.5, -1.2, -0.9, -0.6],
        "turnover": [1.9, 1.8, 1.7, 1.6, 1.5, 1.5],
    },
    {
        "code": "515790",
        "name": "光伏ETF",
        "theme": "新能源",
        "prices": [0.982, 0.974, 0.967, 0.962, 0.958, 0.954],
        "flows": [-1.2, -1.0, -0.9, -0.7, -0.5, -0.4],
        "turnover": [1.6, 1.5, 1.4, 1.4, 1.3, 1.3],
    },
    {
        "code": "512000",
        "name": "券商ETF",
        "theme": "金融",
        "prices": [0.789, 0.795, 0.803, 0.819, 0.833, 0.846],
        "flows": [0.9, 1.4, 2.0, 2.7, 3.4, 3.1],
        "turnover": [1.2, 1.3, 1.4, 1.7, 1.9, 2.0],
    },
    {
        "code": "510880",
        "name": "红利ETF",
        "theme": "高股息",
        "prices": [2.365, 2.372, 2.378, 2.382, 2.387, 2.391],
        "flows": [2.6, 2.2, 1.6, 1.0, 0.3, -0.5],
        "turnover": [0.7, 0.7, 0.8, 0.8, 0.9, 1.0],
    },
    {
        "code": "512800",
        "name": "银行ETF",
        "theme": "金融",
        "prices": [1.124, 1.128, 1.132, 1.136, 1.139, 1.141],
        "flows": [1.9, 1.7, 1.4, 1.1, 0.8, 0.2],
        "turnover": [0.6, 0.6, 0.7, 0.7, 0.8, 0.8],
    },
    {
        "code": "159992",
        "name": "创新药ETF",
        "theme": "医药",
        "prices": [0.653, 0.659, 0.662, 0.669, 0.677, 0.683],
        "flows": [0.2, 0.5, 0.8, 1.1, 1.6, 2.2],
        "turnover": [1.3, 1.4, 1.5, 1.7, 1.9, 2.2],
    },
    {
        "code": "518880",
        "name": "黄金ETF",
        "theme": "避险",
        "prices": [4.876, 4.853, 4.839, 4.812, 4.798, 4.775],
        "flows": [1.4, 0.9, 0.5, -0.4, -0.8, -1.1],
        "turnover": [1.0, 1.0, 1.1, 1.2, 1.3, 1.3],
    },
    {
        "code": "510300",
        "name": "沪深300ETF",
        "theme": "宽基",
        "prices": [3.812, 3.825, 3.839, 3.851, 3.862, 3.871],
        "flows": [1.5, 1.8, 2.0, 1.6, 1.3, 0.9],
        "turnover": [0.9, 0.9, 1.0, 1.0, 1.1, 1.1],
    },
    {
        "code": "510500",
        "name": "中证500ETF",
        "theme": "宽基",
        "prices": [5.623, 5.641, 5.662, 5.688, 5.712, 5.733],
        "flows": [0.8, 1.2, 1.5, 2.1, 2.6, 2.3],
        "turnover": [1.1, 1.1, 1.2, 1.3, 1.4, 1.5],
    },
]

ROTATION_RULES: dict[str, list[dict[str, Any]]] = {
    "510880": [
        {"target": "512000", "probability": 68, "lag_days": 1, "signal": "高股息边际流出，券商成交放大"},
        {"target": "588000", "probability": 52, "lag_days": 2, "signal": "风险偏好回升，成长风格承接"},
        {"target": "512480", "probability": 45, "lag_days": 2, "signal": "弹性科技获得增量资金"},
    ],
    "512800": [
        {"target": "512000", "probability": 58, "lag_days": 1, "signal": "金融内部切换至高弹性子板块"},
        {"target": "588000", "probability": 45, "lag_days": 2, "signal": "防御仓位向科技成长迁移"},
    ],
    "512000": [
        {"target": "588000", "probability": 62, "lag_days": 1, "signal": "券商先行后带动成长估值扩张"},
        {"target": "512480", "probability": 57, "lag_days": 1, "signal": "交易活跃后资金偏好高Beta科技"},
        {"target": "159819", "probability": 51, "lag_days": 2, "signal": "AI主题强化，资金追逐景气主线"},
    ],
    "588000": [
        {"target": "512480", "probability": 64, "lag_days": 1, "signal": "科创风格延伸至半导体子方向"},
        {"target": "159819", "probability": 60, "lag_days": 1, "signal": "算力链条共振，主题扩散"},
        {"target": "159770", "probability": 50, "lag_days": 2, "signal": "从算力向应用端智能制造外溢"},
    ],
    "512480": [
        {"target": "159819", "probability": 66, "lag_days": 1, "signal": "芯片向算力环节传导"},
        {"target": "159770", "probability": 59, "lag_days": 1, "signal": "隔夜节奏下优先跟踪次日联动方向"},
        {"target": "159992", "probability": 42, "lag_days": 2, "signal": "科技高位分歧后转向低位补涨"},
    ],
    "159819": [
        {"target": "159770", "probability": 63, "lag_days": 1, "signal": "AI应用端渗透提速"},
        {"target": "159992", "probability": 48, "lag_days": 2, "signal": "成长资金局部切向医药创新"},
        {"target": "512480", "probability": 44, "lag_days": 2, "signal": "算力链回流上游硬件"},
    ],
    "515030": [
        {"target": "512480", "probability": 41, "lag_days": 2, "signal": "新能源退潮后回流科技"},
        {"target": "159819", "probability": 45, "lag_days": 2, "signal": "产业政策切换带来风格再定价"},
        {"target": "510880", "probability": 38, "lag_days": 1, "signal": "风险偏好下降转向防御资产"},
    ],
    "515790": [
        {"target": "515030", "probability": 40, "lag_days": 1, "signal": "新能源内部轮动"},
        {"target": "512480", "probability": 37, "lag_days": 2, "signal": "景气切换至硬科技"},
    ],
    "518880": [
        {"target": "510880", "probability": 55, "lag_days": 1, "signal": "避险资产流向高股息"},
        {"target": "512800", "probability": 46, "lag_days": 1, "signal": "避险仓位部分回流大金融"},
    ],
    "159992": [
        {"target": "512480", "probability": 36, "lag_days": 2, "signal": "医药轮动后回流科技主线"},
        {"target": "159819", "probability": 39, "lag_days": 2, "signal": "成长风格内再平衡"},
    ],
}

INTERVIEW_PROFILE: dict[str, str] = {
    "trade_cycle": "隔夜",
    "fund_metric": "组合口径（净流入+资金连续性+换手强度）",
    "startup_focus": "价格突破与资金连续流入并重",
    "rotation_view": "完整轮动网络 + Top5重点",
    "risk_control": "ETF波动率动态阈值",
    "review_metric": "收益归因 + 轮动正确率并重",
    "data_integration_order": "1.ETF行情 2.ETF份额 3.行业指数映射",
}

RECOMMENDED_POOL: list[dict[str, Any]] = [
    {"code": "588000", "name": "科创50ETF", "bucket": "核心进攻", "status": "active"},
    {"code": "512480", "name": "半导体ETF", "bucket": "核心进攻", "status": "active"},
    {"code": "159819", "name": "人工智能ETF", "bucket": "核心进攻", "status": "active"},
    {"code": "159770", "name": "机器人ETF", "bucket": "成长扩散", "status": "active"},
    {"code": "512000", "name": "券商ETF", "bucket": "风险偏好", "status": "active"},
    {"code": "510300", "name": "沪深300ETF", "bucket": "宽基锚", "status": "active"},
    {"code": "510500", "name": "中证500ETF", "bucket": "宽基锚", "status": "active"},
    {"code": "510880", "name": "红利ETF", "bucket": "防御底仓", "status": "active"},
    {"code": "512800", "name": "银行ETF", "bucket": "防御底仓", "status": "active"},
    {"code": "518880", "name": "黄金ETF", "bucket": "避险对冲", "status": "active"},
    {"code": "159992", "name": "创新药ETF", "bucket": "轮动补涨", "status": "active"},
    {"code": "515030", "name": "新能源车ETF", "bucket": "超跌观察", "status": "active"},
    {"code": "515790", "name": "光伏ETF", "bucket": "超跌观察", "status": "active"},
]

LIVE_CACHE_TTL_SEC = 120
_LIVE_CACHE: dict[str, Any] = {"ts": 0.0, "series": None, "meta": None}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _pct_change(now: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (now / prev - 1) * 100


def _normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low), 0.0, 1.0)


def _clone_series(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cloned: list[dict[str, Any]] = []
    for item in series:
        cloned.append(
            {
                "code": item["code"],
                "name": item["name"],
                "theme": item["theme"],
                "prices": list(item["prices"]),
                "flows": list(item["flows"]),
                "turnover": list(item["turnover"]),
                "dates": list(item.get("dates", TRADE_DATES)),
                "is_live": bool(item.get("is_live", False)),
            }
        )
    return cloned


def _to_ts_code(code: str) -> str:
    suffix = "SH" if code.startswith(("5", "6", "9")) else "SZ"
    return f"{code}.{suffix}"


def _build_sample_series_bundle() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    series = _clone_series(
        [{**item, "dates": TRADE_DATES, "is_live": False} for item in ETF_SERIES]
    )
    meta = {
        "data_mode": "sample",
        "data_source": "sample_engine",
        "coverage": 0.0,
        "live_count": 0,
        "fallback_count": len(series),
        "live_codes": [],
        "analysis_dates": list(TRADE_DATES),
        "as_of": TRADE_DATES[-1],
    }
    return series, meta


def _derive_flow_proxy_from_klines(klines: list[dict[str, Any]]) -> list[float]:
    flows: list[float] = []
    for idx, item in enumerate(klines):
        close_now = float(item.get("close", 0) or 0)
        close_prev = float(klines[idx - 1].get("close", close_now) or close_now) if idx > 0 else close_now
        ret = _pct_change(close_now, close_prev)

        amount_now = float(item.get("amount", 0) or 0)
        prev_window = [float(x.get("amount", 0) or 0) for x in klines[max(0, idx - 3) : idx]]
        avg_prev = sum(prev_window) / len(prev_window) if prev_window else amount_now
        amount_ratio = amount_now / avg_prev if avg_prev > 0 else 1.0

        # P1 实时行情阶段用“成交额冲量+涨跌方向”估算资金强弱，P2 再替换为真实份额净申赎
        flow_proxy = (amount_ratio - 1) * 3.2 + ret * 0.38
        flows.append(round(_clamp(flow_proxy, -5.5, 9.5), 2))
    return flows


def _derive_turnover_series_from_klines(klines: list[dict[str, Any]]) -> list[float]:
    turnover_series: list[float] = []
    amount_series = [float(item.get("amount", 0) or 0) for item in klines]
    base_amount = sum(amount_series) / len(amount_series) if amount_series else 1.0
    if base_amount <= 0:
        base_amount = 1.0

    for item in klines:
        turnover_raw = float(item.get("turnover", 0) or 0)
        if turnover_raw > 0:
            turnover_series.append(round(_clamp(turnover_raw, 0.4, 12.0), 2))
            continue
        amount_now = float(item.get("amount", 0) or 0)
        turnover_proxy = (amount_now / base_amount) * 1.8
        turnover_series.append(round(_clamp(turnover_proxy, 0.6, 5.2), 2))
    return turnover_series


def _build_live_series_bundle() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cached = load_cached_bundle(max_age_seconds=LIVE_CACHE_TTL_SEC)
    if cached:
        cached_series, cached_meta, is_fresh = cached
        if cached_series and cached_meta:
            cached_meta = dict(cached_meta)
            cached_meta["note"] = (cached_meta.get("note") or "") + (
                " (cache)" if is_fresh else " (cache-stale)"
            )
            cached_meta["cache_stale"] = not is_fresh
            return cached_series, cached_meta

    client = TushareClient()
    if not client.configured:
        sample_series, sample_meta = _build_sample_series_bundle()
        sample_meta["note"] = "TUSHARE_TOKEN missing, fallback sample"
        return sample_series, sample_meta

    series: list[dict[str, Any]] = []
    live_codes: list[str] = []
    fallback_count = 0
    analysis_dates = list(TRADE_DATES)
    as_of = TRADE_DATES[-1]
    try:
        # 网络不可达时快速失败，避免逐只ETF串行超时导致长时间白屏
        first_code = ETF_SERIES[0]["code"]
        first_ts_code = _to_ts_code(first_code)
        first_probe = client.get_fund_daily(ts_code=first_ts_code, limit=14)
        if len(first_probe) < 6:
            sample_series, sample_meta = _build_sample_series_bundle()
            sample_meta["note"] = "tushare probe failed, fallback sample"
            return sample_series, sample_meta

        for idx, base_item in enumerate(ETF_SERIES):
            code = base_item["code"]
            ts_code = _to_ts_code(code)
            klines = first_probe if idx == 0 else client.get_fund_daily(ts_code=ts_code, limit=14)
            if len(klines) >= 6:
                recent = klines[-6:]
                prices = [float(x.get("close", 0) or 0) for x in recent]
                dates = [str(x.get("date") or "") for x in recent]
                if min(prices) > 0 and all(dates):
                    flows = _derive_flow_proxy_from_klines(recent)
                    turnover = _derive_turnover_series_from_klines(recent)
                    analysis_dates = dates
                    as_of = max(as_of, dates[-1])
                    series.append(
                        {
                            "code": code,
                            "name": base_item["name"],
                            "theme": base_item["theme"],
                            "prices": prices,
                            "flows": flows,
                            "turnover": turnover,
                            "dates": dates,
                            "is_live": True,
                        }
                    )
                    live_codes.append(code)
                else:
                    fallback_count += 1
                    series.append(
                        {
                            "code": base_item["code"],
                            "name": base_item["name"],
                            "theme": base_item["theme"],
                            "prices": list(base_item["prices"]),
                            "flows": list(base_item["flows"]),
                            "turnover": list(base_item["turnover"]),
                            "dates": list(TRADE_DATES),
                            "is_live": False,
                        }
                    )
            else:
                fallback_count += 1
                series.append(
                    {
                        "code": base_item["code"],
                        "name": base_item["name"],
                        "theme": base_item["theme"],
                        "prices": list(base_item["prices"]),
                        "flows": list(base_item["flows"]),
                        "turnover": list(base_item["turnover"]),
                        "dates": list(TRADE_DATES),
                        "is_live": False,
                    }
                )
    except Exception as e:
        sample_series, sample_meta = _build_sample_series_bundle()
        sample_meta["note"] = f"live fetch error, fallback sample: {str(e)}"
        return sample_series, sample_meta
    finally:
        client.close()

    if not live_codes:
        sample_series, sample_meta = _build_sample_series_bundle()
        sample_meta["note"] = "tushare data unavailable, fallback sample"
        return sample_series, sample_meta

    mode = "live" if fallback_count == 0 else "hybrid"
    coverage = round(len(live_codes) / len(ETF_SERIES), 4)
    note = ""
    if fallback_count > 0:
        note = f"tushare partial coverage, {fallback_count} ETFs fallback to sample"
    meta = {
        "data_mode": mode,
        "data_source": "tushare_fund_daily",
        "coverage": coverage,
        "live_count": len(live_codes),
        "fallback_count": fallback_count,
        "live_codes": live_codes,
        "analysis_dates": analysis_dates,
        "as_of": as_of,
        "note": note,
        "cache_stale": False,
    }
    save_cached_bundle(series, meta)
    return series, meta


def _get_series_bundle(mode: str = "auto") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global _LIVE_CACHE
    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode == "sample":
        return _build_sample_series_bundle()

    now = time.time()
    cached_series = _LIVE_CACHE.get("series")
    cached_meta = _LIVE_CACHE.get("meta")
    cached_ts = float(_LIVE_CACHE.get("ts") or 0.0)
    if cached_series and cached_meta and now - cached_ts <= LIVE_CACHE_TTL_SEC:
        return _clone_series(cached_series), dict(cached_meta)

    series, meta = _build_live_series_bundle()
    _LIVE_CACHE = {"ts": now, "series": _clone_series(series), "meta": dict(meta)}

    if normalized_mode == "live" and meta.get("data_mode") == "sample":
        meta["note"] = "live mode requested but switched to sample fallback"
    return _clone_series(series), dict(meta)


def _calc_turn_ratio(turnover: list[float]) -> float:
    if len(turnover) < 4:
        return 1.0
    base = sum(turnover[-4:-1]) / 3
    if base <= 0:
        return 1.0
    return turnover[-1] / base


def _calc_volatility(prices: list[float]) -> float:
    if len(prices) < 3:
        return 0.8
    returns = [_pct_change(prices[i], prices[i - 1]) for i in range(1, len(prices))]
    mean_ret = sum(returns) / len(returns)
    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
    return round(max(sqrt(variance), 0.5), 2)


def _dynamic_thresholds(volatility: float) -> dict[str, float]:
    entry = _clamp(57 + volatility * 6.5, 55, 76)
    watch = _clamp(entry - (11 + volatility * 1.2), 42, 63)
    exit_line = _clamp(watch - (8 + volatility), 30, 55)
    return {"entry": round(entry, 2), "watch": round(watch, 2), "exit": round(exit_line, 2)}


def _calc_capital_composite(flow_1d: float, flow_3d: float, turn_ratio: float) -> float:
    flow_1d_norm = _normalize(flow_1d, -2.5, 8.5)
    flow_3d_norm = _normalize(flow_3d, -6.0, 18.0)
    turn_norm = _normalize(turn_ratio, 0.85, 1.9)
    score = (flow_1d_norm * 0.45 + flow_3d_norm * 0.35 + turn_norm * 0.20) * 100
    return round(score, 2)


def _classify_stage(
    change_5d: float, flow_3d: float, turn_ratio: float, breakout: bool, volatility: float
) -> tuple[str, str]:
    accel_change = max(5.5, volatility * 4.2)
    accel_flow = max(10.0, volatility * 7.5)
    accel_turn = 1.18 + min(0.18, volatility * 0.08)

    start_change = max(2.2, volatility * 2.0)
    start_flow = max(5.2, volatility * 4.8)
    start_turn = 1.05 + min(0.16, volatility * 0.06)

    retreat_change = -max(1.2, volatility * 1.6)
    retreat_flow = -max(0.8, volatility * 1.1)

    if change_5d >= accel_change and flow_3d >= accel_flow and turn_ratio >= accel_turn:
        return "加速", "突破后资金持续放大，隔夜延续概率较高"
    if change_5d >= start_change and flow_3d >= start_flow and turn_ratio >= start_turn and breakout:
        return "启动", "价格突破与资金连续流入共振，符合启动定义"
    if change_5d <= retreat_change or flow_3d <= retreat_flow:
        return "退潮", "收益与资金同向走弱，隔夜胜率下降"
    if abs(change_5d) <= (1.6 + volatility * 0.4) and flow_3d > 0:
        return "分歧", "价格震荡但资金仍在试探，需等待次日确认"
    return "蓄势", "量价尚未形成一致性，继续观察"


def _calc_start_score(
    change_5d: float, flow_3d: float, turn_ratio: float, breakout: bool, volatility: float
) -> tuple[float, dict[str, float]]:
    momentum_high = max(8.0, volatility * 6.0)
    flow_high = max(12.0, volatility * 9.0)
    momentum_low = -max(4.0, volatility * 3.2)
    flow_low = -max(5.0, volatility * 4.0)

    momentum_score = _normalize(change_5d, momentum_low, momentum_high) * 34
    flow_score = _normalize(flow_3d, flow_low, flow_high) * 34
    turn_score = _normalize(turn_ratio, 0.85, 1.9) * 18
    breakout_score = 14 if breakout else 0

    total = round(_clamp(momentum_score + flow_score + turn_score + breakout_score, 0, 100), 2)
    breakdown = {
        "momentum": round(momentum_score, 2),
        "flow": round(flow_score, 2),
        "turnover": round(turn_score, 2),
        "breakout": round(float(breakout_score), 2),
    }
    return total, breakdown


def _calc_heat_score(prices: list[float], flows: list[float], turnover: list[float], idx: int) -> float:
    ref_idx = max(0, idx - 3)
    momentum = _pct_change(prices[idx], prices[ref_idx])
    flow_impulse = sum(flows[max(0, idx - 2) : idx + 1])
    prev_turn = turnover[max(0, idx - 3) : idx] or [turnover[idx]]
    turn_ratio = turnover[idx] / (sum(prev_turn) / len(prev_turn))
    score = 50 + momentum * 3.3 + flow_impulse * 1.9 + (turn_ratio - 1) * 15
    return round(_clamp(score, 5, 98), 2)


def _build_etf_metrics(series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for item in series:
        prices = item["prices"]
        flows = item["flows"]
        turnover = item["turnover"]

        change_1d = _pct_change(prices[-1], prices[-2])
        change_5d = _pct_change(prices[-1], prices[0])
        flow_1d = flows[-1]
        flow_3d = sum(flows[-3:])
        flow_5d = sum(flows[-5:])
        turn_ratio = _calc_turn_ratio(turnover)
        volatility = _calc_volatility(prices)
        breakout = prices[-1] >= max(prices[-5:-1])
        capital_score = _calc_capital_composite(flow_1d, flow_3d, turn_ratio)
        thresholds = _dynamic_thresholds(volatility)
        start_score, score_breakdown = _calc_start_score(change_5d, flow_3d, turn_ratio, breakout, volatility)
        stage, reason = _classify_stage(change_5d, flow_3d, turn_ratio, breakout, volatility)
        signal_state = (
            "执行"
            if start_score >= thresholds["entry"]
            else ("观察" if start_score >= thresholds["watch"] else "回避")
        )

        metrics.append(
            {
                "code": item["code"],
                "name": item["name"],
                "theme": item["theme"],
                "last_price": prices[-1],
                "change_1d": round(change_1d, 2),
                "change_5d": round(change_5d, 2),
                "flow_1d": round(flow_1d, 2),
                "flow_3d": round(flow_3d, 2),
                "flow_5d": round(flow_5d, 2),
                "turn_ratio": round(turn_ratio, 2),
                "volatility": volatility,
                "breakout": breakout,
                "capital_score": capital_score,
                "start_score": start_score,
                "score_breakdown": score_breakdown,
                "stage": stage,
                "stage_reason": reason,
                "risk_thresholds": thresholds,
                "signal_state": signal_state,
                "data_flag": "live" if item.get("is_live") else "sample",
                "heat_scores": [
                    _calc_heat_score(prices, flows, turnover, idx) for idx in range(len(prices))
                ],
            }
        )
    return metrics


def _build_links(metrics_by_code: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for source_code, rules in ROTATION_RULES.items():
        source_metric = metrics_by_code.get(source_code)
        if not source_metric:
            continue
        for rule in rules:
            target_code = rule["target"]
            target_metric = metrics_by_code.get(target_code)
            if not target_metric:
                continue

            lag_penalty = max(0.58, 1 - 0.18 * max(0, rule["lag_days"] - 1))
            intensity = (
                (
                    rule["probability"] / 17
                    + target_metric["capital_score"] / 24
                    + max(0.0, -source_metric["flow_3d"]) / 4.5
                )
                * lag_penalty
            )
            links.append(
                {
                    "source_code": source_code,
                    "source_name": source_metric["name"],
                    "target_code": target_code,
                    "target_name": target_metric["name"],
                    "value": round(intensity, 2),
                    "probability": rule["probability"],
                    "lag_days": rule["lag_days"],
                    "signal": rule["signal"],
                    "overnight_priority": rule["lag_days"] <= 1,
                }
            )
    return links


def _build_rotation_evaluation(
    metrics_by_code: dict[str, dict[str, Any]], links: list[dict[str, Any]]
) -> dict[str, float]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        grouped.setdefault(link["source_code"], []).append(link)

    hit_count = 0
    total_count = 0
    weighted_ret_5d = 0.0
    weight_sum = 0.0

    for source_links in grouped.values():
        source_links = sorted(source_links, key=lambda x: x["probability"], reverse=True)
        top_link = source_links[0]
        target_metric = metrics_by_code.get(top_link["target_code"])
        if not target_metric:
            continue

        total_count += 1
        if target_metric["change_1d"] > 0 and target_metric["flow_1d"] > 0:
            hit_count += 1

        for item in source_links[:5]:
            tgt = metrics_by_code.get(item["target_code"])
            if not tgt:
                continue
            weight = item["probability"] / 100
            weighted_ret_5d += tgt["change_5d"] * weight
            weight_sum += weight

    rotation_accuracy = round((hit_count / total_count * 100), 2) if total_count else 0.0
    attribution_return_5d = round(weighted_ret_5d / weight_sum, 2) if weight_sum else 0.0
    attribution_return_1d = round(attribution_return_5d / 5, 2)
    return {
        "rotation_accuracy": rotation_accuracy,
        "attribution_return_1d": attribution_return_1d,
        "attribution_return_5d": attribution_return_5d,
    }


def get_interview_questions() -> list[dict[str, str]]:
    return [
        {
            "id": "Q1",
            "question": "你的主交易节奏是日内、隔日还是3-10日波段？",
            "why_it_matters": "决定轮动模型的滞后参数（lag_days）与信号刷新频率。",
            "default_assumption": "已采用：隔夜节奏（优先滞后1天链路）。",
        },
        {
            "id": "Q2",
            "question": "首批ETF池是否限定在10-20只核心宽基/行业ETF？",
            "why_it_matters": "池子越大噪声越高，先做核心池能提升轮动路径稳定性。",
            "default_assumption": "推荐13只核心池：进攻+防守+宽基锚+补涨观察。",
        },
        {
            "id": "Q3",
            "question": "资金口径优先用成交额、份额变化，还是净申购估算？",
            "why_it_matters": "不同口径对“资金迁移”的解释不同，会影响链路权重。",
            "default_assumption": "已采用：组合口径（净流入+连续性+换手强度）。",
        },
        {
            "id": "Q4",
            "question": "启动阶段你更看重价格突破，还是资金连续流入？",
            "why_it_matters": "决定启动分数里量价权重。",
            "default_assumption": "已采用：价格与资金并重（34%/34%）。",
        },
        {
            "id": "Q5",
            "question": "你希望“推演”输出为Top3方向，还是给完整迁移网络？",
            "why_it_matters": "关系到页面复杂度和交易执行效率。",
            "default_assumption": "已采用：完整迁移网络 + Top5重点。",
        },
        {
            "id": "Q6",
            "question": "风险控制希望设置成统一阈值还是分ETF动态阈值？",
            "why_it_matters": "影响信号触发后是否进入观察/执行状态。",
            "default_assumption": "已采用：按ETF波动率动态阈值。",
        },
        {
            "id": "Q7",
            "question": "复盘结果你更关心收益归因还是轮动正确率？",
            "why_it_matters": "决定模块最终评估指标体系。",
            "default_assumption": "已采用：二者并重，同时输出。",
        },
        {
            "id": "Q8",
            "question": "真实数据接入优先顺序如何排？",
            "why_it_matters": "决定迭代里程碑和工程排期。",
            "default_assumption": "已采用：ETF行情 → ETF份额 → 行业指数映射。",
        },
    ]


def get_interview_profile() -> dict[str, Any]:
    active_codes = {item["code"] for item in ETF_SERIES}
    recommended_pool = []
    for item in RECOMMENDED_POOL:
        enriched = dict(item)
        enriched["available_in_demo"] = item["code"] in active_codes
        recommended_pool.append(enriched)
    return {
        "profile": dict(INTERVIEW_PROFILE),
        "recommended_pool": recommended_pool,
    }


def build_rotation_dashboard(source_code: str | None = None, mode: str = "auto") -> dict[str, Any]:
    series, data_meta = _get_series_bundle(mode=mode)
    metrics = _build_etf_metrics(series)
    metrics = sorted(metrics, key=lambda x: x["start_score"], reverse=True)
    metrics_by_code = {m["code"]: m for m in metrics}
    links = _build_links(metrics_by_code)

    selected_source_code = source_code if source_code in metrics_by_code else metrics[0]["code"]
    selected_source = metrics_by_code[selected_source_code]

    trajectory = [
        {
            **link,
            "target_stage": metrics_by_code[link["target_code"]]["stage"],
            "target_score": metrics_by_code[link["target_code"]]["start_score"],
            "target_signal_state": metrics_by_code[link["target_code"]]["signal_state"],
        }
        for link in links
        if link["source_code"] == selected_source_code
    ]
    trajectory = sorted(trajectory, key=lambda x: x["probability"], reverse=True)[:5]

    stages = Counter(item["stage"] for item in metrics)
    startup_count = stages.get("启动", 0) + stages.get("加速", 0)
    risk_on = [m for m in metrics if m["theme"] in {"科技成长", "硬科技", "AI算力", "智能制造"}]
    risk_on_positive = [m for m in risk_on if m["flow_1d"] > 0]
    risk_on_ratio = round((len(risk_on_positive) / len(risk_on) * 100), 1) if risk_on else 0.0
    evaluation = _build_rotation_evaluation(metrics_by_code, links)

    heatmap_items = [
        {"code": m["code"], "name": m["name"], "stage": m["stage"], "scores": m["heat_scores"]}
        for m in metrics
    ]

    analysis_dates = data_meta.get("analysis_dates") or TRADE_DATES
    timeline: list[dict[str, Any]] = []
    for date_idx, trade_date in enumerate(analysis_dates):
        flows = []
        for item in series:
            series_flows = item["flows"]
            flow_idx = min(date_idx, len(series_flows) - 1)
            flows.append(
                {
                    "code": item["code"],
                    "name": item["name"],
                    "flow": round(series_flows[flow_idx], 2),
                }
            )
        flows_sorted = sorted(flows, key=lambda x: x["flow"], reverse=True)
        timeline.append(
            {
                "date": trade_date,
                "top_inflow": flows_sorted[:3],
                "top_outflow": list(reversed(flows_sorted[-3:])),
            }
        )

    available_codes = {item["code"] for item in series}
    live_codes = set(data_meta.get("live_codes", []))
    profile_bundle = get_interview_profile()
    recommended_pool = []
    for item in profile_bundle["recommended_pool"]:
        enriched = dict(item)
        enriched["available_in_demo"] = item["code"] in available_codes
        enriched["live_data_ready"] = item["code"] in live_codes
        recommended_pool.append(enriched)

    return {
        "as_of": data_meta.get("as_of", TRADE_DATES[-1]),
        "data_mode": data_meta.get("data_mode", "sample"),
        "data_source": data_meta.get("data_source", "sample_engine"),
        "data_coverage": data_meta.get("coverage", 0.0),
        "data_note": data_meta.get("note", ""),
        "source_code": selected_source_code,
        "source_name": selected_source["name"],
        "summary": {
            "etf_count": len(metrics),
            "net_flow_1d": round(sum(m["flow_1d"] for m in metrics), 2),
            "net_flow_5d": round(sum(m["flow_5d"] for m in metrics), 2),
            "startup_count": startup_count,
            "risk_on_ratio": risk_on_ratio,
        },
        "evaluation": evaluation,
        "execution_style": {
            "trade_cycle": "隔夜",
            "rotation_view": "完整网络 + Top5",
            "risk_mode": "波动率动态阈值",
        },
        "interview_profile": profile_bundle["profile"],
        "recommended_pool": recommended_pool,
        "stage_distribution": dict(stages),
        "etfs": metrics,
        "links": links,
        "trajectory": trajectory,
        "heatmap": {
            "dates": analysis_dates,
            "items": heatmap_items,
        },
        "timeline": timeline,
        "integration_plan": [
            "P1: 接入ETF行情（日线+分钟）构建实时轮动监控",
            "P2: 接入ETF份额变化（申赎）强化资金迁移识别",
            "P3: 建立ETF-行业指数映射，补充板块传导解释",
        ],
        "assumptions": [
            "资金口径使用组合信号：净流入+连续性+换手强度",
            "启动评分采用价格与资金并重，适配隔夜节奏",
            "风险阈值按ETF波动率动态调整，避免统一阈值失真",
        ],
    }


def _map_rotation_signal(
    metric: dict[str, Any],
) -> tuple[str, int, dict[str, float], str]:
    start_score = metric["start_score"]
    thresholds = metric["risk_thresholds"]
    change_5d = metric["change_5d"]
    flow_3d = metric["flow_3d"]
    capital_score = metric["capital_score"]
    volatility = metric["volatility"]
    breakout = metric["breakout"]
    stage = metric["stage"]

    momentum_factor = _normalize(change_5d, -4.0, 8.0)
    trend_factor = _normalize(start_score, 0, 100)
    vol_factor = 1.0 - _normalize(volatility, 0.5, 5.0)

    composite = momentum_factor * 0.40 + trend_factor * 0.35 + vol_factor * 0.25
    confidence = round(_clamp(composite * 100, 5, 95))

    factors = {
        "momentum": round(momentum_factor * 100, 1),
        "trend": round(trend_factor * 100, 1),
        "volatility_safety": round(vol_factor * 100, 1),
    }

    if start_score >= thresholds["entry"] and flow_3d > 0 and (breakout or stage in ("启动", "加速")):
        signal = "加仓"
        reasoning = f"启动分{start_score:.0f}突破进场线{thresholds['entry']:.0f}，资金3日净流入{flow_3d:.1f}亿，{stage}阶段适合加仓"
    elif start_score < thresholds["exit"] or (change_5d < -2.0 and flow_3d < -1.0):
        signal = "减仓"
        reasoning = f"启动分{start_score:.0f}低于退出线{thresholds['exit']:.0f}，5日涨幅{change_5d:.1f}%，资金净流出，建议减仓"
    else:
        signal = "持有"
        reasoning = f"启动分{start_score:.0f}处于观察区间[{thresholds['exit']:.0f}-{thresholds['entry']:.0f}]，维持现有仓位"

    return signal, confidence, factors, reasoning


def build_rotation_signals(mode: str = "auto") -> dict[str, Any]:
    series, data_meta = _get_series_bundle(mode=mode)
    metrics = _build_etf_metrics(series)
    metrics_by_code = {m["code"]: m for m in metrics}

    signals: list[dict[str, Any]] = []
    for m in metrics:
        signal, confidence, factors, reasoning = _map_rotation_signal(m)
        signals.append({
            "code": m["code"],
            "name": m["name"],
            "theme": m["theme"],
            "signal": signal,
            "confidence": confidence,
            "factors": factors,
            "reasoning": reasoning,
            "data_flag": m["data_flag"],
        })

    signals.sort(key=lambda s: s["confidence"], reverse=True)

    return {
        "as_of": data_meta.get("as_of", TRADE_DATES[-1]),
        "data_mode": data_meta.get("data_mode", "sample"),
        "data_source": data_meta.get("data_source", "sample_engine"),
        "etf_count": len(signals),
        "signals": signals,
    }
