from __future__ import annotations


def calc_theme_hot(limit_up_count: int, volume: float = 0, news_count: int = 0) -> float:
    return limit_up_count * 10 + (volume / 1e8) * 2 + news_count * 3


def classify_board_tier(stocks: list[dict]) -> dict[str, list[dict]]:
    tiers: dict[str, list[dict]] = {}
    for s in stocks:
        bc = s.get("board_count", 0) or 0
        if bc <= 0:
            bc = 1
        key = f"{bc}板"
        if bc >= 5:
            key = "5板+"
        tiers.setdefault(key, []).append(s)
    return tiers


def identify_leader(stocks: list[dict]) -> list[dict]:
    if not stocks:
        return []
    sorted_stocks = sorted(
        stocks,
        key=lambda s: (s.get("board_count", 0) or 0, s.get("seal_amount", 0) or 0),
        reverse=True,
    )
    for i, s in enumerate(sorted_stocks):
        s["leader_rank"] = i + 1
        s["is_leader"] = i == 0
    return sorted_stocks
