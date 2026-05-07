"""Add lightweight admin console fields.

Revision ID: 20260502_admin_console
Revises: 20260429_atmr_trust
Create Date: 2026-05-02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260502_admin_console"
down_revision = "20260429_atmr_trust"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
    )
    op.add_column(
        "atmr_questions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("atmr_questions", "is_active")
    op.drop_column("users", "role")
