"""initial schema — 27 tables migrated from apps/api/db.py inline SQL.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-30

T03 (M001/S01): hand-written initial revision (sandbox has no SQLAlchemy so
``alembic revision --autogenerate`` was not run). The DDL below mirrors
``packages/shared/db_models.py`` 1:1; CI verifies parity by booting a fresh
MySQL 8.0 container and running ``alembic upgrade head`` (see slice plan
verification block).

Charset/collation: every table is created with ``utf8mb4`` /
``utf8mb4_0900_ai_ci`` and ``InnoDB`` engine (T03 contract). TIMESTAMP-typed
columns rely on the connection-level ``time_zone='+00:00'`` enforced in
``apps.api.db.get_engine`` and ``alembic/env.run_migrations_online``.

JSON-as-text columns (``concept_tags``, ``stock_codes``, ``snapshot``, etc.)
that previously carried SQLite ``DEFAULT '[]'`` / ``DEFAULT '{}'`` use
``DEFAULT (_utf8mb4'[]')`` parenthesized expressions — MySQL 8.0 forbids
unparenthesized DEFAULT on TEXT/BLOB/JSON/GEOMETRY (see error 1101). The
charset prefix is required so the literal is interpreted under utf8mb4
regardless of the server character_set_connection.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Common kwargs applied to every create_table call so charset/collation/engine
# stay consistent across all 27 tables.
_TABLE_KW = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
    "mysql_engine": "InnoDB",
}


def _ts_default() -> sa.sql.elements.TextClause:
    """Server-side default for TIMESTAMP columns (UTC via session time_zone)."""
    return sa.text("CURRENT_TIMESTAMP")


def upgrade() -> None:
    # ---------------- users / quota / orders / events ----------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("phone", sa.String(64), nullable=False, unique=True),
        sa.Column("nickname", sa.String(64), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("vip_level", sa.String(32), nullable=False, server_default="free"),
        sa.Column("vip_expire_at", sa.String(32), nullable=True),
        sa.Column("style", sa.String(32), nullable=False, server_default="short"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )

    op.create_table(
        "user_quota",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("quota_date", sa.String(16), primary_key=True, nullable=False),
        sa.Column("feature", sa.String(64), primary_key=True, nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        **_TABLE_KW,
    )
    op.create_index("idx_user_quota_date", "user_quota", ["quota_date"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_no", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("pay_method", sa.String(32), nullable=False, server_default="wechat"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.Column("paid_at", sa.String(32), nullable=True),
        **_TABLE_KW,
    )
    op.create_index("idx_orders_user", "orders", ["user_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(128), nullable=False),
        sa.Column("page", sa.String(128), nullable=True),
        sa.Column("props", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_events_user", "events", ["user_id"])
    op.create_index("idx_events_created", "events", ["created_at"])

    # ---------------- preferences / dashboards / themes / reports ----------------
    op.create_table(
        "style_profile",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("answers", sa.Text(), nullable=False),
        sa.Column("style", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )

    op.create_table(
        "dashboards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("layout", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_dashboards_user", "dashboards", ["user_id"])

    op.create_table(
        "theme_history",
        sa.Column("theme_name", sa.String(128), primary_key=True),
        sa.Column("first_seen", sa.String(32), nullable=False),
        sa.Column("last_seen", sa.String(32), nullable=False),
        sa.Column("appearance_days", sa.Integer(), nullable=False, server_default="1"),
        **_TABLE_KW,
    )

    op.create_table(
        "reports_archive",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("author_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("author_name", sa.String(128), nullable=False, server_default="智策官方"),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_reports_archive_date", "reports_archive", ["trade_date"])
    op.create_index("idx_reports_archive_author", "reports_archive", ["author_id"])

    op.create_table(
        "report_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("author_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint("user_id", "author_id", name="uq_report_subscriptions_user_author"),
        **_TABLE_KW,
    )
    op.create_index("idx_report_subscriptions_user", "report_subscriptions", ["user_id"])

    # ---------------- alert rules / paper trades / style combo ----------------
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="limit_up"),
        sa.Column("rules", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_alert_rules_user", "alert_rules", ["user_id"])

    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(255), nullable=False, server_default=""),
        sa.Column("trade_date", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_paper_trades_user", "paper_trades", ["user_id"])

    op.create_table(
        "style_combo",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("styles", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )

    # ---------------- watch alerts / invite codes / watchlist ----------------
    op.create_table(
        "watch_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False, server_default=""),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("change_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint(
            "user_id", "code", "kind", "trade_date", name="uq_watch_alerts_user_code_kind_date"
        ),
        **_TABLE_KW,
    )
    op.create_index("idx_watch_alerts_user", "watch_alerts", ["user_id"])
    op.create_index("idx_watch_alerts_date", "watch_alerts", ["trade_date"])

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("plan", sa.String(32), nullable=False, server_default="standard"),
        sa.Column("days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.Column("expires_at", sa.String(32), nullable=True),
        **_TABLE_KW,
    )

    op.create_table(
        "invite_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint("code", "user_id", name="uq_invite_usage_code_user"),
        **_TABLE_KW,
    )

    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("name", sa.String(64), nullable=False, server_default=""),
        sa.Column("group_name", sa.String(64), nullable=False, server_default="默认"),
        sa.Column("note", sa.String(255), nullable=False, server_default=""),
        sa.Column("alert_change_up", sa.Float(), nullable=True),
        sa.Column("alert_change_down", sa.Float(), nullable=True),
        sa.Column("alert_limit_up", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("alert_broken", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint("user_id", "code", name="uq_watchlist_user_code"),
        **_TABLE_KW,
    )
    op.create_index("idx_watchlist_user", "watchlist", ["user_id"])

    # ---------------- short-line market snapshots ----------------
    op.create_table(
        "daily_market_snapshot",
        sa.Column("trade_date", sa.String(16), primary_key=True),
        sa.Column("limit_up_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("broken_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("broken_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("seal_success_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_board", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentiment_level", sa.String(32), nullable=False, server_default=""),
        sa.Column("sentiment_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("up_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("down_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limit_down_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_volume", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )

    op.create_table(
        "limit_up_pool",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("stock_code", sa.String(16), nullable=False),
        sa.Column("stock_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("board_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("limit_time", sa.String(16), nullable=False, server_default=""),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("first_plate", sa.String(128), nullable=False, server_default=""),
        sa.Column("seal_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("change_rate", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("trade_date", "stock_code", name="uq_limit_up_pool_date_code"),
        **_TABLE_KW,
    )
    op.create_index("idx_limit_up_pool_date", "limit_up_pool", ["trade_date"])

    op.create_table(
        "broken_pool",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("stock_code", sa.String(16), nullable=False),
        sa.Column("stock_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("board_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("broken_time", sa.String(16), nullable=False, server_default=""),
        sa.Column("reason_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("reason_raw", sa.String(255), nullable=False, server_default=""),
        sa.Column("change_rate", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("trade_date", "stock_code", name="uq_broken_pool_date_code"),
        **_TABLE_KW,
    )
    op.create_index("idx_broken_pool_date", "broken_pool", ["trade_date"])

    op.create_table(
        "board_ladder_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("stock_codes", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'[]')")),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leader_code", sa.String(16), nullable=False, server_default=""),
        sa.Column("leader_name", sa.String(64), nullable=False, server_default=""),
        sa.UniqueConstraint("trade_date", "tier", name="uq_board_ladder_date_tier"),
        **_TABLE_KW,
    )
    op.create_index("idx_board_ladder_date", "board_ladder_snapshot", ["trade_date"])

    op.create_table(
        "theme_daily_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("theme_name", sa.String(128), nullable=False),
        sa.Column("limit_up_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("intensity", sa.Float(), nullable=False, server_default="0"),
        sa.Column("phase", sa.String(32), nullable=False, server_default=""),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rank_pos", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("trade_date", "theme_name", name="uq_theme_daily_snapshot_date_theme"),
        **_TABLE_KW,
    )
    op.create_index("idx_theme_snapshot_date", "theme_daily_snapshot", ["trade_date"])

    op.create_table(
        "dragon_tier_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("theme_name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("stock_code", sa.String(16), nullable=False),
        sa.Column("stock_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("board_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_rate", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "trade_date", "theme_name", "stock_code", name="uq_dragon_tier_date_theme_code"
        ),
        **_TABLE_KW,
    )
    op.create_index("idx_dragon_tier_date", "dragon_tier_snapshot", ["trade_date"])

    op.create_table(
        "next_day_plan",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_date", sa.String(16), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("stock_code", sa.String(16), nullable=False, server_default=""),
        sa.Column("stock_name", sa.String(64), nullable=False, server_default=""),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("trigger_condition", sa.String(255), nullable=False, server_default=""),
        sa.Column("invalidate_condition", sa.String(255), nullable=False, server_default=""),
        sa.Column("theme", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint(
            "trade_date", "category", "stock_code", name="uq_next_day_plan_date_cat_code"
        ),
        **_TABLE_KW,
    )
    op.create_index("idx_next_day_plan_date", "next_day_plan", ["trade_date"])

    # ---------------- growth/value snapshots ----------------
    op.create_table(
        "industry_mapping",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sw_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sw_code", sa.String(32), nullable=False),
        sa.Column("sw_name", sa.String(128), nullable=False),
        sa.Column("concept_tags", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'[]')")),
        sa.Column("etf_codes", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'[]')")),
        sa.UniqueConstraint("sw_code", name="uq_industry_mapping_sw_code"),
        **_TABLE_KW,
    )
    op.create_index("idx_industry_mapping_level", "industry_mapping", ["sw_level"])

    op.create_table(
        "etf_mapping",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("etf_code", sa.String(16), nullable=False),
        sa.Column("etf_name", sa.String(128), nullable=False),
        sa.Column("track_index", sa.String(128), nullable=False, server_default=""),
        sa.Column("industry", sa.String(128), nullable=False, server_default=""),
        sa.Column("style", sa.String(64), nullable=False, server_default=""),
        sa.UniqueConstraint("etf_code", name="uq_etf_mapping_etf_code"),
        **_TABLE_KW,
    )

    op.create_table(
        "similar_day_case",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_date", sa.String(16), nullable=False),
        sa.Column("similar_date", sa.String(16), nullable=False),
        sa.Column("distance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("snapshot", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'{}')")),
        sa.Column("forward_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("forward_data", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'{}')")),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        sa.UniqueConstraint("target_date", "similar_date", name="uq_similar_day_target_similar"),
        **_TABLE_KW,
    )
    op.create_index("idx_similar_day_target", "similar_day_case", ["target_date"])

    op.create_table(
        "investment_memo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("memo_type", sa.String(32), nullable=False, server_default="growth"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("target_codes", sa.Text(), nullable=False, server_default=sa.text("(_utf8mb4'[]')")),
        sa.Column("action", sa.String(32), nullable=False, server_default="observe"),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=_ts_default()),
        **_TABLE_KW,
    )
    op.create_index("idx_investment_memo_user", "investment_memo", ["user_id"])


def downgrade() -> None:
    # Drop in reverse dependency order. T03 is the initial revision; downgrade
    # exists for completeness but the operational story is "fresh DB on staging".
    op.drop_index("idx_investment_memo_user", table_name="investment_memo")
    op.drop_table("investment_memo")
    op.drop_index("idx_similar_day_target", table_name="similar_day_case")
    op.drop_table("similar_day_case")
    op.drop_table("etf_mapping")
    op.drop_index("idx_industry_mapping_level", table_name="industry_mapping")
    op.drop_table("industry_mapping")
    op.drop_index("idx_next_day_plan_date", table_name="next_day_plan")
    op.drop_table("next_day_plan")
    op.drop_index("idx_dragon_tier_date", table_name="dragon_tier_snapshot")
    op.drop_table("dragon_tier_snapshot")
    op.drop_index("idx_theme_snapshot_date", table_name="theme_daily_snapshot")
    op.drop_table("theme_daily_snapshot")
    op.drop_index("idx_board_ladder_date", table_name="board_ladder_snapshot")
    op.drop_table("board_ladder_snapshot")
    op.drop_index("idx_broken_pool_date", table_name="broken_pool")
    op.drop_table("broken_pool")
    op.drop_index("idx_limit_up_pool_date", table_name="limit_up_pool")
    op.drop_table("limit_up_pool")
    op.drop_table("daily_market_snapshot")
    op.drop_index("idx_watchlist_user", table_name="watchlist")
    op.drop_table("watchlist")
    op.drop_table("invite_usage")
    op.drop_table("invite_codes")
    op.drop_index("idx_watch_alerts_date", table_name="watch_alerts")
    op.drop_index("idx_watch_alerts_user", table_name="watch_alerts")
    op.drop_table("watch_alerts")
    op.drop_table("style_combo")
    op.drop_index("idx_paper_trades_user", table_name="paper_trades")
    op.drop_table("paper_trades")
    op.drop_index("idx_alert_rules_user", table_name="alert_rules")
    op.drop_table("alert_rules")
    op.drop_index("idx_report_subscriptions_user", table_name="report_subscriptions")
    op.drop_table("report_subscriptions")
    op.drop_index("idx_reports_archive_author", table_name="reports_archive")
    op.drop_index("idx_reports_archive_date", table_name="reports_archive")
    op.drop_table("reports_archive")
    op.drop_table("theme_history")
    op.drop_index("idx_dashboards_user", table_name="dashboards")
    op.drop_table("dashboards")
    op.drop_table("style_profile")
    op.drop_index("idx_events_created", table_name="events")
    op.drop_index("idx_events_user", table_name="events")
    op.drop_table("events")
    op.drop_index("idx_orders_user", table_name="orders")
    op.drop_table("orders")
    op.drop_index("idx_user_quota_date", table_name="user_quota")
    op.drop_table("user_quota")
    op.drop_table("users")
