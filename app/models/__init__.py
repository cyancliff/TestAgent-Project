"""
数据模型统一导出

所有 ORM 模型按领域拆分到此包下：
- app.models.user: User
- app.models.assessment: Question, AssessmentSession, AnswerRecord, ModuleDebateResult
- app.models.chat: ChatSession, ChatMessage

此模块导入时自动建表（开发便利），生产环境请使用 Alembic 迁移。
"""

from app.models.user import User
from app.models.assessment import Question, AssessmentSession, AnswerRecord, ModuleDebateResult
from app.models.chat import ChatSession, ChatMessage

# 兼容旧代码：从 app.models.question 的导出名
__all__ = [
    "User",
    "Question",
    "AssessmentSession",
    "AnswerRecord",
    "ModuleDebateResult",
    "ChatSession",
    "ChatMessage",
]

# 自动建表（开发模式便利，生产环境应使用 Alembic）
from app.core.database import Base, engine

Base.metadata.create_all(bind=engine)
