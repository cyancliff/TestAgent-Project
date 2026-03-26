from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from datetime import datetime
from app.models.question import Base  # 确保引用同一个 Base

class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, index=True, comment="受试者唯一ID")
    exam_no = Column(String(50), index=True, comment="题目编号")
    selected_option = Column(Text, comment="选择的选项内容")
    score = Column(Float, comment="该题得分")
    time_spent = Column(Float, comment="实际作答耗时(秒)")

    # 存入 AI 的拦截结果，方便后续审计
    is_anomaly = Column(Integer, default=0, comment="是否异常: 0正常, 1异常")
    ai_follow_up = Column(Text, nullable=True, comment="AI追问内容")
    user_explanation = Column(Text, nullable=True, comment="用户对异常的解释")

    created_at = Column(DateTime, default=datetime.now, comment="答题时间")