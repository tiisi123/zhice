"""S05 compliance terms — terms_accepted_at + payment_terms_accepted_at

Revision ID: 0004_s05_compliance_terms
Revises: 0003_s04_commercial_gates
Create Date: 2026-05-02

S05 (M001/S05): adds nullable DATETIME columns ``terms_accepted_at``
and ``payment_terms_accepted_at`` to ``users``.  These store the UTC
timestamp of when the user accepted the risk-disclosure terms (at
registration) and payment terms (at checkout), forming the audit trail
required for AI compliance.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_s05_compliance_terms"
down_revision: Union[str, None] = "0003_s04_commercial_gates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("payment_terms_accepted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "payment_terms_accepted_at")
    op.drop_column("users", "terms_accepted_at")
