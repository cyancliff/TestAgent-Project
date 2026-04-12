"""
测评系统 Pydantic Schema 定义
从 assessment.py 中提取，供各路由模块复用。
"""

from pydantic import BaseModel, Field
from typing import Optional


class StartSessionRequest(BaseModel):
    pass  # user_id 从 JWT token 获取


class SubmitModuleRequest(BaseModel):
    session_id: int
    module: str  # A/T/M/R


class SaveAnswerRequest(BaseModel):
    session_id: int
    exam_no: str
    selected_option: str
    time_spent: float
    score: float
    is_anomaly: int = 0
    ai_follow_up: Optional[str] = None
    user_explanation: Optional[str] = None


class AnswerSubmitRequest(BaseModel):
    session_id: int
    exam_no: str
    selected_option: str
    time_spent: float


class AnswerSubmitResponse(BaseModel):
    status: str
    message: str
    score: float
    follow_up_question: Optional[str] = None
    risk_score: Optional[int] = None
    risk_reasons: list[str] = Field(default_factory=list)


class ExplanationSubmitRequest(BaseModel):
    session_id: int
    exam_no: str
    text: str


class CheckAnswerRequest(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float


class BatchAnswerItem(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float
    user_explanation: Optional[str] = None


class BatchSubmitRequest(BaseModel):
    session_id: int
    answers: list[BatchAnswerItem]


class AdaptiveAnswerItem(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float
    score: float
    status: str
    user_explanation: Optional[str] = None


class AdaptiveQuestionRequest(BaseModel):
    """智能选题请求"""
    session_id: int
    module: Optional[str] = None  # 模块类型: A/T/M/R
    answers: list[AdaptiveAnswerItem] = Field(default_factory=list)
