"""reports_archive.visibility column — S04 commercial gates foundation

Revision ID: 0003_s04_commercial_gates
Revises: 0002_system_secrets_alerts
Create Date: 2026-05-01

S04 (M001/S04): adds a ``visibility`` VARCHAR(32) column to
``reports_archive`` with server_default='owner'.  This column is the
DB foundation for the paywall lock-point — content behind
``visibility != 'public'`` requires membership to view.  Three valid
states: 'owner' (author only), 'shared_users' (invited), 'public'.
Actual filtering logic lands in S05/S08; this migration only adds the
column with a safe default.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_s04_commercial_gates"
down_revision: Union[str, None] = "0002_system_secrets_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports_archive",
        sa.Column("visibility", sa.String(32), server_default="owner", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("reports_archive", "visibility")
