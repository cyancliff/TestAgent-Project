"""
测评会话管理路由：创建、恢复、重新打开、删除
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.question import (
    SessionLocal, Question, AssessmentSession, AnswerRecord,
    ModuleDebateResult, ChatSession, User,
)
from app.api.assessment.schemas import StartSessionRequest

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


@router.post("/start-session")
async def start_session(
    payload: StartSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新测评会话，清理旧的 active 会话"""
    old_sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
    ).all()
    for old in old_sessions:
        db.query(AnswerRecord).filter(AnswerRecord.session_id == old.id).delete()
        db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == old.id).delete()
        db.delete(old)
    db.commit()

    new_session = AssessmentSession(user_id=current_user.id, status='active')
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id, "status": "success"}


@router.get("/resume-session")
async def resume_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """恢复未完成的测评会话"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
    ).order_by(AssessmentSession.started_at.desc()).first()

    if not session:
        return {"has_active_session": False}

    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session.id,
        AnswerRecord.user_id == current_user.id,
    ).all()

    if not records:
        return {"has_active_session": False}

    exam_nos = [r.exam_no for r in records]
    questions = db.query(Question).filter(
        Question.exam_no.in_(exam_nos)
    ).all()
    q_map = {q.exam_no: q for q in questions}

    answers_data = []
    questions_data = []
    for r in records:
        q = q_map.get(r.exam_no)
        answers_data.append({
            "exam_no": r.exam_no,
            "selected_option": r.selected_option,
            "time_spent": float(r.time_spent) if r.time_spent else 0,
            "score": float(r.score) if r.score else 0,
            "is_anomaly": r.is_anomaly,
            "ai_follow_up": r.ai_follow_up,
            "user_explanation": r.user_explanation,
        })
        if q:
            questions_data.append({
                "examNo": q.exam_no,
                "exam": q.content,
                "options": q.options,
            })

    return {
        "has_active_session": True,
        "session_id": session.id,
        "answered_count": len(records),
        "answers": answers_data,
        "questions": questions_data,
    }


@router.post("/reopen-session/{session_id}")
async def reopen_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重新打开已完成的会话以修改答案"""
    session = ensure_session_owner(db, session_id, current_user.id)
    if session.status != 'completed':
        raise HTTPException(status_code=400, detail="该会话不是已完成状态")

    # 关闭该用户其他 active 会话
    old_active = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
        AssessmentSession.id != session_id,
    ).all()
    for old in old_active:
        db.query(AnswerRecord).filter(AnswerRecord.session_id == old.id).delete()
        db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == old.id).delete()
        db.delete(old)

    session.status = 'active'
    session.finished_at = None
    session.report_content = None
    session.report_file_path = None
    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).delete()
    db.commit()

    return {"status": "success", "session_id": session_id}


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除测评记录及其关联文件"""
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
        except Exception as e:
            print(f"删除报告文件失败: {e}")

    return {"status": "success", "message": "测评记录已删除"}
