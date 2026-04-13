from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, relationship

from app.core.database import Base, SessionLocal, engine, ensure_column


# --- 题目表 (静态题库) ---
class Question(Base):
    __tablename__ = "atmr_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    exam_no = Column(String(50), unique=True, index=True, comment="题目编号")
    dimension_id = Column(String(10), index=True, comment="维度ID")
    content = Column(Text, comment="题干内容")
    options = Column(JSONB, comment="选项列表")
    scores = Column(JSONB, comment="选项对应的分值")

    trait_label = Column(String(100), nullable=True, comment="特质标签")
    ai_analysis_prompt = Column(Text, nullable=True, comment="官方解析")

    is_reverse = Column(Boolean, default=False, comment="是否反向计分")
    avg_time = Column(Numeric(5, 2), default=8.0, comment="预估平均作答时间(秒)")

    # 题目特征向量 (用于智能选题)
    feature_vector = Column(JSONB, nullable=True, comment="题目特征向量")
    feature_dim = Column(Integer, nullable=True, comment="特征向量维度")
    discrimination = Column(Numeric(4, 3), nullable=True, comment="题目区分度(0-1)")
    difficulty = Column(Numeric(4, 3), nullable=True, comment="题目难度(0-1)")

    # 关系
    answers = relationship(
        "AnswerRecord",
        back_populates="question",
        foreign_keys="AnswerRecord.exam_no",
        primaryjoin="Question.exam_no == foreign(AnswerRecord.exam_no)",
    )


# --- 用户表 ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, comment="用户名")
    password_hash = Column(String(255), comment="密码哈希")
    avatar_url = Column(Text, nullable=True, comment="头像 base64 数据")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="注册时间")

    # 关系
    sessions = relationship("AssessmentSession", back_populates="user")
    answers = relationship("AnswerRecord", back_populates="user")
    debate_results = relationship("ModuleDebateResult", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


# --- 测评会话表 ---
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, comment="受试者ID")
    started_at = Column(DateTime(timezone=True), default=datetime.now, comment="开始时间")
    finished_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    status = Column(String(20), default="active", comment="状态: active/completed")
    current_stage = Column(String(20), default="intro", comment="当前阶段: intro/A/T/M/R")
    submitted_stages = Column(JSONB, default=list, comment="已提交的阶段列表")
    report_content = Column(Text, nullable=True, comment="报告内容")
    report_file_path = Column(String(255), nullable=True, comment="报告文件路径")

    # 关系
    user = relationship("User", back_populates="sessions")
    answers = relationship("AnswerRecord", back_populates="session")
    debate_results = relationship("ModuleDebateResult", back_populates="session")
    chat_sessions = relationship("ChatSession", back_populates="assessment_session")
    chat_messages = relationship("ChatMessage", back_populates="session")

    __table_args__ = (Index("idx_session_user_started", "user_id", started_at.desc()),)


# --- 作答记录表 ---
class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("assessment_sessions.id"), index=True, comment="所属会话ID")
    user_id = Column(Integer, ForeignKey("users.id"), index=True, comment="受试者唯一ID")
    exam_no = Column(String(50), index=True, comment="题目编号")
    selected_option = Column(Text, comment="选择的选项内容")
    score = Column(Numeric(4, 2), comment="该题得分")
    time_spent = Column(Numeric(6, 2), comment="实际作答耗时(秒)")

    # 存入 AI 的拦截结果与用户的解释
    is_anomaly = Column(Integer, default=0, comment="是否异常: 0正常, 1异常")
    ai_follow_up = Column(Text, nullable=True, comment="AI追问内容")
    user_explanation = Column(Text, nullable=True, comment="用户对异常的解释")

    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="答题时间")

    # 关系
    session = relationship("AssessmentSession", back_populates="answers")
    user = relationship("User", back_populates="answers")
    question = relationship(
        "Question",
        back_populates="answers",
        foreign_keys=[exam_no],
        primaryjoin="AnswerRecord.exam_no == Question.exam_no",
    )

    __table_args__ = (
        Index("idx_answer_session_user", "session_id", "user_id"),
        Index("idx_answer_session_user_exam", "session_id", "user_id", "exam_no"),
    )


# --- 模块辩论结果表 ---
class ModuleDebateResult(Base):
    __tablename__ = "module_debate_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("assessment_sessions.id"), index=True, comment="所属会话ID")
    user_id = Column(Integer, ForeignKey("users.id"), index=True, comment="用户ID")
    module = Column(String(10), index=True, comment="模块类型: A/T/M/R")
    result_content = Column(Text, comment="辩论结果内容")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="创建时间")

    # 关系
    session = relationship("AssessmentSession", back_populates="debate_results")
    user = relationship("User", back_populates="debate_results")

    __table_args__ = (Index("idx_debate_session_module", "session_id", "module"),)


# --- 咨询会话表 ---
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False, comment="用户ID")
    assessment_session_id = Column(
        Integer, ForeignKey("assessment_sessions.id"), nullable=True, comment="关联的测评会话ID（可选）"
    )
    title = Column(String(100), default="新对话", comment="会话标题")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=datetime.now, onupdate=datetime.now, comment="更新时间")

    user = relationship("User", back_populates="chat_sessions")
    assessment_session = relationship("AssessmentSession", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session", cascade="all, delete-orphan")


# --- 聊天消息表 ---
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
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="创建时间")

    chat_session = relationship("ChatSession", back_populates="messages")
    session = relationship("AssessmentSession", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")

    __table_args__ = (Index("idx_chat_session_created", "chat_session_id", "created_at"),)


# 自动建表（首次启动时）
Base.metadata.create_all(bind=engine)

# 自动为已有表补充新增列
try:
    ensure_column("users", "avatar_url", "TEXT")
except Exception:
    pass
try:
    ensure_column("assessment_sessions", "current_stage", "VARCHAR(20)")
except Exception:
    pass
try:
    ensure_column("assessment_sessions", "submitted_stages", "JSONB")
except Exception:
    pass
