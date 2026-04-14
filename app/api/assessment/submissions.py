"""
测评作答提交路由：草稿保存、答案预检、阶段提交、异常解释
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.constants import MODULE_DIM_MAP
from app.models.assessment import AnswerRecord, AssessmentSession, Question
from app.models.user import User
from app.services.ai_detector import check_anomaly_and_generate_question
from app.services.stage_service import StageService
from app.api.assessment.schemas import (
    SaveAnswerRequest, AnswerSubmitRequest, AnswerSubmitResponse,
    ExplanationSubmitRequest, CheckAnswerRequest, SubmitStageRequest,
)

router = APIRouter()


def ensure_session_owner(db, session_id: int, user_id: int) -> AssessmentSession:
    """校验会话属于当前用户"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


def calculate_question_score(db_question: Question, selected_option: str) -> float:
    """计算题目分数（支持反向计分）"""
    opt_index = db_question.options.index(selected_option)
    raw_score = float(db_question.scores[opt_index])
    if db_question.is_reverse:
        return 6.0 - raw_score
    return raw_score


async def analyze_answer(
    db_question: Question,
    selected_option: str,
    time_spent: float,
    recent_answers: Optional[list[dict]] = None,
) -> tuple[float, dict]:
    """计算分数并执行异常检测"""
    score = calculate_question_score(db_question, selected_option)
    detection_result = await check_anomaly_and_generate_question(
        time_spent=time_spent,
        avg_time=float(db_question.avg_time or 8.0),
        question_content=db_question.content,
        selected_option=selected_option,
        recent_answers=recent_answers or [],
        available_options=db_question.options,
    )
    return score, detection_result


@router.post("/save-answer")
async def save_answer(
    payload: SaveAnswerRequest,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """实时保存单题答案（草稿）"""
    session = ensure_session_owner(db, payload.session_id, current_user.id)
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="该测评已完成")

    existing = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
        AnswerRecord.exam_no == payload.exam_no,
    ).first()

    if existing:
        existing.selected_option = payload.selected_option
        existing.time_spent = payload.time_spent
        existing.score = payload.score
        existing.is_anomaly = payload.is_anomaly
        existing.ai_follow_up = payload.ai_follow_up
        existing.user_explanation = payload.user_explanation
    else:
        db.add(AnswerRecord(
            session_id=payload.session_id,
            user_id=current_user.id,
            exam_no=payload.exam_no,
            selected_option=payload.selected_option,
            score=payload.score,
            time_spent=payload.time_spent,
            is_anomaly=payload.is_anomaly,
            ai_follow_up=payload.ai_follow_up,
            user_explanation=payload.user_explanation,
        ))
    db.commit()
    return {"status": "success"}


@router.post("/check-answer", response_model=AnswerSubmitResponse)
async def check_answer(
    payload: CheckAnswerRequest,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预检答案（不入库），用于前端实时反馈"""
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    try:
        current_score, detection_result = await analyze_answer(
            db_question, payload.selected_option, payload.time_spent, recent_answers=[],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"答案检测失败: {e}")

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="检测完成，尚未正式提交",
        score=current_score,
        follow_up_question=detection_result.get("follow_up"),
        risk_score=detection_result.get("risk_score"),
        risk_reasons=detection_result.get("reasons", []),
    )


@router.post("/submit_explanation")
async def submit_explanation(
    payload: ExplanationSubmitRequest,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交异常作答的补充解释"""
    record = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
        AnswerRecord.exam_no == payload.exam_no,
        AnswerRecord.is_anomaly == 1,
    ).order_by(AnswerRecord.created_at.desc()).first()

    if record:
        record.user_explanation = payload.text
        db.commit()
        return {"status": "success", "message": "解释已入库"}

    raise HTTPException(status_code=404, detail="找不到对应的异常记录")


@router.post("/submit-stage")
async def submit_stage(
    payload: SubmitStageRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交当前阶段所有答案
    1. 校验当前阶段是否满题
    2. upsert 作答记录
    3. 后台调用模块辩论（不阻塞）
    4. 推进到下一阶段
    5. 全部完成后触发最终报告生成
    """
    from app.api.assessment.streaming import generate_report_in_background

    stage_service = StageService(db, payload.session_id, current_user.id)
    current_stage = stage_service.get_current_stage()

    # 校验：检查是否已提交
    submitted = stage_service.get_submitted_stages()
    if current_stage in submitted:
        raise HTTPException(status_code=400, detail=f"阶段 {current_stage} 已提交，不能重复提交")

    # 校验：满题检查
    if not stage_service.is_stage_complete(current_stage):
        answered = stage_service.get_stage_answered_count(current_stage)
        required = stage_service.get_stage_question_count(current_stage)
        raise HTTPException(
            status_code=400,
            detail=f"当前阶段还需作答 {required - answered} 题（已答 {answered}/{required}）",
        )

    # Upsert 作答记录
    answer_map = {item.exam_no: item for item in payload.answers}
    exam_nos = list(answer_map.keys())
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {q.exam_no: q for q in questions}

    invalid_nos = [no for no in exam_nos if no not in question_map]
    if invalid_nos:
        raise HTTPException(status_code=400, detail=f"存在无效题目编号: {invalid_nos}")

    # Upsert 答案（简单写入，不重新分析）
    for exam_no, item in answer_map.items():
        db_question = question_map[exam_no]
        score = calculate_question_score(db_question, item.selected_option)

        existing = db.query(AnswerRecord).filter(
            AnswerRecord.session_id == payload.session_id,
            AnswerRecord.user_id == current_user.id,
            AnswerRecord.exam_no == exam_no,
        ).first()

        if existing:
            existing.selected_option = item.selected_option
            existing.time_spent = item.time_spent
            existing.score = score
            if item.user_explanation:
                existing.user_explanation = item.user_explanation
        else:
            db.add(AnswerRecord(
                session_id=payload.session_id,
                user_id=current_user.id,
                exam_no=exam_no,
                selected_option=item.selected_option,
                score=score,
                time_spent=item.time_spent,
                user_explanation=item.user_explanation if item.user_explanation else None,
            ))

    db.commit()

    # 推进到下一阶段
    next_stage = stage_service.advance_to_next_stage()

    # 后台触发当前模块的辩论（不阻塞响应）
    if current_stage in MODULE_DIM_MAP:
        from app.api.assessment.streaming import trigger_module_debate
        background_tasks.add_task(
            trigger_module_debate, payload.session_id, current_user.id, current_stage,
        )

    # 全部阶段完成，标记并生成最终报告
    all_completed = next_stage is None
    if all_completed:
        session = stage_service.session
        session.status = "completed"
        from datetime import datetime
        session.finished_at = datetime.now()
        db.commit()

        background_tasks.add_task(
            generate_report_in_background, payload.session_id, current_user.id,
        )

    return {
        "status": "success",
        "message": f"阶段 {current_stage} 已提交",
        "current_stage": current_stage,
        "next_stage": next_stage,
        "all_completed": all_completed,
    }
