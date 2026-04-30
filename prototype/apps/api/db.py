"""轻量级 SQLite 持久化层：用户、订单、VIP、埋点、问卷、看板。
使用标准库 sqlite3，避免引入额外依赖。
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

_DB_PATH = Path(os.environ.get("ZHICE_DB_PATH", Path(__file__).resolve().parents[2] / "data" / "zhice.db"))
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        nickname TEXT DEFAULT '',
        password_hash TEXT NOT NULL,
        vip_level TEXT DEFAULT 'free',
        vip_expire_at TEXT DEFAULT NULL,
        style TEXT DEFAULT 'short',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_quota (
        user_id INTEGER NOT NULL,
        quota_date TEXT NOT NULL,
        feature TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, quota_date, feature)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        plan TEXT NOT NULL,
        amount INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        pay_method TEXT DEFAULT 'wechat',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        paid_at TEXT DEFAULT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event TEXT NOT NULL,
        page TEXT,
        props TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS style_profile (
        user_id INTEGER PRIMARY KEY,
        answers TEXT NOT NULL,
        style TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dashboards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        layout TEXT NOT NULL,
        is_default INTEGER DEFAULT 0,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS theme_history (
        theme_name TEXT PRIMARY KEY,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        appearance_days INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports_archive (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author_id INTEGER DEFAULT 1,
        author_name TEXT DEFAULT '智策官方',
        trade_date TEXT NOT NULL,
        kind TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        summary TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS report_subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        author_id INTEGER NOT NULL,
        author_name TEXT DEFAULT '',
        enabled INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, author_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alert_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        kind TEXT DEFAULT 'limit_up',
        rules TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        side TEXT NOT NULL,
        price REAL NOT NULL,
        qty INTEGER NOT NULL,
        note TEXT DEFAULT '',
        trade_date TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS style_combo (
        user_id INTEGER PRIMARY KEY,
        styles TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # PRD US-004：异动命中持久化（调度器写入，前端拉历史 N 条）
    """
    CREATE TABLE IF NOT EXISTS watch_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT DEFAULT '',
        kind TEXT NOT NULL,
        message TEXT NOT NULL,
        change_rate REAL DEFAULT 0,
        trade_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, code, kind, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invite_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        plan TEXT NOT NULL DEFAULT 'standard',
        days INTEGER NOT NULL DEFAULT 30,
        max_uses INTEGER DEFAULT 1,
        used_count INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT DEFAULT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invite_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(code, user_id)
    )
    """,
    # PRD RE-004 / US-004：研究池 + 价格异动阈值
    """
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT DEFAULT '',
        group_name TEXT DEFAULT '默认',
        note TEXT DEFAULT '',
        -- 价格异动阈值（百分比，正为涨幅触发，负为跌幅触发；NULL 表不监控）
        alert_change_up REAL DEFAULT NULL,
        alert_change_down REAL DEFAULT NULL,
        -- 触发任意涨跌停时提醒
        alert_limit_up INTEGER DEFAULT 1,
        alert_broken INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, code)
    )
    """,
    # ==================== 短线数据沉淀表 ====================
    """
    CREATE TABLE IF NOT EXISTS daily_market_snapshot (
        trade_date TEXT PRIMARY KEY,
        limit_up_count INTEGER DEFAULT 0,
        broken_count INTEGER DEFAULT 0,
        broken_rate REAL DEFAULT 0,
        seal_success_rate REAL DEFAULT 0,
        max_board INTEGER DEFAULT 0,
        sentiment_level TEXT DEFAULT '',
        sentiment_score INTEGER DEFAULT 0,
        up_count INTEGER DEFAULT 0,
        down_count INTEGER DEFAULT 0,
        limit_down_count INTEGER DEFAULT 0,
        total_volume REAL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS limit_up_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT DEFAULT '',
        board_count INTEGER DEFAULT 1,
        limit_time TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        first_plate TEXT DEFAULT '',
        seal_amount REAL DEFAULT 0,
        change_rate REAL DEFAULT 0,
        UNIQUE(trade_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS broken_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT DEFAULT '',
        board_count INTEGER DEFAULT 1,
        broken_time TEXT DEFAULT '',
        reason_type TEXT DEFAULT '',
        reason_raw TEXT DEFAULT '',
        change_rate REAL DEFAULT 0,
        UNIQUE(trade_date, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS board_ladder_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        tier INTEGER NOT NULL,
        stock_codes TEXT NOT NULL DEFAULT '[]',
        count INTEGER DEFAULT 0,
        leader_code TEXT DEFAULT '',
        leader_name TEXT DEFAULT '',
        UNIQUE(trade_date, tier)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS theme_daily_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        theme_name TEXT NOT NULL,
        limit_up_count INTEGER DEFAULT 0,
        change_percent REAL DEFAULT 0,
        intensity REAL DEFAULT 0,
        phase TEXT DEFAULT '',
        score INTEGER DEFAULT 0,
        rank_pos INTEGER DEFAULT 0,
        UNIQUE(trade_date, theme_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dragon_tier_snapshot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        theme_name TEXT NOT NULL,
        role TEXT NOT NULL,
        stock_code TEXT NOT NULL,
        stock_name TEXT DEFAULT '',
        board_count INTEGER DEFAULT 0,
        change_rate REAL DEFAULT 0,
        UNIQUE(trade_date, theme_name, stock_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS next_day_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT NOT NULL,
        category TEXT NOT NULL,
        stock_code TEXT DEFAULT '',
        stock_name TEXT DEFAULT '',
        reason TEXT DEFAULT '',
        trigger_condition TEXT DEFAULT '',
        invalidate_condition TEXT DEFAULT '',
        theme TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(trade_date, category, stock_code)
    )
    """,
    # ==================== 成长价值数据沉淀表 ====================
    """
    CREATE TABLE IF NOT EXISTS industry_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sw_level INTEGER DEFAULT 1,
        sw_code TEXT NOT NULL,
        sw_name TEXT NOT NULL,
        concept_tags TEXT DEFAULT '[]',
        etf_codes TEXT DEFAULT '[]',
        UNIQUE(sw_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etf_code TEXT NOT NULL,
        etf_name TEXT NOT NULL,
        track_index TEXT DEFAULT '',
        industry TEXT DEFAULT '',
        style TEXT DEFAULT '',
        UNIQUE(etf_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS similar_day_case (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_date TEXT NOT NULL,
        similar_date TEXT NOT NULL,
        distance REAL DEFAULT 0,
        snapshot TEXT DEFAULT '{}',
        forward_days INTEGER DEFAULT 5,
        forward_data TEXT DEFAULT '{}',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(target_date, similar_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS investment_memo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        memo_type TEXT NOT NULL DEFAULT 'growth',
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        target_codes TEXT DEFAULT '[]',
        action TEXT DEFAULT 'observe',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
]


_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_watch_alerts_user ON watch_alerts(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_watch_alerts_date ON watch_alerts(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_dashboards_user ON dashboards(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_alert_rules_user ON alert_rules(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_paper_trades_user ON paper_trades(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_reports_archive_date ON reports_archive(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_reports_archive_author ON reports_archive(author_id)",
    "CREATE INDEX IF NOT EXISTS idx_report_subscriptions_user ON report_subscriptions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_user_quota_date ON user_quota(quota_date)",
    "CREATE INDEX IF NOT EXISTS idx_limit_up_pool_date ON limit_up_pool(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_broken_pool_date ON broken_pool(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_board_ladder_date ON board_ladder_snapshot(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_theme_snapshot_date ON theme_daily_snapshot(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_dragon_tier_date ON dragon_tier_snapshot(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_next_day_plan_date ON next_day_plan(trade_date)",
    "CREATE INDEX IF NOT EXISTS idx_investment_memo_user ON investment_memo(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_industry_mapping_level ON industry_mapping(sw_level)",
    "CREATE INDEX IF NOT EXISTS idx_similar_day_target ON similar_day_case(target_date)",
]


def init_db() -> None:
    with _lock:
        conn = get_conn()
        try:
            for sql in _SCHEMA:
                conn.execute(sql)
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(reports_archive)").fetchall()}
            if "author_id" not in cols:
                conn.execute("ALTER TABLE reports_archive ADD COLUMN author_id INTEGER DEFAULT 1")
            if "author_name" not in cols:
                conn.execute("ALTER TABLE reports_archive ADD COLUMN author_name TEXT DEFAULT '智策官方'")
            for sql in _INDEXES:
                conn.execute(sql)
            conn.commit()
            _seed_admin(conn)
        finally:
            conn.close()


def _seed_admin(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT id FROM users WHERE phone = ?", ("admin",)).fetchone()
    if row:
        return
    import secrets
    import logging
    _logger = logging.getLogger(__name__)
    password = os.environ.get("ZHICE_ADMIN_PASSWORD", "")
    if not password:
        password = secrets.token_urlsafe(16)
        _logger.warning(
            "首次启动已创建管理员账户 admin，随机密码: %s  "
            "请立即登录后修改。或在 .env 中设置 ZHICE_ADMIN_PASSWORD 指定初始密码。",
            password,
        )
    from apps.api.auth.password import hash_password
    conn.execute(
        "INSERT INTO users(phone, password_hash, nickname, vip_level) VALUES (?,?,?,?)",
        ("admin", hash_password(password), "管理员", "pro"),
    )
    conn.commit()


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    with _lock:
        conn = get_conn()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur.lastrowid or cur.rowcount
        finally:
            conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.execute(sql, tuple(params))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


init_db()
