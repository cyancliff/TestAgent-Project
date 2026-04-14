"""聊天相关模型：咨询会话、聊天消息"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, comment="用户ID")
    assessment_session_id = Column(
        Integer, ForeignKey("assessment_sessions.id"), nullable=True, comment="关联的测评会话ID（可选）"
    )
    title = Column(String(100), default="新对话", comment="会话标题")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), comment="更新时间")

    user = relationship("User", back_populates="chat_sessions")
    assessment_session = relationship("AssessmentSession", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chat_session_id = Column(
        Integer, ForeignKey("chat_sessions.id"), index=True, nullable=False, comment="所属咨询会话ID"
    )
    session_id = Column(
        Integer, ForeignKey("assessment_sessions.id"), index=True, nullable=True, comment="兼容旧数据：测评会话ID"
    )
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, comment="用户ID")
    role = Column(String(20), nullable=False, comment="角色: system/user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="创建时间")

    chat_session = relationship("ChatSession", back_populates="messages")
    session = relationship("AssessmentSession", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")

    __table_args__ = (Index("idx_chat_session_created", "chat_session_id", "created_at"),)
