"""
Assessment session and history regressions.
"""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.assessment.sessions import reopen_session, start_session
from app.api.assessment.streaming import get_history
from app.core.constants import MODULE_DIM_MAP
from app.models.assessment import AnswerRecord, AssessmentSession, Question


def test_start_session_reuses_existing_active_session():
    db = MagicMock()
    current_user = MagicMock(id=7)
    existing_active = MagicMock(id=42)

    with patch("app.api.assessment.sessions.get_latest_active_session", return_value=existing_active):
        result = asyncio.run(
            start_session(payload=MagicMock(), db=db, current_user=current_user)
        )

    assert result == {
        "session_id": 42,
        "status": "success",
        "reused_existing": True,
    }
    db.add.assert_not_called()
    db.commit.assert_not_called()


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
