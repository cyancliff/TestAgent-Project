"""
Central exports for ORM models.

Model modules are imported here so SQLAlchemy metadata includes every table,
but table creation stays explicit via init_db() instead of running on import.
"""

from app.core.database import Base, engine
from app.models.assessment import AnswerRecord, AssessmentSession, ModuleDebateResult, Question
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

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
