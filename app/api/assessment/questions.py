"""
Assessment question routes: stage info and adaptive next-question selection.
"""

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.assessment.schemas import AdaptiveQuestionRequest, StageInfo
from app.api.assessment.submissions import calculate_question_score
from app.core.constants import STAGE_DIM_MAP, STAGE_NAMES, STAGE_QUESTION_COUNT
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.assessment import Question
from app.models.user import User
from app.services.question_selection import QuestionSelectionService
from app.services.stage_service import StageService

router = APIRouter()


def _build_question_response(
    question: Question,
    total_questions: int,
    answered_count: int,
    current_stage: str,
    is_adaptive: bool,
    similarity: float | None = None,
    ability_vector_exists: bool = False,
) -> dict:
    return {
        "examNo": question.exam_no,
        "exam": question.content,
        "options": question.options,
        "total": total_questions,
        "remaining": max(total_questions - answered_count - 1, 0),
        "is_adaptive": is_adaptive,
        "current_stage": current_stage,
        "stage_display_name": STAGE_NAMES.get(current_stage, current_stage),
        "selected_dimension": question.dimension_id,
        "selected_trait": question.trait_label,
        "question_stats": {
            "difficulty": float(question.difficulty or 0.5),
            "discrimination": float(question.discrimination or 0.7),
            "has_feature_vector": question.feature_vector is not None,
            "similarity": similarity,
            "ability_vector_exists": ability_vector_exists,
        },
    }


def _record_exam_no(record) -> str | None:
    if isinstance(record, dict):
        return record.get("exam_no")
    return getattr(record, "exam_no", None)


def _build_transient_records(db: Session, transient_answers: list) -> list[dict]:
    if not transient_answers:
        return []

    exam_nos = [item.exam_no for item in transient_answers]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {question.exam_no: question for question in questions}

    transient_records = []
    for item in transient_answers:
        question = question_map.get(item.exam_no)
        if not question:
            continue
        transient_records.append(
            {
                "exam_no": item.exam_no,
                "selected_option": item.selected_option,
                "time_spent": item.time_spent,
                "score": item.score
                if item.score is not None
                else calculate_question_score(question, item.selected_option),
                "is_anomaly": item.is_anomaly,
                "ai_follow_up": item.ai_follow_up,
                "user_explanation": item.user_explanation,
            }
        )
    return transient_records


def _merge_records(persisted_records: list, transient_records: list[dict]) -> list:
    merged = {}
    for record in persisted_records:
        exam_no = _record_exam_no(record)
        if exam_no:
            merged[exam_no] = record
    for record in transient_records:
        exam_no = _record_exam_no(record)
        if exam_no:
            merged[exam_no] = record
    return list(merged.values())


def _filter_records_by_stage(db: Session, records: list, stage: str) -> list:
    if not records:
        return []

    target_dim = STAGE_DIM_MAP.get(stage)
    if not target_dim:
        return []

    exam_nos = [_record_exam_no(record) for record in records if _record_exam_no(record)]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all() if exam_nos else []
    question_map = {question.exam_no: question for question in questions}
    return [
        record
        for record in records
        if question_map.get(_record_exam_no(record))
        and question_map[_record_exam_no(record)].dimension_id == target_dim
    ]


@router.get("/stage-info", response_model=StageInfo)
async def get_stage_info(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return persisted stage info for an existing session."""
    stage_service = StageService(db, session_id, current_user.id)
    current_stage = stage_service.get_current_stage()

    return StageInfo(
        current_stage=current_stage,
        stage_name=current_stage,
        stage_display_name=STAGE_NAMES.get(current_stage, current_stage),
        question_count=stage_service.get_stage_question_count(current_stage),
        answered_count=stage_service.get_stage_answered_count(current_stage),
        can_submit=stage_service.is_stage_complete(current_stage),
        is_stage_complete=stage_service.is_stage_complete(current_stage),
        submitted_stages=stage_service.get_submitted_stages(),
    )


@router.post("/adaptive-question")
async def get_adaptive_question(
    payload: AdaptiveQuestionRequest | None = Body(default=None),
    session_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Select the next question for the current stage.
    Unsaved answers from the current stage can be supplied in the request body.
    """
    request_data = payload or AdaptiveQuestionRequest()
    resolved_session_id = request_data.session_id or session_id
    transient_records = _build_transient_records(db, request_data.transient_answers)

    stage_service = None
    current_stage = request_data.current_stage or "intro"
    persisted_records = []

    if resolved_session_id:
        stage_service = StageService(db, resolved_session_id, current_user.id)
        current_stage = stage_service.get_current_stage()
        if stage_service.session.status == "completed":
            raise HTTPException(status_code=404, detail="测评已完成")
        persisted_records = stage_service.get_all_answer_records()

    combined_records = _merge_records(persisted_records, transient_records)
    answered_records = _filter_records_by_stage(db, combined_records, current_stage)
    answered_exam_nos = [_record_exam_no(record) for record in answered_records if _record_exam_no(record)]

    expected_count = STAGE_QUESTION_COUNT.get(current_stage, 10)
    dim_id = STAGE_DIM_MAP.get(current_stage)
    if not dim_id:
        raise HTTPException(status_code=500, detail=f"阶段 {current_stage} 配置缺失")

    candidates = (
        db.query(Question)
        .filter(Question.dimension_id == dim_id)
        .filter(Question.exam_no.notin_(answered_exam_nos) if answered_exam_nos else True)
        .order_by(Question.exam_no)
        .all()
    )

    if not candidates:
        if len(answered_records) >= expected_count:
            raise HTTPException(status_code=400, detail=f"阶段 {current_stage} 题目已全部作答，请提交后进入下一阶段")
        raise HTTPException(
            status_code=404,
            detail=f"阶段 {current_stage} 题目不足（已答 {len(answered_records)}/{expected_count}）",
        )

    answered_total = len(combined_records)
    total_questions = sum(STAGE_QUESTION_COUNT.values())

    next_question = None
    is_adaptive = False
    similarity = None
    ability_vector_exists = False

    if len(candidates) > 1:
        try:
            combined_exam_nos = [_record_exam_no(record) for record in combined_records if _record_exam_no(record)]
            answered_ids = (
                [question.id for question in db.query(Question).filter(Question.exam_no.in_(combined_exam_nos)).all()]
                if combined_exam_nos
                else []
            )
            candidate_ids = {question.id for question in candidates}

            selector = QuestionSelectionService(db)
            selected = selector.select_next_question(
                current_user.id,
                resolved_session_id or 0,
                answered_ids,
                module=current_stage if current_stage != "intro" else None,
                transient_records=combined_records,
            )

            if selected and selected.id in candidate_ids:
                next_question = selected
                is_adaptive = True

                profile, _, _ = selector.get_user_ability_vector(
                    current_user.id,
                    resolved_session_id or 0,
                    current_stage if current_stage != "intro" else None,
                    transient_records=combined_records,
                )
                if profile is not None and selected.feature_vector:
                    similarity = selector._cosine_similarity(profile, np.array(selected.feature_vector))
                    ability_vector_exists = True
        except Exception as exc:
            print(f"[选题] 自适应异常: {exc}")

    if next_question is None:
        next_question = candidates[0]

    return _build_question_response(
        question=next_question,
        total_questions=total_questions,
        answered_count=answered_total,
        current_stage=current_stage,
        is_adaptive=is_adaptive,
        similarity=similarity,
        ability_vector_exists=ability_vector_exists,
    )
