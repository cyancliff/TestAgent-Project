from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.models.question import SessionLocal, Question, AnswerRecord
from app.services.ai_detector import check_anomaly_and_generate_question

router = APIRouter()


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


class ExplanationSubmitRequest(BaseModel):
    user_id: int
    exam_no: str
    text: str


# --- 接口 1：获取题目 ---
# --- 接口 1：获取题目 (10题极速测试版) ---
TEST_LIMIT = 10  # 极速测试版只取前 10 题


@router.get("/question/{index}")
async def get_question(index: int, db: Session = Depends(get_db)):
    # 核心拦截：如果前端请求的题号达到了 10，直接告诉它测试结束了！
    if index >= TEST_LIMIT:
        raise HTTPException(status_code=404, detail="10题极速测试已完成")

    db_question = db.query(Question).offset(index).limit(1).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题库已做完")

    return {
        "examNo": db_question.exam_no,
        "exam": db_question.content,
        "options": db_question.options,
        "total": TEST_LIMIT  # 动态告诉前端，总进度条只有 10
    }

# --- 接口 2：提交答案 (含自动算分与持久化) ---
@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(payload: AnswerSubmitRequest, db: Session = Depends(get_db)):
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 1. 智能计算本题得分
    current_score = 0.0
    try:
        # 找到用户选的选项在列表中的索引，然后去 scores 列表里拿对应的分数
        opt_index = db_question.options.index(payload.selected_option)
        current_score = float(db_question.scores[opt_index])
    except Exception as e:
        print(f"算分出错: {e}")

    # 2. AI 瞬间拦截逻辑
    detection_result = await check_anomaly_and_generate_question(
        time_spent=payload.time_spent,
        avg_time=db_question.avg_time,
        question_content=db_question.content,
        selected_option=payload.selected_option
    )

    # 3. 写入数据库！
    is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
    new_record = AnswerRecord(
        user_id=payload.user_id,
        exam_no=payload.exam_no,
        selected_option=payload.selected_option,
        score=current_score,
        time_spent=payload.time_spent,
        is_anomaly=is_anomaly_flag,
        ai_follow_up=detection_result.get("follow_up")
    )
    db.add(new_record)
    db.commit()

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="记录已成功存入数据库",
        score=current_score,
        follow_up_question=detection_result.get("follow_up")
    )


# --- 接口 3：提交补充解释 (新增！) ---
@router.post("/submit_explanation")
async def submit_explanation(payload: ExplanationSubmitRequest, db: Session = Depends(get_db)):
    # 找到刚才那条被拦截的异常记录
    record = db.query(AnswerRecord).filter(
        AnswerRecord.user_id == payload.user_id,
        AnswerRecord.exam_no == payload.exam_no,
        AnswerRecord.is_anomaly == 1
    ).order_by(AnswerRecord.created_at.desc()).first()

    if record:
        record.user_explanation = payload.text
        db.commit()
        return {"status": "success", "message": "解释已入库"}

    raise HTTPException(status_code=404, detail="找不到对应的异常记录")