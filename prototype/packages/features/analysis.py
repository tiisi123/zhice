from __future__ import annotations


BROKEN_REASONS = {
    "抛压": "大量获利盘集中抛出，买盘承接不住",
    "撤单": "主力主动撤回封单，导致封板打开",
    "大盘": "大盘急跌拖累，市场恐慌情绪蔓延",
    "跟风不足": "板块内跟风股弱势，龙头独木难支",
    "消息利空": "个股或板块出现利空消息冲击",
    "尾盘": "尾盘资金分歧加大，封单被砸开",
}


def classify_broken_reason(reason: str) -> str:
    if not reason:
        return "其他"
    for key in BROKEN_REASONS:
        if key in reason:
            return key
    return "其他"


def build_broken_case(stock: dict) -> dict:
    reason_type = classify_broken_reason(stock.get("combined_reason", ""))
    return {
        "stock_code": stock.get("stock_code", ""),
        "stock_name": stock.get("stock_name", ""),
        "broken_time": stock.get("time"),
        "reason_raw": stock.get("combined_reason", ""),
        "reason_type": reason_type,
        "reason_explain": BROKEN_REASONS.get(reason_type, ""),
        "board_count": stock.get("board_count", 0),
        "change_rate": stock.get("change_rate", 0),
        "plate": stock.get("first_plate_name", ""),
    }


def detect_new_theme(current_themes: list[str], history_themes: set[str]) -> list[str]:
    return [t for t in current_themes if t not in history_themes]


def recommend_strategy(sentiment: str, max_board: int) -> list[str]:
    """旧版字符串列表，保留向后兼容。"""
    recs = []
    if sentiment in ("高潮", "回暖") and max_board >= 4:
        recs.append("连板龙头低吸")
        recs.append("涨停次日高开")
    if sentiment in ("回暖", "中性"):
        recs.append("题材轮动跟随")
    if sentiment in ("低迷", "冰点"):
        recs.append("观望为主，等待情绪修复")
    return recs or ["观望为主"]


# ===== PRD M4A-08：次日开盘策略 · 三场景结构化输出 =====
# 场景：溢价（高开冲高）/ 低吸（回踩接力）/ 排板（一字板/T 字板挂单）

def _pick_top_themes(sectors: list[dict], n: int = 3) -> list[str]:
    """从 sectors 中提取 Top N 主线题材名（兼容多种字段名）。"""
    out: list[str] = []
    for s in sectors[:n]:
        name = s.get("PlateName") or s.get("concept_name") or s.get("name") or s.get("col2", "")
        if name:
            out.append(name)
    return out


def _flatten_ladder(ladder: dict | None) -> list[dict]:
    """把 ladder.tiers 拉平成股票列表，标注 board_count。"""
    if not ladder:
        return []
    tiers = ladder.get("tiers") or {}
    out: list[dict] = []
    for tier_key, stocks in tiers.items():
        try:
            n = int(str(tier_key).strip())
        except Exception:
            n = 1
        for s in stocks or []:
            item = dict(s)
            item.setdefault("board_count", n)
            out.append(item)
    return out


