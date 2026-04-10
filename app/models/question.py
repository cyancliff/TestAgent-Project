from sqlalchemy import Column, Integer, String, Text, Float, Boolean, create_engine, DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()


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
    answers = relationship("AnswerRecord", back_populates="question", foreign_keys="AnswerRecord.exam_no", primaryjoin="Question.exam_no == foreign(AnswerRecord.exam_no)")


# --- 用户表 ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, comment="用户名")
    password_hash = Column(String(255), comment="密码哈希")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="注册时间")

    # 关系
    sessions = relationship("AssessmentSession", back_populates="user")
    answers = relationship("AnswerRecord", back_populates="user")
    debate_results = relationship("ModuleDebateResult", back_populates="user")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


# --- 测评会话表 ---
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True, comment="受试者ID")
    started_at = Column(DateTime(timezone=True), default=datetime.now, comment="开始时间")
    finished_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    status = Column(String(20), default='active', comment="状态: active/completed")
    report_content = Column(Text, nullable=True, comment="报告内容")
    report_file_path = Column(String(255), nullable=True, comment="报告文件路径")

    # 关系
    user = relationship("User", back_populates="sessions")
    answers = relationship("AnswerRecord", back_populates="session")
    debate_results = relationship("ModuleDebateResult", back_populates="session")
    chat_messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_session_user_started', 'user_id', started_at.desc()),
    )


# --- 作答记录表 ---
class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('assessment_sessions.id'), index=True, comment="所属会话ID")
    user_id = Column(Integer, ForeignKey('users.id'), index=True, comment="受试者唯一ID")
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
    question = relationship("Question", back_populates="answers", foreign_keys=[exam_no], primaryjoin="AnswerRecord.exam_no == Question.exam_no")

    __table_args__ = (
        Index('idx_answer_session_user', 'session_id', 'user_id'),
        Index('idx_answer_session_user_exam', 'session_id', 'user_id', 'exam_no'),
    )


# --- 模块辩论结果表 ---
class ModuleDebateResult(Base):
    __tablename__ = "module_debate_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('assessment_sessions.id'), index=True, comment="所属会话ID")
    user_id = Column(Integer, ForeignKey('users.id'), index=True, comment="用户ID")
    module = Column(String(10), index=True, comment="模块类型: A/T/M/R")
    result_content = Column(Text, comment="辩论结果内容")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="创建时间")

    # 关系
    session = relationship("AssessmentSession", back_populates="debate_results")
    user = relationship("User", back_populates="debate_results")

    __table_args__ = (
        Index('idx_debate_session_module', 'session_id', 'module'),
    )


# --- 聊天消息表 ---
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('assessment_sessions.id'), index=True, nullable=False, comment="所属会话ID")
    user_id = Column(Integer, ForeignKey('users.id'), index=True, nullable=False, comment="用户ID")
    role = Column(String(20), nullable=False, comment="角色: system/user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime(timezone=True), default=datetime.now, comment="创建时间")

    session = relationship("AssessmentSession", back_populates="chat_messages")
    user = relationship("User", back_populates="chat_messages")

    __table_args__ = (
        Index('idx_chat_session_created', 'session_id', 'created_at'),
    )


# 自动在数据库中创建表
Base.metadata.create_all(bind=engine)
