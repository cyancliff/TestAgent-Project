"""
测评题目获取路由：顺序选题、智能自适应选题
"""

import numpy as np
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.constants import (
    TOTAL_QUESTIONS, FIXED_QUESTIONS, QUESTIONS_PER_MODULE, MODULES, MODULE_DIM_MAP,
)
from app.models.question import Question, AnswerRecord, AssessmentSession, User
from app.services.question_selection import QuestionSelectionService
from app.api.assessment.schemas import AdaptiveQuestionRequest, AdaptiveAnswerItem

router = APIRouter()


def get_current_module_and_stage(answered_count: int):
    """根据已答题数确定当前阶段和模块"""
    if answered_count < FIXED_QUESTIONS:
        return None, "fixed"

    module_index = (answered_count - FIXED_QUESTIONS) // QUESTIONS_PER_MODULE
    if module_index < len(MODULES):
        return MODULES[module_index], "module"

    return MODULES[-1], "module"


def build_transient_answer_context(db: Session, answers: list[AdaptiveAnswerItem]) -> dict:
    """将前端本地答案快照归一化为自适应选题可用的上下文"""
    if not answers:
        return {
            "answered_question_nos": [],
            "answered_ids": [],
            "answered_count": 0,
            "question_map": {},
            "transient_records": [],
        }

    answered_question_nos = [item.exam_no for item in answers]
    if len(answered_question_nos) != len(set(answered_question_nos)):
        raise HTTPException(status_code=400, detail="自适应选题请求中存在重复题目")

    questions = db.query(Question).filter(Question.exam_no.in_(answered_question_nos)).all()
    question_map = {q.exam_no: q for q in questions}
    if len(question_map) != len(answered_question_nos):
        raise HTTPException(status_code=400, detail="自适应选题请求中存在无效题目编号")

    transient_records = []
    answered_ids = []
    for item in answers:
        question = question_map[item.exam_no]
        answered_ids.append(question.id)
        transient_records.append({
            "exam_no": item.exam_no,
            "selected_option": item.selected_option,
            "score": item.score,
            "time_spent": item.time_spent,
            "is_anomaly": item.status == "anomaly",
            "user_explanation": item.user_explanation,
        })

    return {
        "answered_question_nos": answered_question_nos,
        "answered_ids": answered_ids,
        "answered_count": len(answered_question_nos),
        "question_map": question_map,
        "transient_records": transient_records,
    }


@router.get("/question/{index}")
async def get_question(index: int, db: Session = Depends(get_db)):
    """顺序获取题目（旧版兼容）"""
    if index >= TOTAL_QUESTIONS:
        raise HTTPException(status_code=404, detail="测评已完成")

    db_question = db.query(Question).offset(index).limit(1).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题库已做完")

    return {
        "examNo": db_question.exam_no,
        "exam": db_question.content,
        "options": db_question.options,
        "total": TOTAL_QUESTIONS,
    }