def build_next_day_strategy(
    summary: dict | None,
    ladder: dict | None,
    sectors: list[dict] | None,
) -> dict:
    """
    生成次日开盘策略的三场景结构化建议。
    
    返回：
    {
      "sentiment": "...",
      "max_board": int,
      "scenarios": {
        "premium": { "name": "溢价场景", "logic": "...", "stocks": [...], "watch_signal": "...", "risk": "...", "confidence": 0-100 },
        "dip": { "name": "低吸场景", ... },
        "ladder": { "name": "排板场景", ... }
      },
      "overall_advice": "...",
      "disclaimer": "..."
    }
    """
    summary = summary or {}
    sectors = sectors or []
    sentiment = summary.get("sentiment_level", "中性")
    max_board = summary.get("max_board", 0)
    limit_up_count = summary.get("limit_up_count", 0)
    broken_rate = summary.get("broken_rate", 0)
    seal_success_rate = summary.get("seal_success_rate", 0)

    top_themes = _pick_top_themes(sectors, 3)
    all_stocks = _flatten_ladder(ladder)

    # ---- 1. 溢价场景候选：高板龙头 + 板块强度高 ----
    premium_pool = [
        s for s in all_stocks
        if (s.get("board_count", 0) >= 3) and s.get("is_leader")
    ]
    if not premium_pool:
        premium_pool = [s for s in all_stocks if s.get("board_count", 0) >= 3][:5]
    premium_stocks = [{
        "code": s.get("stock_code", ""),
        "name": s.get("stock_name", ""),
        "board_count": s.get("board_count", 1),
        "theme": s.get("first_plate_name", ""),
        "reason": "高板龙头次日高开冲高",
    } for s in premium_pool[:5]]

    if sentiment == "高潮" and max_board >= 5:
        premium_logic = f"情绪【{sentiment}】+ 最高板 {max_board}，龙头次日高开溢价空间打开。"
        premium_conf = 75
    elif sentiment == "回暖" and max_board >= 4:
        premium_logic = f"情绪【{sentiment}】回暖中，龙头有望延续，但需警惕分歧。"
        premium_conf = 60
    else:
        premium_logic = f"情绪【{sentiment}】，溢价空间有限，仅龙头中的龙头可博弈。"
        premium_conf = 35

    # ---- 2. 低吸场景候选：主线 1-2 板 + 强势接力位 ----
    dip_pool = [
        s for s in all_stocks
        if 1 <= s.get("board_count", 0) <= 2 and (s.get("first_plate_name", "") in top_themes)
    ]
    dip_stocks = [{
        "code": s.get("stock_code", ""),
        "name": s.get("stock_name", ""),
        "board_count": s.get("board_count", 1),
        "theme": s.get("first_plate_name", ""),
        "reason": f"主线【{s.get('first_plate_name','')}】低位接力候选",
    } for s in dip_pool[:8]]

    if sentiment in ("回暖", "高潮") and len(top_themes) >= 2:
        dip_logic = f"主线 {' / '.join(top_themes[:2])} 强势，1-2 板成员次日回踩低吸性价比高。"
        dip_conf = 65
    elif sentiment in ("中性",):
        dip_logic = "情绪中性，选择强势主线低位股低吸，止损位需严格执行。"
        dip_conf = 50
    else:
        dip_logic = "情绪偏弱，低吸需更谨慎，仅在强势板块内寻找机会。"
        dip_conf = 30

    # ---- 3. 排板场景候选：题材热度高 + 板块新晋启动 ----
    # 排板适合一字板/T 字板的潜在标的：板块强但今日尚未涨停的强势股
    ladder_pool = [
        s for s in all_stocks
        if s.get("board_count", 0) == 1 and (s.get("first_plate_name", "") in top_themes)
    ]
    ladder_stocks = [{
        "code": s.get("stock_code", ""),
        "name": s.get("stock_name", ""),
        "board_count": s.get("board_count", 1),
        "theme": s.get("first_plate_name", ""),
        "reason": f"主线【{s.get('first_plate_name','')}】首板，次日有连板预期",
    } for s in ladder_pool[:6]]

    if seal_success_rate >= 70 and limit_up_count >= 30:
        ladder_logic = f"封板率 {seal_success_rate:.0f}%，市场承接力强，可挂单排板首板龙头。"
        ladder_conf = 70
    elif seal_success_rate >= 50:
        ladder_logic = f"封板率 {seal_success_rate:.0f}%，排板需精挑细选，仅最强主线可博。"
        ladder_conf = 50
    else:
        ladder_logic = f"封板率仅 {seal_success_rate:.0f}%，炸板率 {broken_rate:.0f}%，不建议盲目排板。"
        ladder_conf = 25

    # ---- 整体建议 ----
    if sentiment == "高潮":
        overall = "情绪高潮，三场景同步启用；优先溢价 → 低吸 → 排板。"
    elif sentiment == "回暖":
        overall = "情绪回暖，重点低吸 + 选择性排板；溢价仓位控制。"
    elif sentiment == "中性":
        overall = "情绪中性，半仓低吸为主；溢价/排板观望。"
    else:
        overall = "情绪偏冷，建议空仓观望，等待情绪修复信号。"

    return {
        "sentiment": sentiment,
        "max_board": max_board,
        "limit_up_count": limit_up_count,
        "top_themes": top_themes,
        "scenarios": {
            "premium": {
                "name": "溢价场景",
                "icon": "🚀",
                "logic": premium_logic,
                "stocks": premium_stocks,
                "watch_signal": "9:25 集合竞价高开 ≥3% 且封单 >5000 万，可参与；分歧砸盘则放弃。",
                "risk": "高位龙头炸板风险大，止损 -5% 严格执行。",
                "confidence": premium_conf,
            },
            "dip": {
                "name": "低吸场景",
                "icon": "🎯",
                "logic": dip_logic,
                "stocks": dip_stocks,
                "watch_signal": "开盘回踩 5/10 日均线企稳，量能温和放大可介入。",
                "risk": "破位 5 日线立即止损，避免滚动套牢。",
                "confidence": dip_conf,
            },
            "ladder": {
                "name": "排板场景",
                "icon": "🪜",
                "logic": ladder_logic,
                "stocks": ladder_stocks,
                "watch_signal": "9:15 集合竞价直接挂涨停板价，关注封单金额与撤单情况。",
                "risk": "若 9:30 后未封板，立即撤单避免被套。",
                "confidence": ladder_conf,
            },
        },
        "overall_advice": overall,
        "disclaimer": "以上策略基于历史数据与情绪推演，仅供参考，不构成投资建议。",
    }
