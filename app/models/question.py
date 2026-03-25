from sqlalchemy import Column, Integer, String, Text, JSON, Float, Boolean, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# 初始化数据库引擎
# 注意：connect_args={"check_same_thread": False} 是 SQLite 专属，用 MySQL 时会自动忽略
engine = create_engine(settings.DATABASE_URL,
                       connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Question(Base):
    __tablename__ = "atmr_questions"  # MySQL 中的真实表名

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    exam_no = Column(String(50), unique=True, index=True, comment="题目编号(如DX01)")
    dimension_id = Column(String(10), index=True, comment="维度ID(如1,4,5,6)")
    content = Column(Text, comment="题干内容")
    options = Column(JSON, comment="选项列表(JSON格式)")
    scores = Column(JSON, comment="选项对应的分值(JSON格式)")

    # --- AI 辩论慢车道专属字段 ---
    trait_label = Column(String(100), nullable=True, comment="特质标签(如:人品,坚持)")
    ai_analysis_prompt = Column(Text, nullable=True, comment="官方解析(发给大模型做参考)")

    # --- 算法判断专属字段 ---
    is_reverse = Column(Boolean, default=False, comment="是否反向计分")
    avg_time = Column(Float, default=8.0, comment="预估平均作答时间(秒)")


# 自动在数据库中创建这张表（如果表不存在的话）
Base.metadata.create_all(bind=engine)