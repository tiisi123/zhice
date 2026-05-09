import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import ai


def test_resolve_chat_trade_date_yesterday_uses_previous_weekday():
    trade_date, reason = ai._resolve_chat_trade_date(
        "你昨日呢？",
        [],
        "2026-05-08",
    )

    assert trade_date == "2026-05-07"
    assert reason == "relative_yesterday"


def test_resolve_chat_trade_date_explicit_date_wins():
    trade_date, reason = ai._resolve_chat_trade_date(
        "复盘 2026-05-07 的主线",
        [],
        "2026-05-08",
    )

    assert trade_date == "2026-05-07"
    assert reason == "explicit_date"


def test_headline_is_deterministic_from_summary_numbers():
    summary = {
        "sentiment_level": "回暖",
        "limit_up_count": 58,
        "broken_count": 12,
        "max_board": 4,
    }
    text = ai._build_deterministic_headline(
        summary,
        [{"PlateName": "ST摘帽"}],
        [{"stock_name": "中国软件", "first_plate_name": "IT服务Ⅱ", "related_plates": []}],
    )

    assert "涨停58家" in text
    assert "炸板12家" in text
    assert "最高4板" in text
    assert "均为0" not in text
