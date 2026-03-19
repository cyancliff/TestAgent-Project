from fastapi import APIRouter
from app.schemas.payload import AnswerSubmitRequest, AnswerSubmitResponse
from app.services.ai_detector import check_anomaly_and_generate_question

router = APIRouter()


@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(payload: AnswerSubmitRequest):
    # 1. 业务逻辑交由 service 层处理
    detection_result = await check_anomaly_and_generate_question(
        time_spent=payload.time_spent,
        avg_time=payload.avg_time,
        question_content=payload.question_content,
        selected_option=payload.selected_option
    )

    # 2. 返回结果给前端
    if detection_result["status"] == "anomaly":
        return AnswerSubmitResponse(
            status="anomaly",
            message="检测到作答异常，触发 AI 追问",
            follow_up_question=detection_result["follow_up"]
        )

    return AnswerSubmitResponse(
        status="normal",
        message="记录成功，准备进入下一题",
        follow_up_question=None
    )
