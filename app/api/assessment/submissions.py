"""
测评作答提交路由：草稿保存、单题提交、批量提交、模块提交、异常检测
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.core.constants import (
    TOTAL_QUESTIONS, QUESTIONS_PER_MODULE, MODULES, MODULE_DIM_MAP, MODULE_COOLDOWN_SECONDS,
)
from app.models.question import (
    AnswerRecord, AssessmentSession, ModuleDebateResult, Question, User,
)
from app.services.ai_detector import check_anomaly_and_generate_question
from app.api.assessment.schemas import (
    SaveAnswerRequest, SubmitModuleRequest, AnswerSubmitRequest, AnswerSubmitResponse,
    ExplanationSubmitRequest, CheckAnswerRequest, BatchAnswerItem, BatchSubmitRequest,
)
from app.api.assessment.questions import get_current_module_and_stage

router = APIRouter()


def ensure_session_owner(db: Session, session_id: int, user_id: int) -> AssessmentSession:
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


def build_recent_answer_context(db: Session, session_id: int, user_id: int, limit: int = 5) -> list[dict]:
    """获取最近作答记录用于异常检测上下文"""
    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session_id,
        AnswerRecord.user_id == user_id,
    ).order_by(AnswerRecord.created_at.asc()).all()
    return [
        {
            "exam_no": record.exam_no,
            "selected_option": record.selected_option,
            "time_spent": float(record.time_spent or 0),
            "score": float(record.score or 0),
            "is_anomaly": int(record.is_anomaly or 0),
        }
        for record in records[-limit:]
    ]


def trigger_completed_module_debates(db: Session, session_id: int, user_id: int, background_tasks: BackgroundTasks):
    """检测已完成模块并触发辩论"""
    from app.api.assessment.streaming import trigger_module_debate

    all_records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session_id,
        AnswerRecord.user_id == user_id,
    ).all()
    if not all_records:
        return

    all_exam_nos = [rec.exam_no for rec in all_records]
    all_questions = db.query(Question).filter(Question.exam_no.in_(all_exam_nos)).all() if all_exam_nos else []
    all_q_map = {q.exam_no: q for q in all_questions}

    existing_modules = {
        r.module for r in db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).all()
    }

    for module, target_dimension in MODULE_DIM_MAP.items():
        if module in existing_modules:
            continue
        module_questions_count = 0
        for record in all_records:
            question = all_q_map.get(record.exam_no)
            if question and question.dimension_id == target_dimension:
                module_questions_count += 1
        if module_questions_count >= QUESTIONS_PER_MODULE:
            background_tasks.add_task(trigger_module_debate, session_id, user_id, module)


@router.post("/save-answer")
async def save_answer(
    payload: SaveAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """实时保存单题答案（草稿）"""
    session = ensure_session_owner(db, payload.session_id, current_user.id)
    if session.status == 'completed':
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
    db: Session = Depends(get_db),
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


@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(
    payload: AnswerSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单题提交（旧版兼容）"""
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    current_score, detection_result = await analyze_answer(
        db_question,
        payload.selected_option,
        payload.time_spent,
        recent_answers=build_recent_answer_context(db, payload.session_id, current_user.id),
    )
    is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
    new_record = AnswerRecord(
        session_id=payload.session_id,
        user_id=current_user.id,
        exam_no=payload.exam_no,
        selected_option=payload.selected_option,
        score=current_score,
        time_spent=payload.time_spent,
        is_anomaly=is_anomaly_flag,
        ai_follow_up=detection_result.get("follow_up"),
    )
    db.add(new_record)
    db.commit()

    try:
        trigger_completed_module_debates(db, payload.session_id, current_user.id, background_tasks)
    except Exception as e:
        print(f"模块完成检测出错: {e}")

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="记录已成功存入数据库",
        score=current_score,
        follow_up_question=detection_result.get("follow_up"),
        risk_score=detection_result.get("risk_score"),
        risk_reasons=detection_result.get("reasons", []),
    )


