"""S04 portfolio columns — cost_price + shares on watchlist

Revision ID: 0005_s04_portfolio_columns
Revises: 0004_s05_compliance_terms
Create Date: 2026-05-04

M002/S04: adds nullable REAL ``cost_price`` and nullable INTEGER ``shares``
columns to ``watchlist``.  NULL means pure watch-only item; non-NULL means
the user holds a position (D011).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_s04_portfolio_columns"
down_revision: Union[str, None] = "0004_s05_compliance_terms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "watchlist",
        sa.Column("cost_price", sa.Float(), nullable=True),
    )
    op.add_column(
        "watchlist",
        sa.Column("shares", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("watchlist", "shares")
    op.drop_column("watchlist", "cost_price")
