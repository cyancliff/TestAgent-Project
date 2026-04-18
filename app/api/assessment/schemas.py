"""
测评系统 Pydantic Schema 定义
"""

from pydantic import BaseModel, Field
from typing import Optional


class StartSessionRequest(BaseModel):
    pass  # user_id 从 JWT token 获取


class StageAnswerItem(BaseModel):
    """单题答案项"""
    exam_no: str
    selected_option: str
    time_spent: float
    user_explanation: Optional[str] = None


class SubmitStageRequest(BaseModel):
    """阶段提交请求"""
    session_id: int
    answers: list[StageAnswerItem]


class StageInfo(BaseModel):
    """阶段信息响应"""
    current_stage: str
    stage_name: str
    stage_display_name: str
    question_count: int
    answered_count: int
    can_submit: bool
    is_stage_complete: bool
    submitted_stages: list[str]


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


class RestartSessionRequest(BaseModel):
    session_id: int


# 兼容旧代码的别名
class UpdateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


BatchAnswerItem = StageAnswerItem
BatchSubmitRequest = SubmitStageRequest
AdaptiveAnswerItem = StageAnswerItem