@router.post("/submit_explanation")
async def submit_explanation(
    payload: ExplanationSubmitRequest,
    db: Session = Depends(get_db),
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


@router.post("/submit-batch")
async def submit_batch(
    payload: BatchSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量提交答案（最终提交）"""
    session = ensure_session_owner(db, payload.session_id, current_user.id)
    if session.status == 'completed':
        raise HTTPException(status_code=400, detail="该测评已提交，不能重复提交")

    # 去重
    answer_map = {}
    for item in payload.answers:
        answer_map[item.exam_no] = item

    if len(answer_map) < TOTAL_QUESTIONS:
        print(f"[submit-batch] 去重后题目数: {len(answer_map)}/{TOTAL_QUESTIONS}（原始: {len(payload.answers)}）")

    exam_nos = list(answer_map.keys())
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {q.exam_no: q for q in questions}

    invalid_nos = [no for no in exam_nos if no not in question_map]
    if invalid_nos:
        raise HTTPException(status_code=400, detail=f"存在无效题目编号: {invalid_nos}")

    # 清理旧正式记录
    db.query(AnswerRecord).filter(AnswerRecord.session_id == payload.session_id).delete()
    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == payload.session_id).delete()
    db.commit()

    recent_answers = []
    for item in answer_map.values():
        db_question = question_map[item.exam_no]
        score, detection_result = await analyze_answer(
            db_question, item.selected_option, item.time_spent, recent_answers=recent_answers,
        )
        is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
        new_record = AnswerRecord(
            session_id=payload.session_id,
            user_id=current_user.id,
            exam_no=item.exam_no,
            selected_option=item.selected_option,
            score=score,
            time_spent=item.time_spent,
            is_anomaly=is_anomaly_flag,
            ai_follow_up=detection_result.get("follow_up"),
            user_explanation=item.user_explanation if is_anomaly_flag else None,
        )
        db.add(new_record)
        recent_answers.append({
            "exam_no": item.exam_no,
            "selected_option": item.selected_option,
            "time_spent": item.time_spent,
            "score": score,
            "is_anomaly": is_anomaly_flag,
        })
        recent_answers = recent_answers[-5:]

    session.status = 'completed'
    session.finished_at = datetime.now()
    db.commit()

    try:
        trigger_completed_module_debates(db, payload.session_id, current_user.id, background_tasks)
    except Exception as e:
        print(f"批量提交后模块辩论检测失败: {e}")

    # 后台自动生成最终报告
    from app.api.assessment.streaming import generate_report_in_background
    background_tasks.add_task(
        generate_report_in_background, payload.session_id, current_user.id,
    )

    return {
        "status": "success",
        "message": "答题记录已正式提交，报告将在后台自动生成",
        "saved_count": len(answer_map),
        "session_id": payload.session_id,
    }


@router.post("/finish")
async def finish_assessment(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保留兼容：标记测评完成"""
    session = ensure_session_owner(db, session_id, current_user.id)
    session.status = 'completed'
    session.finished_at = datetime.now()
    db.commit()

    return {
        "status": "success",
        "message": "测评已完成！请连接 /finish-stream 端点观看专家评审团的实时辩论并获取最终报告。",
    }


@router.post("/submit-module")
async def submit_module(
    payload: SubmitModuleRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动提交模块触发辩论"""
    from app.api.assessment.streaming import trigger_module_debate

    module = payload.module.upper()
    if module not in MODULES:
        raise HTTPException(status_code=400, detail=f"无效模块: {module}")

    session = ensure_session_owner(db, payload.session_id, current_user.id)

    target_dimension = MODULE_DIM_MAP[module]
    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
    ).all()
    exam_nos = [r.exam_no for r in records]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all() if exam_nos else []
    q_map = {q.exam_no: q for q in questions}

    module_count = sum(1 for r in records if q_map.get(r.exam_no) and q_map[r.exam_no].dimension_id == target_dimension)
    if module_count < QUESTIONS_PER_MODULE:
        raise HTTPException(status_code=400, detail=f"模块 {module} 答题不足 {QUESTIONS_PER_MODULE} 题（当前 {module_count} 题）")

    # 检查冷却时间
    existing = db.query(ModuleDebateResult).filter(
        ModuleDebateResult.session_id == payload.session_id,
        ModuleDebateResult.module == module,
    ).first()

    if existing:
        elapsed = (
            datetime.now(existing.created_at.tzinfo) if existing.created_at.tzinfo else datetime.now()
        ) - existing.created_at
        if elapsed.total_seconds() < MODULE_COOLDOWN_SECONDS:
            remaining = int(MODULE_COOLDOWN_SECONDS - elapsed.total_seconds())
            raise HTTPException(status_code=429, detail=f"请等待 {remaining} 秒后再重新提交")
        db.delete(existing)
        db.commit()

    background_tasks.add_task(trigger_module_debate, payload.session_id, current_user.id, module)
    return {"status": "success", "message": f"模块 {module} 辩论已启动"}
