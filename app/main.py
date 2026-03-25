from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import assessment
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 允许跨域请求 (非常重要！)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有前端地址访问
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assessment.router, prefix="/api/v1/assessment", tags=["实时测评系统"])

@app.get("/")
def read_root():
    return {"message": "TestAgent 核心后端服务已启动！"}