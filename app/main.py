import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import assessment, auth, chat, rag
from app.core.config import settings
from app.core.limiter import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

# API 限流
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessment.router, prefix="/api/v1/assessment", tags=["实时测评系统"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["用户认证"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["心理专家对话"])
app.include_router(rag.router, prefix="/api/v1/rag", tags=["RAG 知识库"])

# 挂载静态文件（头像等上传文件）
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


@app.get("/")
def read_root():
    return {"message": "TestAgent 核心后端服务已启动！"}


@app.get("/health")
def health_check():
    """健康检查端点，用于 Docker/K8s 探针"""
    from app.core.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
    }
