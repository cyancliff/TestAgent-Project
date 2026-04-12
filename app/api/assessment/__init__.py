"""
测评系统 API 路由聚合

将各子模块的路由器组合为统一的 router，保持与旧版
`from app.api.assessment import router` 的完全兼容。
"""

from fastapi import APIRouter

from app.api.assessment.sessions import router as sessions_router
from app.api.assessment.questions import router as questions_router
from app.api.assessment.submissions import router as submissions_router
from app.api.assessment.streaming import router as streaming_router

router = APIRouter()

router.include_router(sessions_router)
router.include_router(questions_router)
router.include_router(submissions_router)
router.include_router(streaming_router)
