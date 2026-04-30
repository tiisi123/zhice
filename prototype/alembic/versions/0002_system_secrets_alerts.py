"""system_secrets + system_alerts — KPL Cookie 加密存储 + 健康探测告警

Revision ID: 0002_system_secrets_alerts
Revises: 0001_initial
Create Date: 2026-05-01

T03 (M001/S03): adds two tables for the cookie-aware data path:

- ``system_secrets`` — Fernet-encrypted secret store. The c1 KPL Cookie
  topology lands as a single ``secret_key='kpl_cookie'`` row shared across
  realtime/history/merge hosts. ``secret_type`` reserves the c2 upgrade
  path (per-endpoint cookie domains) without further migration.
- ``system_alerts`` — health-probe alert log written by the APScheduler
  30-minute jobs (S03/T05). The composite index on ``(kind, resolved_at)``
  supports the admin "unresolved=1" filter.

Charset/collation/engine match the S01 baseline (utf8mb4 / utf8mb4_0900_ai_ci /
InnoDB). TEXT columns with ``DEFAULT '...'`` use the parenthesized
``DEFAULT (_utf8mb4'...')`` expression-default syntax — MySQL 8.0 forbids
unparenthesized DEFAULT on TEXT/BLOB/JSON (errno 1101).

A placeholder ``kpl_cookie`` row is INSERTed in upgrade so the admin
``/admin/kpl-cookie`` POST handler can UPDATE on first paste (no INSERT
branch needed in cookie_provider.set_kpl_cookie).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_system_secrets_alerts"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE_KW = {
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
    "mysql_engine": "InnoDB",
}


def upgrade() -> None:
    op.create_table(
        "system_secrets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("secret_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "secret_value",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(_utf8mb4'')"),
        ),
        sa.Column("secret_type", sa.String(32), nullable=False, server_default="cookie"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        **_TABLE_KW,
    )

    op.create_table(
        "system_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("message", sa.String(500), nullable=False, server_default=""),
        sa.Column(
            "meta",
            sa.Text(),
            nullable=False,
            server_default=sa.text("(_utf8mb4'{}')"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        **_TABLE_KW,
    )
    op.create_index(
        "idx_system_alerts_kind_resolved",
        "system_alerts",
        ["kind", "resolved_at"],
    )

    # Seed a placeholder row so /admin/kpl-cookie POST is always a pure UPDATE.
    # secret_value='' encrypts to nothing — cookie_provider.get_kpl_cookie
    # returns '' until an admin posts a real cookie.
    op.execute(
        "INSERT INTO system_secrets(secret_key, secret_value, secret_type) "
        "VALUES ('kpl_cookie', '', 'cookie')"
    )


def downgrade() -> None:
    op.drop_index("idx_system_alerts_kind_resolved", table_name="system_alerts")
    op.drop_table("system_alerts")
    op.drop_table("system_secrets")
