from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app


def test_finish_stream_requires_authentication():
    client = TestClient(app)

    response = client.get("/api/v1/assessment/finish-stream", params={"session_id": 1})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_finish_stream_uses_standard_authenticated_user(monkeypatch):
    client = TestClient(app)
    fake_db = MagicMock()
    persisted_session = SimpleNamespace(report_content=None, report_file_path=None)
    fake_db.query.return_value.filter.return_value.first.return_value = persisted_session

    def fake_build_debate_context(user_id, db, session_id):
        assert user_id == 7
        assert db is fake_db
        assert session_id == 12
        return "prompt"

    def fake_run_debate_streaming(prompt, message_queue):
        assert prompt == "prompt"
        message_queue.put({"type": "done", "content": "final report"})

    monkeypatch.setattr("app.api.assessment.streaming.SessionLocal", lambda: fake_db)
    monkeypatch.setattr("app.api.assessment.streaming.build_debate_context", fake_build_debate_context)
    monkeypatch.setattr("app.api.assessment.streaming.run_debate_streaming", fake_run_debate_streaming)
    monkeypatch.setattr("app.api.assessment.streaming.save_report_to_file", lambda user_id, content: "saved-report.md")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, username="tester")

    try:
        response = client.get("/api/v1/assessment/finish-stream", params={"session_id": 12})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: debate_complete" in response.text
    assert "final report" in response.text
    assert persisted_session.report_content == "final report"
    assert persisted_session.report_file_path == "saved-report.md"
    fake_db.commit.assert_called()
    fake_db.close.assert_called()
