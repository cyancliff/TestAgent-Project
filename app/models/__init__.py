"""
Central exports for ORM models.

Model modules are imported here so SQLAlchemy metadata includes every table,
but table creation stays explicit via init_db() instead of running on import.
"""

import logging

from app.core.database import Base, SessionLocal, engine
from app.models.assessment import AnswerRecord, AssessmentSession, ModuleDebateResult, Question
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

logger = logging.getLogger(__name__)

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
    from app.services.question_sanitizer import repair_question_contents

    db = SessionLocal()
    try:
        updated_count = repair_question_contents(db)
        if updated_count:
            logger.info("Normalized %s existing question contents during startup", updated_count)
    finally:
        db.close()
