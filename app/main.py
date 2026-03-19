from fastapi import FastAPI
from app.api import assessment
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

# 注册 API 路由
app.include_router(assessment.router, prefix="/api/v1/assessment", tags=["实时测评系统"])

@app.get("/")
def read_root():
    return {"message": "TestAgent 核心后端服务已启动！快去 /docs 看看吧！"}