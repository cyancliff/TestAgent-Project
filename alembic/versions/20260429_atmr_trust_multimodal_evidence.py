"""Add ATMR trust and multimodal evidence summaries.

Revision ID: 20260429_atmr_trust
Revises:
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260429_atmr_trust"
down_revision = None
branch_labels = None
depends_on = None


json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.add_column("answer_records", sa.Column("risk_score", sa.Integer(), nullable=True))
    op.add_column("answer_records", sa.Column("risk_reasons", json_type, nullable=True))
    op.add_column("answer_records", sa.Column("answer_confidence", sa.Float(), nullable=True))
    op.add_column("answer_records", sa.Column("behavior_metrics", json_type, nullable=True))

    op.add_column("assessment_sessions", sa.Column("trust_summary", json_type, nullable=True))
    op.add_column("assessment_sessions", sa.Column("adaptive_metrics", json_type, nullable=True))
    op.add_column("assessment_sessions", sa.Column("evidence_summary", json_type, nullable=True))

    op.add_column("big_five_personality_reports", sa.Column("quality_summary", json_type, nullable=True))
    op.add_column("big_five_personality_reports", sa.Column("confidence_summary", json_type, nullable=True))
    op.add_column("big_five_personality_reports", sa.Column("consistency_summary", json_type, nullable=True))

    op.execute("UPDATE answer_records SET risk_score = 0 WHERE risk_score IS NULL")
    op.execute("UPDATE answer_records SET answer_confidence = 1.0 WHERE answer_confidence IS NULL")


def downgrade() -> None:
    op.drop_column("big_five_personality_reports", "consistency_summary")
    op.drop_column("big_five_personality_reports", "confidence_summary")
    op.drop_column("big_five_personality_reports", "quality_summary")

    op.drop_column("assessment_sessions", "evidence_summary")
    op.drop_column("assessment_sessions", "adaptive_metrics")
    op.drop_column("assessment_sessions", "trust_summary")

    op.drop_column("answer_records", "answer_confidence")
    op.drop_column("answer_records", "risk_reasons")
    op.drop_column("answer_records", "risk_score")
    op.drop_column("answer_records", "behavior_metrics")
