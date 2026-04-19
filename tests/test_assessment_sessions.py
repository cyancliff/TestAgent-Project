"""
Assessment session and staged-persistence regressions.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.assessment.sessions import reopen_session, resume_session, start_session
from app.api.assessment.streaming import get_history
from app.api.assessment.submissions import save_answer, submit_stage
from app.core.constants import MODULE_DIM_MAP, STAGE_DIM_MAP
from app.models.assessment import AnswerRecord, AssessmentSession, Question


def test_start_session_requires_confirmation_when_active_session_exists():
    db = MagicMock()
    current_user = MagicMock(id=7)
    existing_active = MagicMock(id=42)
    existing_active.title = "进行中"
    existing_active.started_at = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)

    with patch("app.api.assessment.sessions.get_latest_active_session", return_value=existing_active):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                start_session(
                    payload=SimpleNamespace(force_overwrite=False),
                    db=db,
                    current_user=current_user,
                )
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "active_session_exists"
    assert exc_info.value.detail["session_id"] == 42
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_start_session_force_overwrite_stays_in_draft_mode():
    db = MagicMock()
    current_user = MagicMock(id=7)
    existing_active = MagicMock(id=42)
    existing_active.title = "进行中"
    existing_active.started_at = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)
    active_query = MagicMock()
    active_query.filter.return_value.all.return_value = [existing_active]
    db.query.return_value = active_query

    with patch("app.api.assessment.sessions.get_latest_active_session", return_value=existing_active), patch(
        "app.api.assessment.sessions.delete_assessment_session_data"
    ) as delete_session_data:
        delete_session_data.return_value = None
        result = asyncio.run(
            start_session(
                payload=SimpleNamespace(force_overwrite=True),
                db=db,
                current_user=current_user,
            )
        )

    delete_session_data.assert_called_once_with(db, existing_active)
    assert result["session_id"] is None
    assert result["draft_only"] is True
    assert result["overwrote_existing"] is True
    db.add.assert_not_called()


def test_reopen_session_blocks_when_other_active_session_exists():
    db = MagicMock()
    current_user = MagicMock(id=7)
    completed_session = MagicMock(status="completed")
    other_active = MagicMock(id=99)

    with patch("app.api.assessment.sessions.ensure_session_owner", return_value=completed_session), patch(
        "app.api.assessment.sessions.get_latest_active_session",
        return_value=other_active,
    ):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(reopen_session(session_id=12, db=db, current_user=current_user))

    assert exc_info.value.status_code == 409
    assert "未完成" in exc_info.value.detail
    db.commit.assert_not_called()


def test_reopen_session_creates_new_editable_copy():
    db = MagicMock()
    current_user = MagicMock(id=7)
    completed_session = SimpleNamespace(id=12, status="completed", user_id=7)
    copied_session = SimpleNamespace(id=18)

    with patch("app.api.assessment.sessions.ensure_session_owner", return_value=completed_session), patch(
        "app.api.assessment.sessions.get_latest_active_session",
        return_value=None,
    ), patch(
        "app.api.assessment.sessions.create_editable_session_copy",
        return_value=copied_session,
    ) as create_copy:
        result = asyncio.run(reopen_session(session_id=12, db=db, current_user=current_user))

    create_copy.assert_called_once_with(db, completed_session)
    assert result == {
        "status": "success",
        "session_id": 18,
    }


def test_resume_session_exposes_question_stage_metadata():
    db = MagicMock()
    current_user = SimpleNamespace(id=7)
    active_session = SimpleNamespace(id=21)
    records = [
        SimpleNamespace(
            exam_no="DX01",
            selected_option="A",
            time_spent=2.5,
            score=1.0,
            is_anomaly=0,
            ai_follow_up=None,
            user_explanation=None,
        ),
        SimpleNamespace(
            exam_no="Z016",
            selected_option="4",
            time_spent=6.2,
            score=4.0,
            is_anomaly=0,
            ai_follow_up=None,
            user_explanation="",
        ),
    ]
    questions = [
        SimpleNamespace(
            exam_no="DX01",
            content="intro question",
            options=["A", "B"],
            dimension_id=STAGE_DIM_MAP["intro"],
        ),
        SimpleNamespace(
            exam_no="Z016",
            content="A question",
            options=["1", "2", "3", "4", "5"],
            dimension_id=STAGE_DIM_MAP["A"],
        ),
    ]
    stage_service = MagicMock()
    stage_service.get_all_answer_records.return_value = records
    stage_service.get_current_stage.return_value = "intro"
    stage_service.get_submitted_stages.return_value = []

    question_query = MagicMock()
    question_query.filter.return_value.all.return_value = questions

    def query_side_effect(model):
        if model is Question:
            return question_query
        raise AssertionError(f"unexpected model query: {model}")

    db.query.side_effect = query_side_effect

    with patch("app.api.assessment.sessions.get_latest_active_session", return_value=active_session), patch(
        "app.api.assessment.sessions.StageService",
        return_value=stage_service,
    ):
        result = asyncio.run(resume_session(db=db, current_user=current_user))

    assert result["has_active_session"] is True
    assert result["questions"] == [
        {
            "examNo": "DX01",
            "exam": "intro question",
            "options": ["A", "B"],
            "dimension_id": STAGE_DIM_MAP["intro"],
            "stage": "intro",
        },
        {
            "examNo": "Z016",
            "exam": "A question",
            "options": ["1", "2", "3", "4", "5"],
            "dimension_id": STAGE_DIM_MAP["A"],
            "stage": "A",
        },
    ]


def test_resume_session_prefers_explicit_session_id():
    db = MagicMock()
    current_user = SimpleNamespace(id=7)
    active_session = SimpleNamespace(id=21, status="active")
    stage_service = MagicMock()
    stage_service.get_all_answer_records.return_value = []
    stage_service.get_current_stage.return_value = "intro"
    stage_service.get_submitted_stages.return_value = []

    with patch("app.api.assessment.sessions.ensure_session_owner", return_value=active_session) as ensure_owner, patch(
        "app.api.assessment.sessions.get_latest_active_session"
    ) as get_latest, patch(
        "app.api.assessment.sessions.StageService",
        return_value=stage_service,
    ):
        result = asyncio.run(resume_session(session_id=21, db=db, current_user=current_user))

    ensure_owner.assert_called_once_with(db, 21, current_user.id)
    get_latest.assert_not_called()
    assert result["has_active_session"] is False


def test_get_history_includes_active_sessions():
    db = MagicMock()
    current_user = SimpleNamespace(id=7)
    dim_id = next(iter(MODULE_DIM_MAP.values()))
    started_at = datetime(2026, 4, 19, 9, 0, tzinfo=timezone.utc)
    finished_at = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)

    active_session = SimpleNamespace(
        id=11,
        title="进行中的测评",
        started_at=started_at,
        finished_at=None,
        status="active",
        current_stage="A",
        report_content=None,
    )
    completed_session = SimpleNamespace(
        id=12,
        title="已完成的测评",
        started_at=finished_at,
        finished_at=finished_at,
        status="completed",
        current_stage=None,
        report_content="report-ready",
    )
    records = [
        SimpleNamespace(session_id=11, exam_no="Q001", score=4, is_anomaly=0),
        SimpleNamespace(session_id=12, exam_no="Q002", score=5, is_anomaly=1),
    ]
    questions = [
        SimpleNamespace(exam_no="Q001", dimension_id=dim_id),
        SimpleNamespace(exam_no="Q002", dimension_id=dim_id),
    ]

    def query_side_effect(model):
        query = MagicMock()
        if model is AssessmentSession:
            query.filter.return_value.order_by.return_value.all.return_value = [
                active_session,
                completed_session,
            ]
        elif model is AnswerRecord:
            query.filter.return_value.all.return_value = records
        elif model is Question:
            query.filter.return_value.all.return_value = questions
        else:
            raise AssertionError(f"unexpected model query: {model}")
        return query

    db.query.side_effect = query_side_effect

    result = asyncio.run(get_history(db=db, current_user=current_user))

    assert [session["status"] for session in result["sessions"]] == ["active", "completed"]
    assert result["sessions"][0]["stage_display_name"]
    assert result["sessions"][0]["has_report"] is False
    assert result["sessions"][1]["has_report"] is True


def test_save_answer_is_now_a_noop_until_stage_submit():
    db = MagicMock()
    current_user = SimpleNamespace(id=7)
    payload = SimpleNamespace(
        session_id=12,
        exam_no="Q001",
        selected_option="A",
        time_spent=3.2,
        score=4.0,
        is_anomaly=0,
        ai_follow_up=None,
        user_explanation=None,
    )

    with patch("app.api.assessment.submissions.ensure_session_owner", return_value=SimpleNamespace(status="active")):
        result = asyncio.run(save_answer(payload=payload, db=db, current_user=current_user))

    assert result["persisted"] is False
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_submit_stage_creates_session_on_first_stage_commit():
    db = MagicMock()
    current_user = SimpleNamespace(id=7)
    background_tasks = MagicMock()
    background_tasks.add_task = MagicMock()
    answer_item = SimpleNamespace(
        exam_no="Q001",
        selected_option="A",
        time_spent=3.2,
        score=4.0,
        is_anomaly=0,
        ai_follow_up=None,
        user_explanation=None,
    )
    persisted_session = SimpleNamespace(id=55, status="active", finished_at=None)
    stage_service = MagicMock()
    stage_service.advance_to_next_stage.return_value = "A"
    stage_service.session = persisted_session

    answer_query = MagicMock()
    answer_query.filter.return_value.first.return_value = None
    db.query.return_value = answer_query

    with patch("app.api.assessment.submissions.get_latest_active_session", return_value=None), patch(
        "app.api.assessment.submissions.validate_stage_answers",
        return_value=({"Q001": answer_item}, {"Q001": SimpleNamespace()}),
    ), patch(
        "app.api.assessment.submissions.create_assessment_session",
        return_value=persisted_session,
    ) as create_session, patch(
        "app.api.assessment.submissions.StageService",
        return_value=stage_service,
    ):
        result = asyncio.run(
            submit_stage(
                payload=SimpleNamespace(session_id=None, answers=[answer_item]),
                background_tasks=background_tasks,
                db=db,
                current_user=current_user,
            )
        )

    create_session.assert_called_once_with(db, current_user.id)
    assert result["session_id"] == 55
    assert result["next_stage"] == "A"
    assert result["all_completed"] is False
