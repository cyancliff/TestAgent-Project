"""Models for multimodal Big Five personality reports."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base

JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


class BigFivePersonalityReport(Base):
    __tablename__ = "big_five_personality_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(String(64), unique=True, index=True, nullable=False, comment="Multimodal task id")
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, comment="Owner user id")
    source_assessment_session_id = Column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
        comment="Optional source ATMR assessment session id",
    )
    title = Column(String(100), nullable=True, comment="User-facing report title")
    status = Column(String(20), default="pending", index=True, nullable=False, comment="pending/running/completed/failed")
    message = Column(Text, nullable=False, default="", comment="User-facing processing message")
    original_filename = Column(String(255), nullable=True, comment="Original uploaded video filename")
    video_path = Column(String(500), nullable=False, comment="Stored video path")
    model_version = Column(String(100), nullable=False, default="scaffold-v1", comment="Model version")
    scores = Column(JSON_TYPE, nullable=True, comment="Big Five scores")
    artifacts = Column(JSON_TYPE, default=dict, nullable=False, comment="Generated artifact paths")
    errors = Column(JSON_TYPE, default=list, nullable=False, comment="Processing errors")
    is_real_result = Column(Boolean, default=False, nullable=False, comment="Whether result came from the real model")
    quality_summary = Column(JSON_TYPE, default=dict, nullable=True, comment="Modality quality assessment")
    confidence_summary = Column(JSON_TYPE, default=dict, nullable=True, comment="Prediction confidence summary")
    consistency_summary = Column(JSON_TYPE, default=dict, nullable=True, comment="ATMR-Big Five consistency analysis")
    interpretation_status = Column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending/running/completed/failed/skipped",
    )
    interpretation_content = Column(Text, nullable=True, comment="AI generated Big Five interpretation markdown")
    interpretation_file_path = Column(String(255), nullable=True, comment="Saved interpretation markdown path")
    interpretation_model = Column(String(100), nullable=True, comment="Model used to generate interpretation")
    interpretation_error = Column(Text, nullable=True, comment="Interpretation generation error")
    interpretation_created_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="big_five_reports")
    source_assessment_session = relationship("AssessmentSession", back_populates="big_five_reports")
    chat_sessions = relationship("ChatSession", back_populates="big_five_report")

    __table_args__ = (
        Index("idx_big_five_report_user_created", "user_id", created_at.desc()),
        Index("idx_big_five_report_user_status", "user_id", "status"),
    )
