"""SQLAlchemy 2.x ORM 模型 — 智策项目 27 张表的集中定义。

T03 (M001 / S01) 一次性把 prototype/apps/api/db.py 内联 SQL 重写为 ORM 模型，
为 Alembic 0001_initial revision 提供 target metadata。

设计要点
--------
- 主键统一 ``Integer primary_key=True autoincrement=True``：SQLAlchemy 在 SQLite 走
  ``INTEGER PRIMARY KEY AUTOINCREMENT``、在 MySQL 走 ``BIGINT AUTO_INCREMENT``，无需方言分支。
- ``TEXT`` 字段：使用 :class:`sqlalchemy.String` / :class:`sqlalchemy.Text` 并显式标注
  ``mysql_charset='utf8mb4', mysql_collate='utf8mb4_0900_ai_ci'`` 在 ``__table_args__``。
- ``CURRENT_TIMESTAMP``：用 ``DateTime`` + ``server_default=func.current_timestamp()``。
  连接级别 ``SET time_zone='+00:00'`` 由 ``apps.api.db`` 的 connect listener 强制（见 db.py），
  确保 MySQL TIMESTAMP 隐式时区转换坑被锁死在 UTC。
- "TEXT 存 JSON 字串" 列：保留 :class:`Text` 并在 SQLAlchemy 层 ``default`` 为 ``'[]'`` / ``'{}'`` 的字符串。
  **deviation from plan**：T03 计划写 "MySQL 原生 JSON 类型"。改用 TEXT 是为了 1:1 保
  pymysql 读回 ``json.loads(row['x'])`` 的字符串契约（routes/dashboard.py:64、
  routes/style.py:111 等已有代码假设值是字符串），避开 MySQL 8.0 JSON DEFAULT
  在 8.0.13 前的语法限制 + pymysql 跨版本 JSON 解码差异。utf8mb4 charset 已经覆盖
  unicode 存储语义；JSON 字段格式校验目前由路由层负责。后续 slice 若引入 JSON 谓词
  查询再单独迁移这些列即可。
- 业主指定 charset=utf8mb4、collation=utf8mb4_0900_ai_ci 全表生效（见 deploy/.env.example
  + docker compose 启动参数 + 此文件 ``__table_args__``）。
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# MySQL 8.0 prohibits unparenthesized DEFAULT on TEXT/BLOB/JSON; use the
# expression-default syntax (8.0.13+). _utf8mb4 prefix pins charset of the
# literal so it does not depend on character_set_connection.
_JSON_ARR_DEFAULT = text("(_utf8mb4'[]')")
_JSON_OBJ_DEFAULT = text("(_utf8mb4'{}')")

# Common MySQL table options — every table inherits charset/collation from here.
MYSQL_TABLE_ARGS: dict[str, str] = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
    "mysql_engine": "InnoDB",
}


class Base(DeclarativeBase):
    """Declarative base — all 27 tables register against ``Base.metadata``."""

    pass


# --------------------------------------------------------------------------- #
# 用户 / 配额 / 订单 / 埋点                                                    #
# --------------------------------------------------------------------------- #


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="", server_default="")
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    vip_level: Mapped[str] = mapped_column(String(32), default="free", server_default="free")
    # vip_expire_at remains a string column ("YYYY-MM-DD HH:MM:SS") because
    # apps/api/auth/service.py reads it via datetime.strptime — switching to
    # a native DATETIME would break that call without a routes change.
    vip_expire_at: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    style: Mapped[str] = mapped_column(String(32), default="short", server_default="short")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class UserQuota(Base):
    __tablename__ = "user_quota"
    __table_args__ = (
        Index("idx_user_quota_date", "quota_date"),
        MYSQL_TABLE_ARGS,
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, nullable=False)
    quota_date: Mapped[str] = mapped_column(String(16), primary_key=True, nullable=False)
    feature: Mapped[str] = mapped_column(String(64), primary_key=True, nullable=False)
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", server_default="pending")
    pay_method: Mapped[str] = mapped_column(String(32), default="wechat", server_default="wechat")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )
    paid_at: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_user", "user_id"),
        Index("idx_events_created", "created_at"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event: Mapped[str] = mapped_column(String(128), nullable=False)
    page: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Stored as JSON string (json.dumps from app); see file-level docstring.
    props: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 用户偏好 / 看板 / 题材 / 报告                                                #
# --------------------------------------------------------------------------- #


class StyleProfile(Base):
    __tablename__ = "style_profile"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    answers: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-as-text
    style: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class Dashboard(Base):
    __tablename__ = "dashboards"
    __table_args__ = (
        Index("idx_dashboards_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    layout: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-as-text
    is_default: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class ThemeHistory(Base):
    __tablename__ = "theme_history"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    theme_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    first_seen: Mapped[str] = mapped_column(String(32), nullable=False)
    last_seen: Mapped[str] = mapped_column(String(32), nullable=False)
    appearance_days: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class ReportArchive(Base):
    __tablename__ = "reports_archive"
    __table_args__ = (
        Index("idx_reports_archive_date", "trade_date"),
        Index("idx_reports_archive_author", "author_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    author_name: Mapped[str] = mapped_column(String(128), default="智策官方", server_default="智策官方")
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class ReportSubscription(Base):
    __tablename__ = "report_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "author_id", name="uq_report_subscriptions_user_author"),
        Index("idx_report_subscriptions_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_name: Mapped[str] = mapped_column(String(128), default="", server_default="")
    enabled: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 报警规则 / 策略 / 模拟交易 / 风格组合                                        #
# --------------------------------------------------------------------------- #


class AlertRule(Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        Index("idx_alert_rules_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="limit_up", server_default="limit_up")
    rules: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-as-text
    enabled: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    __table_args__ = (
        Index("idx_paper_trades_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(String(255), default="", server_default="")
    trade_date: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class StyleCombo(Base):
    __tablename__ = "style_combo"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    styles: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-as-text
    updated_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 异动命中 / 邀请码 / 自选股                                                   #
# --------------------------------------------------------------------------- #


class WatchAlert(Base):
    __tablename__ = "watch_alerts"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "code", "kind", "trade_date", name="uq_watch_alerts_user_code_kind_date"
        ),
        Index("idx_watch_alerts_user", "user_id"),
        Index("idx_watch_alerts_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    change_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class InviteCode(Base):
    __tablename__ = "invite_codes"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="standard", server_default="standard", nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=30, server_default="30", nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )
    expires_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class InviteUsage(Base):
    __tablename__ = "invite_usage"
    __table_args__ = (
        UniqueConstraint("code", "user_id", name="uq_invite_usage_code_user"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    used_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class Watchlist(Base):
    __tablename__ = "watchlist"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_watchlist_user_code"),
        Index("idx_watchlist_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    group_name: Mapped[str] = mapped_column(String(64), default="默认", server_default="默认")
    note: Mapped[str] = mapped_column(String(255), default="", server_default="")
    alert_change_up: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_change_down: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_limit_up: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    alert_broken: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 短线数据沉淀                                                                 #
# --------------------------------------------------------------------------- #


class DailyMarketSnapshot(Base):
    __tablename__ = "daily_market_snapshot"
    __table_args__ = (MYSQL_TABLE_ARGS,)

    trade_date: Mapped[str] = mapped_column(String(16), primary_key=True)
    limit_up_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    broken_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    broken_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    seal_success_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    max_board: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    sentiment_level: Mapped[str] = mapped_column(String(32), default="", server_default="")
    sentiment_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    up_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    down_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    limit_down_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_volume: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class LimitUpPool(Base):
    __tablename__ = "limit_up_pool"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_limit_up_pool_date_code"),
        Index("idx_limit_up_pool_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    board_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    limit_time: Mapped[str] = mapped_column(String(16), default="", server_default="")
    reason: Mapped[str] = mapped_column(String(255), default="", server_default="")
    first_plate: Mapped[str] = mapped_column(String(128), default="", server_default="")
    seal_amount: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    change_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")


class BrokenPool(Base):
    __tablename__ = "broken_pool"
    __table_args__ = (
        UniqueConstraint("trade_date", "stock_code", name="uq_broken_pool_date_code"),
        Index("idx_broken_pool_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    board_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    broken_time: Mapped[str] = mapped_column(String(16), default="", server_default="")
    reason_type: Mapped[str] = mapped_column(String(64), default="", server_default="")
    reason_raw: Mapped[str] = mapped_column(String(255), default="", server_default="")
    change_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")


class BoardLadderSnapshot(Base):
    __tablename__ = "board_ladder_snapshot"
    __table_args__ = (
        UniqueConstraint("trade_date", "tier", name="uq_board_ladder_date_tier"),
        Index("idx_board_ladder_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_codes: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default=_JSON_ARR_DEFAULT)
    count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    leader_code: Mapped[str] = mapped_column(String(16), default="", server_default="")
    leader_name: Mapped[str] = mapped_column(String(64), default="", server_default="")


class ThemeDailySnapshot(Base):
    __tablename__ = "theme_daily_snapshot"
    __table_args__ = (
        UniqueConstraint("trade_date", "theme_name", name="uq_theme_daily_snapshot_date_theme"),
        Index("idx_theme_snapshot_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    limit_up_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    change_percent: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    intensity: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    phase: Mapped[str] = mapped_column(String(32), default="", server_default="")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rank_pos: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class DragonTierSnapshot(Base):
    __tablename__ = "dragon_tier_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "trade_date", "theme_name", "stock_code", name="uq_dragon_tier_date_theme_code"
        ),
        Index("idx_dragon_tier_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    theme_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    board_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    change_rate: Mapped[float] = mapped_column(Float, default=0, server_default="0")


class NextDayPlan(Base):
    __tablename__ = "next_day_plan"
    __table_args__ = (
        UniqueConstraint(
            "trade_date", "category", "stock_code", name="uq_next_day_plan_date_cat_code"
        ),
        Index("idx_next_day_plan_date", "trade_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_date: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    stock_code: Mapped[str] = mapped_column(String(16), default="", server_default="")
    stock_name: Mapped[str] = mapped_column(String(64), default="", server_default="")
    reason: Mapped[str] = mapped_column(String(500), default="", server_default="")
    trigger_condition: Mapped[str] = mapped_column(String(255), default="", server_default="")
    invalidate_condition: Mapped[str] = mapped_column(String(255), default="", server_default="")
    theme: Mapped[str] = mapped_column(String(128), default="", server_default="")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 成长价值数据沉淀                                                             #
# --------------------------------------------------------------------------- #


class IndustryMapping(Base):
    __tablename__ = "industry_mapping"
    __table_args__ = (
        UniqueConstraint("sw_code", name="uq_industry_mapping_sw_code"),
        Index("idx_industry_mapping_level", "sw_level"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sw_level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sw_code: Mapped[str] = mapped_column(String(32), nullable=False)
    sw_name: Mapped[str] = mapped_column(String(128), nullable=False)
    concept_tags: Mapped[str] = mapped_column(Text, default="[]", server_default=_JSON_ARR_DEFAULT, nullable=False)
    etf_codes: Mapped[str] = mapped_column(Text, default="[]", server_default=_JSON_ARR_DEFAULT, nullable=False)


class EtfMapping(Base):
    __tablename__ = "etf_mapping"
    __table_args__ = (
        UniqueConstraint("etf_code", name="uq_etf_mapping_etf_code"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    etf_code: Mapped[str] = mapped_column(String(16), nullable=False)
    etf_name: Mapped[str] = mapped_column(String(128), nullable=False)
    track_index: Mapped[str] = mapped_column(String(128), default="", server_default="")
    industry: Mapped[str] = mapped_column(String(128), default="", server_default="")
    style: Mapped[str] = mapped_column(String(64), default="", server_default="")


class SimilarDayCase(Base):
    __tablename__ = "similar_day_case"
    __table_args__ = (
        UniqueConstraint("target_date", "similar_date", name="uq_similar_day_target_similar"),
        Index("idx_similar_day_target", "target_date"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_date: Mapped[str] = mapped_column(String(16), nullable=False)
    similar_date: Mapped[str] = mapped_column(String(16), nullable=False)
    distance: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    snapshot: Mapped[str] = mapped_column(Text, default="{}", server_default=_JSON_OBJ_DEFAULT, nullable=False)
    forward_days: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    forward_data: Mapped[str] = mapped_column(Text, default="{}", server_default=_JSON_OBJ_DEFAULT, nullable=False)
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


class InvestmentMemo(Base):
    __tablename__ = "investment_memo"
    __table_args__ = (
        Index("idx_investment_memo_user", "user_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    memo_type: Mapped[str] = mapped_column(String(32), default="growth", server_default="growth", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    target_codes: Mapped[str] = mapped_column(Text, default="[]", server_default=_JSON_ARR_DEFAULT, nullable=False)
    action: Mapped[str] = mapped_column(String(32), default="observe", server_default="observe")
    created_at: Mapped["DateTime"] = mapped_column(
        DateTime(timezone=False), server_default=func.current_timestamp(), nullable=False
    )


# --------------------------------------------------------------------------- #
# 模型清单（与 db.py 内联 SQL 1:1 对齐 — 27 张表）                              #
# --------------------------------------------------------------------------- #

ALL_MODELS: tuple[type[Base], ...] = (
    User,
    UserQuota,
    Order,
    Event,
    StyleProfile,
    Dashboard,
    ThemeHistory,
    ReportArchive,
    ReportSubscription,
    AlertRule,
    PaperTrade,
    StyleCombo,
    WatchAlert,
    InviteCode,
    InviteUsage,
    Watchlist,
    DailyMarketSnapshot,
    LimitUpPool,
    BrokenPool,
    BoardLadderSnapshot,
    ThemeDailySnapshot,
    DragonTierSnapshot,
    NextDayPlan,
    IndustryMapping,
    EtfMapping,
    SimilarDayCase,
    InvestmentMemo,
)

assert len(ALL_MODELS) == 27, "T03 contract: db_models must define exactly 27 tables"
