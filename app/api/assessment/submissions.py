"""
Assessment submission routes: draft save, answer checking, stage submission.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.assessment.schemas import (
    AnswerSubmitResponse,
    CheckAnswerRequest,
    ExplanationSubmitRequest,
    SaveAnswerRequest,
    SubmitStageRequest,
)
from app.api.assessment.sessions import (
    build_active_session_conflict_detail,
    create_assessment_session,
    get_latest_active_session,
)
from app.core.constants import MODULE_DIM_MAP, STAGE_DIM_MAP, STAGE_QUESTION_COUNT
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.assessment import AnswerRecord, AssessmentSession, Question
from app.models.user import User
from app.services.ai_detector import check_anomaly_and_generate_question
from app.services.stage_service import StageService

router = APIRouter()


def ensure_session_owner(db, session_id: int, user_id: int) -> AssessmentSession:
    """Ensure the session belongs to the current user."""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


def calculate_question_score(db_question: Question, selected_option: str) -> float:
    """Calculate the scored value for the selected option."""
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
    """Run anomaly detection without persisting anything."""
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


def validate_stage_answers(db, current_stage: str, answers) -> tuple[dict, dict]:
    """Validate a stage payload before anything is written to the database."""
    if not answers:
        raise HTTPException(status_code=400, detail="当前阶段还没有可提交的答案")

    answer_map = {}
    for item in answers:
        if item.exam_no in answer_map:
            raise HTTPException(status_code=400, detail=f"题目 {item.exam_no} 被重复提交")
        answer_map[item.exam_no] = item

    exam_nos = list(answer_map.keys())
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {q.exam_no: q for q in questions}

    invalid_nos = [no for no in exam_nos if no not in question_map]
    if invalid_nos:
        raise HTTPException(status_code=400, detail=f"存在无效题目编号: {invalid_nos}")

    target_dim = STAGE_DIM_MAP.get(current_stage)
    if not target_dim:
        raise HTTPException(status_code=500, detail=f"阶段 {current_stage} 配置缺失")

    wrong_stage_nos = [
        exam_no for exam_no, question in question_map.items() if question.dimension_id != target_dim
    ]
    if wrong_stage_nos:
        raise HTTPException(status_code=400, detail=f"存在不属于阶段 {current_stage} 的题目: {wrong_stage_nos}")

    required = STAGE_QUESTION_COUNT.get(current_stage, 10)
    answered = len(answer_map)
    if answered < required:
        raise HTTPException(
            status_code=400,
            detail=f"当前阶段还需作答 {required - answered} 题（已答 {answered}/{required}）",
        )
    if answered > required:
        raise HTTPException(
            status_code=400,
            detail=f"当前阶段只允许提交 {required} 题，收到 {answered} 题",
        )

    return answer_map, question_map


@router.post("/save-answer")
async def save_answer(
    payload: SaveAnswerRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Draft answers are no longer persisted question-by-question.
    Keep the endpoint as a harmless no-op for backward compatibility.
    """
    session = ensure_session_owner(db, payload.session_id, current_user.id)
    if session.status == "completed":
        raise HTTPException(status_code=400, detail="该测评已完成")
    return {"status": "success", "persisted": False}


@router.post("/check-answer", response_model=AnswerSubmitResponse)
async def check_answer(
    payload: CheckAnswerRequest,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check an answer without persisting it."""
    del current_user

    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    try:
        current_score, detection_result = await analyze_answer(
            db_question, payload.selected_option, payload.time_spent, recent_answers=[]
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"答案检测失败: {exc}") from exc

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
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist an explanation only for already-saved anomaly answers."""
    record = (
        db.query(AnswerRecord)
        .filter(
            AnswerRecord.session_id == payload.session_id,
            AnswerRecord.user_id == current_user.id,
            AnswerRecord.exam_no == payload.exam_no,
            AnswerRecord.is_anomaly == 1,
        )
        .order_by(AnswerRecord.created_at.desc())
        .first()
    )

    if record:
        record.user_explanation = payload.text
        db.commit()
        return {"status": "success", "message": "解释已入库"}

    raise HTTPException(status_code=404, detail="找不到对应的异常记录")


@router.post("/submit-stage")
async def submit_stage(
    payload: SubmitStageRequest,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Persist a full stage at once.
    Empty drafts are kept in memory only; the first DB write happens here.
    """
    from app.api.assessment.streaming import generate_report_in_background

    stage_service = None
    current_stage = "intro"

    if payload.session_id:
        stage_service = StageService(db, payload.session_id, current_user.id)
        current_stage = stage_service.get_current_stage()
        submitted = stage_service.get_submitted_stages()
        if current_stage in submitted:
            raise HTTPException(status_code=400, detail=f"阶段 {current_stage} 已提交，不能重复提交")
    else:
        existing_active = get_latest_active_session(db, current_user.id)
        if existing_active:
            raise HTTPException(status_code=409, detail=build_active_session_conflict_detail(existing_active))

    answer_map, question_map = validate_stage_answers(db, current_stage, payload.answers)

    if stage_service is None:
        session = create_assessment_session(db, current_user.id)
        stage_service = StageService(db, session.id, current_user.id)
    else:
        session = stage_service.session

    for exam_no, item in answer_map.items():
        db_question = question_map[exam_no]
        score = item.score if item.score is not None else calculate_question_score(db_question, item.selected_option)

        existing = db.query(AnswerRecord).filter(
            AnswerRecord.session_id == session.id,
            AnswerRecord.user_id == current_user.id,
            AnswerRecord.exam_no == exam_no,
        ).first()

        if existing:
            existing.selected_option = item.selected_option
            existing.time_spent = item.time_spent
            existing.score = score
            existing.is_anomaly = item.is_anomaly
            existing.ai_follow_up = item.ai_follow_up
            existing.user_explanation = item.user_explanation if item.user_explanation is not None else None
        else:
            db.add(
                AnswerRecord(
                    session_id=session.id,
                    user_id=current_user.id,
                    exam_no=exam_no,
                    selected_option=item.selected_option,
                    score=score,
                    time_spent=item.time_spent,
                    is_anomaly=item.is_anomaly,
                    ai_follow_up=item.ai_follow_up,
                    user_explanation=item.user_explanation if item.user_explanation is not None else None,
                )
            )

    db.commit()

    next_stage = stage_service.advance_to_next_stage()

    if current_stage in MODULE_DIM_MAP:
        from app.api.assessment.streaming import trigger_module_debate

        background_tasks.add_task(trigger_module_debate, session.id, current_user.id, current_stage)

    all_completed = next_stage is None
    if all_completed:
        session.status = "completed"
        session.finished_at = datetime.now(timezone.utc)
        db.commit()
        background_tasks.add_task(generate_report_in_background, session.id, current_user.id)

    return {
        "status": "success",
        "message": f"阶段 {current_stage} 已提交",
        "session_id": session.id,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "all_completed": all_completed,
    }
