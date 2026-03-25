from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List

from app.models.question import SessionLocal, Question
from app.services.ai_detector import check_anomaly_and_generate_question

router = APIRouter()


# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Schema 定义 ---
class AnswerSubmitRequest(BaseModel):
    user_id: int
    exam_no: str
    selected_option: str
    time_spent: float


class AnswerSubmitResponse(BaseModel):
    status: str
    message: str
    score: float
    follow_up_question: Optional[str] = None


# --- 接口 1：获取题目 (新增加) ---
@router.get("/question/{index}")
async def get_question(index: int, db: Session = Depends(get_db)):
    # 从数据库中按顺序取题
    db_question = db.query(Question).offset(index).limit(1).first()

    if not db_question:
        raise HTTPException(status_code=404, detail="题库已做完")

    return {
        "examNo": db_question.exam_no,
        "exam": db_question.content,
        "options": db_question.options,  # 这里会自动解析 JSON
        "total": 102
    }


# --- 接口 2：提交答案 (逻辑升级) ---
@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(payload: AnswerSubmitRequest, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # AI 瞬间拦截逻辑
    detection_result = await check_anomaly_and_generate_question(
        time_spent=payload.time_spent,
        avg_time=db_question.avg_time,
        question_content=db_question.content,
        selected_option=payload.selected_option
    )

    # 简单的计分逻辑 (后期可根据 scores 字段细化)
    current_score = 1.0

    if detection_result["status"] == "anomaly":
        return AnswerSubmitResponse(
            status="anomaly",
            message="检测到作答异常",
            score=current_score,
            follow_up_question=detection_result["follow_up"]
        )

    return AnswerSubmitResponse(status="normal", message="记录成功", score=current_score)