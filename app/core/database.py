"""
数据库连接与会话管理
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base

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


def get_db():
    """FastAPI 依赖：获取数据库会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_column(table: str, column: str, column_type: str):
    """检查并添加缺失的数据库列（用于平滑迁移）"""
    inspector = inspect(engine)
    if inspector.has_table(table) and column not in {c["name"] for c in inspector.get_columns(table)}:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))
