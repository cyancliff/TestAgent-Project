import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import assessment, auth, chat, rag
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 允许跨域请求 (非常重要！)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有前端地址访问
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
