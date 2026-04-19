"""
测评会话管理路由：创建、恢复、重新开始、重新打开、删除
"""

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.assessment.schemas import StartSessionRequest, UpdateSessionRequest
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.assessment import AnswerRecord, AssessmentSession, ModuleDebateResult, Question
from app.models.chat import ChatSession
from app.models.user import User
from app.services.stage_service import StageService

router = APIRouter()


def get_latest_active_session(
    db: Session,
    user_id: int,
    exclude_session_id: int | None = None,
) -> AssessmentSession | None:
    """Return the latest active assessment session for the current user."""
    query = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id,
        AssessmentSession.status == "active",
    )
    if exclude_session_id is not None:
        query = query.filter(AssessmentSession.id != exclude_session_id)
    return query.order_by(AssessmentSession.started_at.desc()).first()


def ensure_session_owner(db: Session, session_id: int, user_id: int) -> AssessmentSession:
    """校验会话属于当前用户。"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


def build_assessment_session_title(started_at: datetime | None, session_id: int | None = None) -> str:
    if started_at is not None:
        try:
            return started_at.astimezone().strftime("%Y.%m.%d %H:%M")
        except Exception:
            return started_at.strftime("%Y.%m.%d %H:%M")
    if session_id is not None:
        return f"测评 #{session_id}"
    return "未命名测评"


@router.post("/start-session")
async def start_session(
    payload: StartSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新测评会话，如已有未完成会话则直接复用。"""
    existing_active = get_latest_active_session(db, current_user.id)
    if existing_active:
        return {
            "session_id": existing_active.id,
            "status": "success",
            "reused_existing": True,
        }

    new_session = AssessmentSession(
        user_id=current_user.id,
        status="active",
        current_stage="intro",
        submitted_stages=[],
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    new_session.title = build_assessment_session_title(new_session.started_at, new_session.id)
    db.commit()
    return {
        "session_id": new_session.id,
        "status": "success",
        "reused_existing": False,
    }


@router.get("/resume-session")
async def resume_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复未完成的测评会话。"""
    session = get_latest_active_session(db, current_user.id)
    if not session:
        return {"has_active_session": False}

    stage_service = StageService(db, session.id, current_user.id)
    records = stage_service.get_all_answer_records()
    if not records:
        return {"has_active_session": False}

    exam_nos = [record.exam_no for record in records]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {question.exam_no: question for question in questions}

    answers_data = []
    questions_data = []
    for record in records:
        question = question_map.get(record.exam_no)
        answers_data.append(
            {
                "exam_no": record.exam_no,
                "selected_option": record.selected_option,
                "time_spent": float(record.time_spent) if record.time_spent else 0,
                "score": float(record.score) if record.score else 0,
                "is_anomaly": record.is_anomaly,
                "ai_follow_up": record.ai_follow_up,
                "user_explanation": record.user_explanation,
            }
        )
        if question:
            questions_data.append(
                {
                    "examNo": question.exam_no,
                    "exam": question.content,
                    "options": question.options,
                }
            )

    current_stage = stage_service.get_current_stage()
    return {
        "has_active_session": True,
        "session_id": session.id,
        "current_stage": current_stage,
        "submitted_stages": stage_service.get_submitted_stages(),
        "answered_count": len(records),
        "answers": answers_data,
        "questions": questions_data,
    }


@router.post("/restart-session")
async def restart_session(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新作答：重置阶段到 intro，清理辩论结果，保留作答记录。"""
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="缺少 session_id")

    session = ensure_session_owner(db, session_id, current_user.id)
    if session.status not in {"completed", "active"}:
        raise HTTPException(status_code=400, detail="该会话不可重新开始")

    stage_service = StageService(db, session_id, current_user.id)
    stage_service.restart_session()

    return {
        "status": "success",
        "session_id": session_id,
        "current_stage": "intro",
        "message": "已重置阶段，可重新作答",
    }


@router.post("/reopen-session/{session_id}")
async def reopen_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新打开已完成的会话以修改答案。"""
    session = ensure_session_owner(db, session_id, current_user.id)
    if session.status != "completed":
        raise HTTPException(status_code=400, detail="该会话不是已完成状态")

    existing_active = get_latest_active_session(db, current_user.id, exclude_session_id=session_id)
    if existing_active:
        raise HTTPException(
            status_code=409,
            detail="当前还有一份未完成的测评，请先继续或重置它，系统已不再自动删除旧答题记录",
        )

    session.status = "active"
    session.current_stage = "intro"
    session.submitted_stages = []
    session.finished_at = None
    session.report_content = None
    session.report_file_path = None
    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).delete()
    db.commit()

    return {"status": "success", "session_id": session_id}


@router.put("/session/{session_id}")
async def update_session(
    session_id: int,
    payload: UpdateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = ensure_session_owner(db, session_id, current_user.id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")

    session.title = title
    db.commit()

    return {
        "status": "success",
        "session_id": session.id,
        "title": session.title,
    }


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除测评记录及其关联文件。"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    report_file_path = session.report_file_path

    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).delete()
    db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).delete()
    db.query(ChatSession).filter(ChatSession.assessment_session_id == session_id).update(
        {ChatSession.assessment_session_id: None}
    )
    db.delete(session)
    db.commit()

    if report_file_path and os.path.exists(report_file_path):
        try:
            os.remove(report_file_path)
        except Exception as exc:
            print(f"删除报告文件失败: {exc}")

    return {"status": "success", "message": "测评记录已删除"}
