"""
数据库连接与会话管理
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from app.core.config import settings

is_sqlite = settings.DATABASE_URL.startswith("sqlite:")
engine_kwargs = {
    "pool_pre_ping": True,
}

if is_sqlite:
    sqlite_url = settings.DATABASE_URL.removeprefix("sqlite:///")
    if sqlite_url and sqlite_url != ":memory:":
        sqlite_dir = os.path.dirname(sqlite_url)
        if sqlite_dir:
            os.makedirs(sqlite_dir, exist_ok=True)
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 40,
        "pool_recycle": 3600,
    })

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：获取数据库会话，请求结束自动关闭"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
