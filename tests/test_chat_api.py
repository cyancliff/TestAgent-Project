import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.chat import UpdateChatSessionRequest, update_chat_session
from app.api.chat import get_big_five_context
from app.core.database import Base
from app.models.assessment import AssessmentSession
from app.models.chat import ChatMessage, ChatSession
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User


def _build_test_session(tmp_path):
    db_path = tmp_path / "chat_api_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    return engine, testing_session_local()


def _seed_chat_session(db, with_history=True):
    user = User(username="chat-reviewer", nickname="Chat Reviewer", password_hash="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)

    original_assessment = AssessmentSession(
        user_id=user.id,
        status="completed",
        title="原始测评",
        report_content="old report",
    )
    replacement_assessment = AssessmentSession(
        user_id=user.id,
        status="completed",
        title="新测评",
        report_content="new report",
    )
    db.add_all([original_assessment, replacement_assessment])
    db.commit()
    db.refresh(original_assessment)
    db.refresh(replacement_assessment)

    big_five_report = BigFivePersonalityReport(
        task_id="task-real-1",
        user_id=user.id,
        title="视频大五人格报告",
        status="completed",
        message="done",
        original_filename="demo.mp4",
        video_path="demo.mp4",
        model_version="agtn-mtl-best-lr1e4-drop02",
        scores={
            "openness": 0.61,
            "conscientiousness": 0.58,
            "extraversion": 0.54,
            "agreeableness": 0.57,
            "neuroticism": 0.49,
        },
        is_real_result=True,
    )
    db.add(big_five_report)
    db.commit()
    db.refresh(big_five_report)

    chat_session = ChatSession(
        user_id=user.id,
        assessment_session_id=original_assessment.id,
        title="原始测评 咨询",
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    system_message = ChatMessage(
        chat_session_id=chat_session.id,
        session_id=original_assessment.id,
        user_id=user.id,
        role="system",
        content="old-system",
    )
    db.add(system_message)

    if with_history:
        db.add_all(
            [
                ChatMessage(
                    chat_session_id=chat_session.id,
                    session_id=original_assessment.id,
                    user_id=user.id,
                    role="user",
                    content="old-msg",
                ),
                ChatMessage(
                    chat_session_id=chat_session.id,
                    session_id=original_assessment.id,
                    user_id=user.id,
                    role="assistant",
                    content="old-reply",
                ),
            ]
        )
    db.commit()

    return SimpleNamespace(
        user=user,
        chat_session=chat_session,
        original_assessment=original_assessment,
        replacement_assessment=replacement_assessment,
        big_five_report=big_five_report,
    )


def test_update_chat_session_rejects_assessment_change_when_history_exists(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        seeded = _seed_chat_session(db, with_history=True)

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                update_chat_session(
                    chat_session_id=seeded.chat_session.id,
                    payload=UpdateChatSessionRequest(assessment_session_id=seeded.replacement_assessment.id),
                    db=db,
                    current_user=SimpleNamespace(id=seeded.user.id),
                )
            )

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == seeded.chat_session.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
        db.refresh(seeded.chat_session)
    finally:
        db.close()
        engine.dispose()

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "chat_session_has_history"
    assert seeded.chat_session.assessment_session_id == seeded.original_assessment.id
    assert [msg.role for msg in messages] == ["system", "user", "assistant"]
    assert [msg.content for msg in messages] == ["old-system", "old-msg", "old-reply"]


def test_update_chat_session_allows_assessment_change_for_empty_session(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        seeded = _seed_chat_session(db, with_history=False)

        result = asyncio.run(
            update_chat_session(
                chat_session_id=seeded.chat_session.id,
                payload=UpdateChatSessionRequest(assessment_session_id=seeded.replacement_assessment.id),
                db=db,
                current_user=SimpleNamespace(id=seeded.user.id),
            )
        )

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == seeded.chat_session.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    finally:
        db.close()
        engine.dispose()

    assert result["assessment_session_id"] == seeded.replacement_assessment.id
    assert [(msg.role, msg.session_id) for msg in messages] == [("system", seeded.replacement_assessment.id)]
    assert messages[0].content != "old-system"
    assert "new report" in messages[0].content


def test_update_chat_session_title_change_preserves_existing_history(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        seeded = _seed_chat_session(db, with_history=True)

        result = asyncio.run(
            update_chat_session(
                chat_session_id=seeded.chat_session.id,
                payload=UpdateChatSessionRequest(title="重命名后的会话"),
                db=db,
                current_user=SimpleNamespace(id=seeded.user.id),
            )
        )

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == seeded.chat_session.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    finally:
        db.close()
        engine.dispose()

    assert result["title"] == "重命名后的会话"
    assert [msg.role for msg in messages] == ["system", "user", "assistant"]
    assert [msg.content for msg in messages] == ["old-system", "old-msg", "old-reply"]


def test_update_chat_session_can_reset_history_and_attach_big_five_report(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        seeded = _seed_chat_session(db, with_history=True)

        result = asyncio.run(
            update_chat_session(
                chat_session_id=seeded.chat_session.id,
                payload=UpdateChatSessionRequest(
                    assessment_session_id=seeded.replacement_assessment.id,
                    big_five_report_id=seeded.big_five_report.id,
                    reset_history=True,
                ),
                db=db,
                current_user=SimpleNamespace(id=seeded.user.id),
            )
        )

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.chat_session_id == seeded.chat_session.id)
            .order_by(ChatMessage.id.asc())
            .all()
        )
    finally:
        db.close()
        engine.dispose()

    assert result["assessment_session_id"] == seeded.replacement_assessment.id
    assert result["big_five_report_id"] == seeded.big_five_report.id
    assert [(msg.role, msg.session_id) for msg in messages] == [("system", seeded.replacement_assessment.id)]
    assert "new report" in messages[0].content
    assert "视频大五人格报告" in messages[0].content
    assert "开放性: 61/100" in messages[0].content


def test_big_five_context_prefers_ai_interpretation_when_available(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        seeded = _seed_chat_session(db, with_history=False)
        seeded.big_five_report.interpretation_status = "completed"
        seeded.big_five_report.interpretation_content = "# 大五人格详细解读\n\n这是大五 AI 解读正文。"
        db.commit()

        context = get_big_five_context(seeded.big_five_report.id, db)
    finally:
        db.close()
        engine.dispose()

    assert "【AI 详细解读】" in context
    assert "这是大五 AI 解读正文" in context
