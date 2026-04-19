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
    "ChatSession",
    "ChatMessage",
    "init_db",
]


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_assessment_session_title_column()
    _ensure_user_nickname_column()
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
        if sessions_needing_title_update or users_needing_nickname_update:
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


def _format_assessment_session_title(started_at: datetime | None, session_id: int | None = None) -> str:
    if started_at is not None:
        try:
            return started_at.astimezone().strftime("%Y.%m.%d %H:%M")
        except Exception:
            return started_at.strftime("%Y.%m.%d %H:%M")
    if session_id is not None:
        return f"测评 #{session_id}"
    return "未命名测评"
