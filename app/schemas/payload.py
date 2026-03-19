from pydantic import BaseModel, Field
from typing import Optional

class AnswerSubmitRequest(BaseModel):
    user_id: int = Field(default=1, description="受试者ID")
    question_id: int = Field(default=101, description="题目ID")
    question_content: str = Field(default="当团队项目进度落后时，你通常的反应是？", description="题干")
    selected_option: str = Field(default="C. 独自加班把缺口补上", description="选项")
    time_spent: float = Field(default=1.5, description="实际作答耗时（秒）")
    avg_time: float = Field(default=8.0, description="基准平均作答时间（秒）")

class AnswerSubmitResponse(BaseModel):
    status: str = Field(description="normal: 正常 / anomaly: 异常")
    message: str = Field(description="后端处理结果说明")
    follow_up_question: Optional[str] = Field(default=None, description="AI追问文本")