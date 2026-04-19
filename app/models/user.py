"""用户模型"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, comment="用户名")
    nickname = Column(String(50), nullable=True, comment="用户昵称")
    password_hash = Column(String(255), comment="密码哈希")
    avatar_url = Column(Text, nullable=True, comment="头像路径（相对路径）")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment="注册时间")

    # 关系（懒加载，引用延迟绑定避免循环导入）
    sessions = relationship("AssessmentSession", back_populates="user")
    answers = relationship("AnswerRecord", back_populates="user")
    debate_results = relationship("ModuleDebateResult", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
