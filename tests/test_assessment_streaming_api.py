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


def test_report_response_includes_agent_workflow():
    client = TestClient(app)

    fake_session = SimpleNamespace(
        id=12,
        user_id=7,
        status="completed",
        title="部署演示测评",
        started_at=None,
        finished_at=None,
        report_content="本报告仅作为非临床参考，不能替代专业诊断。",
        trust_summary={},
        evidence_summary={},
        adaptive_metrics={},
    )
    fake_record = SimpleNamespace(
        exam_no="A1",
        selected_option="符合",
        score=4,
        time_spent=8.0,
        is_anomaly=0,
        ai_follow_up=None,
        user_explanation=None,
        risk_score=0,
        risk_reasons=[],
        answer_confidence=1.0,
        behavior_metrics={},
    )
    fake_question = SimpleNamespace(
        exam_no="A1",
        content="我能欣赏他人的优点",
        dimension_id="6",
        trait_label="欣赏线索",
        is_reverse=False,
    )
    fake_debates = [
        SimpleNamespace(module=module, result_content=f"模块 {module} 分析")
        for module in ["A", "T", "M", "R"]
    ]

    class FakeQuery:
        def __init__(self, items):
            self.items = items

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return self.items[0] if self.items else None

        def all(self):
            return self.items

    class FakeDB:
        def query(self, model):
            model_name = getattr(model, "__name__", "")
            if model_name == "AssessmentSession":
                return FakeQuery([fake_session])
            if model_name == "AnswerRecord":
                return FakeQuery([fake_record])
            if model_name == "Question":
                return FakeQuery([fake_question])
            if model_name == "ModuleDebateResult":
                return FakeQuery(fake_debates)
            return FakeQuery([])

        def commit(self):
            return None

    from app.core.database import get_db

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=7, username="tester")
    app.dependency_overrides[get_db] = lambda: FakeDB()

    try:
        response = client.get("/api/v1/assessment/report/12")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent_workflow"]["name"] == "evidence_constrained_static_agent"
    assert payload["agent_state"]["workflow"] == "evidence_constrained_static_agent"
    assert payload["agent_trace"]["steps"][0]["key"] == "observe_assessment"
    assert payload["report_critic"]["status"] == "passed"
