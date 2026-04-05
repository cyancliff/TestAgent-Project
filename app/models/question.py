from sqlalchemy import Column, Integer, String, Text, JSON, Float, Boolean, create_engine, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL,
                       connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- 题目表 (静态题库) ---
class Question(Base):
    __tablename__ = "atmr_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    exam_no = Column(String(50), unique=True, index=True, comment="题目编号")
    dimension_id = Column(String(10), index=True, comment="维度ID")
    content = Column(Text, comment="题干内容")
    options = Column(JSON, comment="选项列表")
    scores = Column(JSON, comment="选项对应的分值")

    trait_label = Column(String(100), nullable=True, comment="特质标签")
    ai_analysis_prompt = Column(Text, nullable=True, comment="官方解析")

    is_reverse = Column(Boolean, default=False, comment="是否反向计分")
    avg_time = Column(Float, default=8.0, comment="预估平均作答时间(秒)")


# --- 用户表 ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, comment="用户名")
    password_hash = Column(String(128), comment="密码哈希")
    created_at = Column(DateTime, default=datetime.now, comment="注册时间")


# --- 测评会话表 ---
class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, comment="受试者ID")
    started_at = Column(DateTime, default=datetime.now, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="完成时间")
    status = Column(String(20), default='active', comment="状态: active/completed")
    report_content = Column(Text, nullable=True, comment="报告内容")
    report_file_path = Column(String(255), nullable=True, comment="报告文件路径")


# --- 作答记录表 (动态数据，本次新增！) ---
class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('assessment_sessions.id'), index=True, comment="所属会话ID")
    user_id = Column(Integer, index=True, comment="受试者唯一ID")
    exam_no = Column(String(50), index=True, comment="题目编号")
    selected_option = Column(Text, comment="选择的选项内容")
    score = Column(Float, comment="该题得分")
    time_spent = Column(Float, comment="实际作答耗时(秒)")

    # 存入 AI 的拦截结果与用户的解释
    is_anomaly = Column(Integer, default=0, comment="是否异常: 0正常, 1异常")
    ai_follow_up = Column(Text, nullable=True, comment="AI追问内容")
    user_explanation = Column(Text, nullable=True, comment="用户对异常的解释")

    created_at = Column(DateTime, default=datetime.now, comment="答题时间")


# 自动在数据库中创建表（如果新增了 AnswerRecord，它会自动建表）
Base.metadata.create_all(bind=engine)