@router.post("/adaptive-question")
async def get_adaptive_question(
    payload: AdaptiveQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    智能选题接口
    基于用户能力向量和题目特征向量，选择最合适的下一题
    """
    use_local_answers = bool(payload.answers)
    fallback_index = len(payload.answers)
    try:
        if use_local_answers:
            transient_context = build_transient_answer_context(db, payload.answers)
            answered_question_nos = transient_context["answered_question_nos"]
            answered_count = transient_context["answered_count"]
            answered_q_map = transient_context["question_map"]
            answered_ids = transient_context["answered_ids"]
            transient_records = transient_context["transient_records"]
        else:
            answered_records = db.query(AnswerRecord).filter(
                AnswerRecord.session_id == payload.session_id,
                AnswerRecord.user_id == current_user.id,
            ).all()
            answered_question_nos = [record.exam_no for record in answered_records]
            answered_count = len(answered_question_nos)
            answered_questions = db.query(Question).filter(
                Question.exam_no.in_(answered_question_nos)
            ).all() if answered_question_nos else []
            answered_q_map = {q.exam_no: q for q in answered_questions}
            answered_ids = [q.id for q in answered_questions]
            transient_records = None
            fallback_index = answered_count

        if answered_count >= TOTAL_QUESTIONS:
            raise HTTPException(status_code=404, detail="测评已完成")

        current_module, stage = get_current_module_and_stage(answered_count)
        service = QuestionSelectionService(db)

        if current_module and stage == "module":
            target_dimension = MODULE_DIM_MAP.get(current_module)
            module_answered_count = 0
            module_questions = []
            if target_dimension:
                for exam_no in answered_question_nos:
                    q = answered_q_map.get(exam_no)
                    if q and q.dimension_id == target_dimension:
                        module_answered_count += 1
                        module_questions.append(q.exam_no)
            print(f"[DEBUG] 总已答题数: {answered_count}, 当前模块: {current_module}, target_dimension: {target_dimension}")
            print(f"[DEBUG] 当前模块已答题: {module_questions}")
            print(f"[DEBUG] 当前模块已答: {module_answered_count}/{QUESTIONS_PER_MODULE}题")

            if module_answered_count >= QUESTIONS_PER_MODULE:
                current_module_index = MODULES.index(current_module) if current_module in MODULES else -1
                if current_module_index < len(MODULES) - 1:
                    current_module = MODULES[current_module_index + 1]
                    print(f"模块已答满10题，切换到下一个模块: {current_module}")
                else:
                    raise HTTPException(status_code=404, detail="所有模块已完成")

        next_question = None
        if stage == "fixed":
            fixed_query = db.query(Question).filter(Question.dimension_id == '1')
            if answered_ids:
                fixed_query = fixed_query.filter(Question.id.notin_(answered_ids))
            fixed_candidates = fixed_query.all()
            if fixed_candidates:
                next_question = fixed_candidates[0]
        else:
            next_question = service.select_next_question(
                current_user.id,
                payload.session_id,
                answered_ids,
                module=current_module,
                transient_records=transient_records,
            )

        is_adaptive = True
        similarity = None
        ability_vector_exists = False

        if next_question is not None:
            profile_vector, ability_level, _ = service.get_user_ability_vector(
                current_user.id,
                payload.session_id,
                current_module,
                transient_records=transient_records,
            )
            if profile_vector is not None and next_question.feature_vector:
                question_vector = np.array(next_question.feature_vector)
                similarity = service._cosine_similarity(profile_vector, question_vector)
                ability_vector_exists = True
        else:
            print(f"[DEBUG] 智能选题返回None，进入回退逻辑")
            print(f"[DEBUG] stage={stage}, current_module={current_module}")
            query = db.query(Question)
            if stage == "fixed":
                query = query.filter(Question.dimension_id == '1')
            elif current_module:
                if current_module in MODULE_DIM_MAP:
                    query = query.filter(Question.dimension_id == MODULE_DIM_MAP[current_module])

            if answered_ids:
                query = query.filter(Question.id.notin_(answered_ids))

            next_question = query.order_by(
                func.cast(func.substr(Question.exam_no, 2), db.Integer)
            ).first()

            if not next_question:
                raise HTTPException(status_code=404, detail="当前模块题目已用完")

            is_adaptive = False

        remaining = TOTAL_QUESTIONS - answered_count - 1
        if remaining < 0:
            remaining = 0

        selected_dimension = next_question.dimension_id
        selected_trait = next_question.trait_label

        return {
            "examNo": next_question.exam_no,
            "exam": next_question.content,
            "options": next_question.options,
            "total": TOTAL_QUESTIONS,
            "remaining": remaining,
            "is_adaptive": is_adaptive,
            "current_module": current_module,
            "selected_dimension": selected_dimension,
            "selected_trait": selected_trait,
            "question_stats": {
                "difficulty": float(next_question.difficulty or 0.5),
                "discrimination": float(next_question.discrimination or 0.7),
                "has_feature_vector": next_question.feature_vector is not None,
                "similarity": similarity,
                "ability_vector_exists": ability_vector_exists,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"智能选题错误: {e}")
        index = fallback_index
        if index >= TOTAL_QUESTIONS:
            raise HTTPException(status_code=404, detail="测评已完成")

        db_question = db.query(Question).offset(index).limit(1).first()
        if not db_question:
            raise HTTPException(status_code=404, detail="题库已做完")

        return {
            "examNo": db_question.exam_no,
            "exam": db_question.content,
            "options": db_question.options,
            "total": TOTAL_QUESTIONS,
            "remaining": TOTAL_QUESTIONS - index - 1,
            "is_adaptive": False,
            "error": "智能选题失败，使用顺序模式",
            "question_stats": {
                "difficulty": float(db_question.difficulty or 0.5),
                "discrimination": float(db_question.discrimination or 0.7),
                "has_feature_vector": db_question.feature_vector is not None,
                "similarity": None,
                "ability_vector_exists": False,
            },
        }
