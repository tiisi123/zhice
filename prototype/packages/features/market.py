from __future__ import annotations

from packages.normalizers.enums import SentimentLevel


def calc_sentiment_level(
    limit_up: int, limit_down: int, broken: int, broken_rate: float
) -> SentimentLevel:
    if broken_rate > 50 or limit_up < 10:
        return SentimentLevel.FREEZING
    if broken_rate > 35 or limit_up < 30:
        return SentimentLevel.LOW
    if limit_up > 80 and broken_rate < 15:
        return SentimentLevel.HOT
    if limit_up > 50 and broken_rate < 25:
        return SentimentLevel.WARM
    return SentimentLevel.NEUTRAL


def calc_broken_rate(limit_up: int, broken: int) -> float:
    if limit_up + broken == 0:
        return 0.0
    return round(broken / (limit_up + broken) * 100, 2)


def build_market_summary(
    kpl_stats: list[dict], xgt_limit_up: list[dict], xgt_broken: list[dict]
) -> dict:
    limit_up_count = len(xgt_limit_up)
    broken_count = len(xgt_broken)
    broken_rate = calc_broken_rate(limit_up_count, broken_count)

    kpl = kpl_stats[0] if kpl_stats else {}

    max_board = 0
    for s in xgt_limit_up:
        bc = s.get("board_count", 0) or 0
        if bc > max_board:
            max_board = bc

    sentiment = calc_sentiment_level(limit_up_count, 0, broken_count, broken_rate)

    seal_success_rate = (
        round(limit_up_count / (limit_up_count + broken_count) * 100, 2)
        if (limit_up_count + broken_count) > 0
        else 0.0
    )

    return {
        "limit_up_count": limit_up_count,
        "broken_count": broken_count,
        "broken_rate": broken_rate,
        "seal_success_rate": seal_success_rate,
        "max_board": max_board,
        "sentiment_level": sentiment.value,
        "sentiment_score": kpl.get("market_strong", 0),
        "up_count": kpl.get("market_znum", 0),
        "down_count": kpl.get("market_dnum", 0),
        "limit_down_count": kpl.get("market_dtnum", 0),
        "total_volume": kpl.get("market_amount", 0),
    }
