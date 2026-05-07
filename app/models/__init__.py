"""
Central exports for ORM models.

Model modules are imported here so SQLAlchemy metadata includes every table,
but table creation stays explicit via init_db() instead of running on import.
"""

import logging
import re
from datetime import datetime

from sqlalchemy import inspect, text

from app.core.database import Base, SessionLocal, engine
from app.models.assessment import AnswerRecord, AssessmentSession, ModuleDebateResult, Question
from app.models.chat import ChatMessage, ChatSession
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User

logger = logging.getLogger(__name__)
DEFAULT_ASSESSMENT_TITLE_PATTERN = re.compile(r"^测评 #\d+$")

__all__ = [
    "Base",
    "engine",
    "User",
    "Question",
    "AssessmentSession",
    "AnswerRecord",
    "ModuleDebateResult",
    "BigFivePersonalityReport",
    "ChatSession",
    "ChatMessage",
    "init_db",
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_assessment_session_title_column()
    _ensure_assessment_session_revision_columns()
    _ensure_assessment_trust_columns()
    _ensure_answer_trust_columns()
    _ensure_chat_session_big_five_report_column()
    _ensure_big_five_interpretation_columns()
    _ensure_big_five_evidence_columns()
    _ensure_user_nickname_column()
    _ensure_user_role_column()
    _ensure_question_active_column()
    from app.services.question_sanitizer import repair_question_contents

    db = SessionLocal()
    try:
        sessions_needing_title_update = [
            session
            for session in db.query(AssessmentSession).all()
            if not (session.title or "").strip() or DEFAULT_ASSESSMENT_TITLE_PATTERN.fullmatch((session.title or "").strip())
        ]
        for session in sessions_needing_title_update:
            session.title = _format_assessment_session_title(session.started_at, session.id)
        users_needing_nickname_update = [
            user
            for user in db.query(User).all()
            if not (user.nickname or "").strip()
        ]
        for user in users_needing_nickname_update:
            user.nickname = (user.username or "用户").strip()
        role_updates = _sync_configured_admin_roles(db)
        if sessions_needing_title_update or users_needing_nickname_update or role_updates:
            db.commit()

        updated_count = repair_question_contents(db)
        if updated_count:
            logger.info("Normalized %s existing question contents during startup", updated_count)
    finally:
        db.close()


def _ensure_assessment_session_title_column() -> None:
    inspector = inspect(engine)
    if "assessment_sessions" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("assessment_sessions")}
    if "title" in column_names:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE assessment_sessions ADD COLUMN title VARCHAR(100)"))
    logger.info("Added missing assessment_sessions.title column")


def _ensure_assessment_session_revision_columns() -> None:
    inspector = inspect(engine)
    if "assessment_sessions" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("assessment_sessions")}

    statements = []
    if "parent_session_id" not in column_names:
        statements.append("ALTER TABLE assessment_sessions ADD COLUMN parent_session_id INTEGER")
    if "revision_no" not in column_names:
        statements.append("ALTER TABLE assessment_sessions ADD COLUMN revision_no INTEGER DEFAULT 1")

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        if statements:
            logger.info("Added missing assessment_sessions revision columns")

        connection.execute(text("UPDATE assessment_sessions SET revision_no = 1 WHERE revision_no IS NULL"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_assessment_sessions_parent_session_id "
                "ON assessment_sessions (parent_session_id)"
            )
        )


def _json_column_type() -> str:
    return "JSONB" if engine.dialect.name == "postgresql" else "JSON"


def _ensure_assessment_trust_columns() -> None:
    inspector = inspect(engine)
    if "assessment_sessions" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("assessment_sessions")}
    json_type = _json_column_type()
    statements = []
    if "trust_summary" not in column_names:
        statements.append(f"ALTER TABLE assessment_sessions ADD COLUMN trust_summary {json_type}")
    if "adaptive_metrics" not in column_names:
        statements.append(f"ALTER TABLE assessment_sessions ADD COLUMN adaptive_metrics {json_type}")
    if "evidence_summary" not in column_names:
        statements.append(f"ALTER TABLE assessment_sessions ADD COLUMN evidence_summary {json_type}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    logger.info("Added missing assessment_sessions trust/evidence columns")


def _ensure_answer_trust_columns() -> None:
    inspector = inspect(engine)
    if "answer_records" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("answer_records")}
    json_type = _json_column_type()
    statements = []
    if "risk_score" not in column_names:
        statements.append("ALTER TABLE answer_records ADD COLUMN risk_score INTEGER")
    if "risk_reasons" not in column_names:
        statements.append(f"ALTER TABLE answer_records ADD COLUMN risk_reasons {json_type}")
    if "answer_confidence" not in column_names:
        statements.append("ALTER TABLE answer_records ADD COLUMN answer_confidence FLOAT")
    if "behavior_metrics" not in column_names:
        statements.append(f"ALTER TABLE answer_records ADD COLUMN behavior_metrics {json_type}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        connection.execute(text("UPDATE answer_records SET risk_score = 0 WHERE risk_score IS NULL"))
        connection.execute(text("UPDATE answer_records SET answer_confidence = 1.0 WHERE answer_confidence IS NULL"))
    logger.info("Added missing answer_records trust columns")


def _ensure_chat_session_big_five_report_column() -> None:
    inspector = inspect(engine)
    if "chat_sessions" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("chat_sessions")}
    with engine.begin() as connection:
        if "big_five_report_id" not in column_names:
            connection.execute(text("ALTER TABLE chat_sessions ADD COLUMN big_five_report_id INTEGER"))
            logger.info("Added missing chat_sessions.big_five_report_id column")

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_chat_sessions_big_five_report_id "
                "ON chat_sessions (big_five_report_id)"
            )
        )


