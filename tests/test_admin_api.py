from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import get_current_user, hash_password
from app.main import app
from app.models.assessment import AnswerRecord, AssessmentSession, Question
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User
from app.services.question_selection import QuestionSelectionService


def _build_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return testing_session()


def _client(db, current_user=None):
    app.dependency_overrides[get_db] = lambda: db
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def _seed_admin_data(db):
    admin = User(username="admin", nickname="Admin", role="admin", password_hash=hash_password("12345678"))
    user = User(username="student", nickname="Student", role="user", password_hash=hash_password("12345678"))
    db.add_all([admin, user])
    db.commit()
    db.refresh(admin)
    db.refresh(user)

    q1 = Question(
        exam_no="A001",
        dimension_id="6",
        content="我愿意欣赏不同观点。",
        options=["A", "B", "C", "D", "E"],
        scores=[1, 2, 3, 4, 5],
        trait_label="欣赏线索",
        is_reverse=False,
        is_active=True,
        avg_time=8.0,
        feature_vector=[0.1, 0.2, 0.3],
        discrimination=0.7,
        difficulty=0.5,
    )
    q2 = Question(
        exam_no="A002",
        dimension_id="6",
        content="我会主动理解新的表达。",
        options=["A", "B", "C", "D", "E"],
        scores=[1, 2, 3, 4, 5],
        trait_label="理解线索",
        is_reverse=False,
        is_active=True,
        avg_time=8.0,
        feature_vector=[0.2, 0.3, 0.4],
        discrimination=0.8,
        difficulty=0.5,
    )
    db.add_all([q1, q2])
    db.commit()

    session = AssessmentSession(
        user_id=user.id,
        status="completed",
        current_stage="R",
        report_content="# ATMR 报告",
        trust_summary={"assessment_confidence": 0.82, "label": "较高"},
        adaptive_metrics={"algorithm": "ATMR-CAT"},
        evidence_summary={"strategy": "ATMR evidence-chain v1"},
        title="演示测评",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    answer = AnswerRecord(
        session_id=session.id,
        user_id=user.id,
        exam_no="A001",
        selected_option="E",
        score=5,
        time_spent=4.2,
        is_anomaly=1,
        risk_score=70,
        risk_reasons=["作答时间明显过快"],
        answer_confidence=0.465,
        behavior_metrics={"mouse_move_count": 0},
    )
    db.add(answer)
    report = BigFivePersonalityReport(
        task_id="task-admin-1",
        user_id=user.id,
        title="大五演示报告",
        status="completed",
        message="完成",
        original_filename="demo.mp4",
        video_path="uploads/demo.mp4",
        model_version="agtn-mtl-best-lr1e4-drop02",
        scores={"openness": 0.7},
        artifacts={},
        errors=[],
        is_real_result=True,
        quality_summary={"overall_quality": 0.9},
        confidence_summary={"overall_confidence": 0.88},
        consistency_summary={"status": "互相支持"},
    )
    db.add(report)
    db.commit()
    return admin, user, q1, q2, session, report


def test_register_admin_username_returns_admin_role():
    db = _build_session()
    client = _client(db)
    try:
        response = client.post("/api/v1/auth/register", json={"username": "admin", "password": "12345678"})
    finally:
        _clear_overrides()
        db.close()

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert response.json()["is_admin"] is True


def test_admin_dashboard_requires_admin():
    db = _build_session()
    _, user, *_ = _seed_admin_data(db)
    client = _client(db, user)
    try:
        response = client.get("/api/v1/admin/dashboard")
    finally:
        _clear_overrides()
        db.close()

    assert response.status_code == 403


def test_admin_dashboard_and_report_lists():
    db = _build_session()
    admin, *_ = _seed_admin_data(db)
    client = _client(db, admin)
    try:
        dashboard = client.get("/api/v1/admin/dashboard")
        reports = client.get("/api/v1/admin/assessment-reports")
        big_five = client.get("/api/v1/admin/big-five-reports")
    finally:
        _clear_overrides()
        db.close()

    assert dashboard.status_code == 200
    assert dashboard.json()["assessment_count"] == 1
    assert dashboard.json()["anomaly_count"] == 1
    assert reports.status_code == 200
    assert reports.json()["items"][0]["username"] == "student"
    assert big_five.status_code == 200
    assert big_five.json()["items"][0]["model_version"] == "agtn-mtl-best-lr1e4-drop02"


def test_admin_can_patch_question_and_disabled_question_is_not_selected():
    db = _build_session()
    admin, _, q1, q2, *_ = _seed_admin_data(db)
    client = _client(db, admin)
    try:
        response = client.patch(
            "/api/v1/admin/questions/A001",
            json={"difficulty": 0.33, "discrimination": 0.91, "is_active": False},
        )
        selected = QuestionSelectionService(db).select_next_question(
            user_id=admin.id,
            session_id=1,
            answered_question_ids=[],
            module="A",
        )
    finally:
        _clear_overrides()
        db.close()

    assert response.status_code == 200
    assert response.json()["difficulty"] == 0.33
    assert response.json()["discrimination"] == 0.91
    assert response.json()["is_active"] is False
    assert selected.exam_no == q2.exam_no
