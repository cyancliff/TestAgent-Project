"""
测评题目获取路由：阶段信息、阶段选题
"""

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.constants import STAGE_DIM_MAP, STAGE_QUESTION_COUNT, STAGE_NAMES
from app.models.assessment import Question
from app.models.user import User
from app.services.stage_service import StageService
from app.api.assessment.schemas import StageInfo

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
    """统一构建题目响应"""
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


@router.get("/stage-info", response_model=StageInfo)
async def get_stage_info(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前阶段信息"""
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
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前阶段下一题
    优先使用自适应策略，失败则回退到顺序选题
    """
    stage_service = StageService(db, session_id, current_user.id)
    current_stage = stage_service.get_current_stage()

    # 检查会话状态
    if stage_service.session.status == "completed":
        raise HTTPException(status_code=404, detail="测评已完成")

    # 获取本阶段已答编号
    answered_records = stage_service.get_answered_in_stage(current_stage)
    answered_exam_nos = [r.exam_no for r in answered_records]
    expected_count = STAGE_QUESTION_COUNT.get(current_stage, 10)

    # 查询本阶段未答题目
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
        raise HTTPException(status_code=404, detail=f"阶段 {current_stage} 题目不足（已答 {len(answered_records)}/{expected_count}）")

    # 总已答题数
    all_records = stage_service.get_all_answer_records()
    answered_total = len(all_records)
    total_questions = sum(STAGE_QUESTION_COUNT.values())

    # 自适应选题（仅当候选 > 1 时才有意义）
    next_question = None
    is_adaptive = False
    similarity = None
    ability_vector_exists = False

    if len(candidates) > 1:
        try:
            from app.services.question_selection import QuestionSelectionService

            answered_ids = (
                [q.id for q in db.query(Question).filter(
                    Question.exam_no.in_([r.exam_no for r in all_records])
                ).all()]
                if all_records else []
            )
            candidate_ids = {q.id for q in candidates}

            svc = QuestionSelectionService(db)
            selected = svc.select_next_question(
                current_user.id,
                session_id,
                answered_ids,
                module=current_stage if current_stage != "intro" else None,
            )

            # 验证选题在本阶段范围内
            if selected and selected.id in candidate_ids:
                next_question = selected
                is_adaptive = True

                # 计算相似度
                profile, _, _ = svc.get_user_ability_vector(
                    current_user.id, session_id,
                    current_stage if current_stage != "intro" else None,
                )
                if profile is not None and selected.feature_vector:
                    similarity = svc._cosine_similarity(profile, np.array(selected.feature_vector))
                    ability_vector_exists = True
        except Exception as e:
            print(f"[选题] 自适应异常: {e}")

    # 回退到顺序选题
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