def _ensure_big_five_interpretation_columns() -> None:
    inspector = inspect(engine)
    if "big_five_personality_reports" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("big_five_personality_reports")}
    statements = []
    if "interpretation_status" not in column_names:
        statements.append(
            "ALTER TABLE big_five_personality_reports "
            "ADD COLUMN interpretation_status VARCHAR(20) DEFAULT 'pending' NOT NULL"
        )
    if "interpretation_content" not in column_names:
        statements.append("ALTER TABLE big_five_personality_reports ADD COLUMN interpretation_content TEXT")
    if "interpretation_file_path" not in column_names:
        statements.append("ALTER TABLE big_five_personality_reports ADD COLUMN interpretation_file_path VARCHAR(255)")
    if "interpretation_model" not in column_names:
        statements.append("ALTER TABLE big_five_personality_reports ADD COLUMN interpretation_model VARCHAR(100)")
    if "interpretation_error" not in column_names:
        statements.append("ALTER TABLE big_five_personality_reports ADD COLUMN interpretation_error TEXT")
    if "interpretation_created_at" not in column_names:
        timestamp_type = "TIMESTAMP WITH TIME ZONE" if engine.dialect.name == "postgresql" else "DATETIME"
        statements.append(f"ALTER TABLE big_five_personality_reports ADD COLUMN interpretation_created_at {timestamp_type}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    logger.info("Added missing big_five_personality_reports interpretation columns")


def _ensure_big_five_evidence_columns() -> None:
    inspector = inspect(engine)
    if "big_five_personality_reports" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("big_five_personality_reports")}
    json_type = _json_column_type()
    statements = []
    if "quality_summary" not in column_names:
        statements.append(f"ALTER TABLE big_five_personality_reports ADD COLUMN quality_summary {json_type}")
    if "confidence_summary" not in column_names:
        statements.append(f"ALTER TABLE big_five_personality_reports ADD COLUMN confidence_summary {json_type}")
    if "consistency_summary" not in column_names:
        statements.append(f"ALTER TABLE big_five_personality_reports ADD COLUMN consistency_summary {json_type}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    logger.info("Added missing big_five_personality_reports evidence columns")


def _ensure_user_nickname_column() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "nickname" in column_names:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(50)"))
    logger.info("Added missing users.nickname column")


def _ensure_user_role_column() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("users")}
    if "role" not in column_names:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user' NOT NULL"))
        logger.info("Added missing users.role column")
        return

    with engine.begin() as connection:
        connection.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''"))


def _ensure_question_active_column() -> None:
    inspector = inspect(engine)
    if "atmr_questions" not in inspector.get_table_names():
        return

    column_names = {column["name"] for column in inspector.get_columns("atmr_questions")}
    if "is_active" not in column_names:
        default_value = "TRUE" if engine.dialect.name == "postgresql" else "1"
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE atmr_questions ADD COLUMN is_active BOOLEAN DEFAULT {default_value} NOT NULL"))
        logger.info("Added missing atmr_questions.is_active column")
        return

    active_value = "TRUE" if engine.dialect.name == "postgresql" else "1"
    with engine.begin() as connection:
        connection.execute(text(f"UPDATE atmr_questions SET is_active = {active_value} WHERE is_active IS NULL"))


def _sync_configured_admin_roles(db) -> bool:
    from app.core.security import resolve_user_role

    changed = False
    for user in db.query(User).all():
        resolved_role = resolve_user_role(user.username, getattr(user, "role", None))
        if getattr(user, "role", None) != resolved_role:
            user.role = resolved_role
            changed = True
    return changed


def _format_assessment_session_title(started_at: datetime | None, session_id: int | None = None) -> str:
    if started_at is not None:
        try:
            return started_at.astimezone().strftime("%Y.%m.%d %H:%M")
        except Exception:
            return started_at.strftime("%Y.%m.%d %H:%M")
    if session_id is not None:
        return f"测评 #{session_id}"
    return "未命名测评"
