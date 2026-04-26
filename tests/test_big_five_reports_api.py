import asyncio
from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import multimodal_personality
from app.api.multimodal_personality import (
    _generate_interpretation_for_report,
    delete_report,
    get_report,
    upload_report_file,
)
from app.core.database import Base
from app.models.assessment import AssessmentSession
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User
from app.schemas.multimodal_personality import BigFiveScores
from app.services.big_five_report_service import _build_interpretation_prompt


def _build_test_session(tmp_path):
    db_path = tmp_path / "big_five_reports_test.db"
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


def _seed_user(db, username="big-five-user"):
    user = User(username=username, nickname=username, password_hash="hashed")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_upload_report_file_creates_owned_big_five_report(tmp_path, monkeypatch):
    engine, db = _build_test_session(tmp_path)
    try:
        user = _seed_user(db)
        assessment = AssessmentSession(user_id=user.id, status="completed", title="ATMR", report_content="report")
        db.add(assessment)
        db.commit()
        db.refresh(assessment)

        now = datetime.now(timezone.utc)
        fake_task = SimpleNamespace(
            task_id="task-123",
            status="pending",
            message="created",
            video_path=str(tmp_path / "demo.mp4"),
            session_id=assessment.id,
            model_version="scaffold-v1",
            scores=None,
            artifacts={},
            errors=[],
            created_at=now,
            updated_at=now,
        )
        monkeypatch.setattr(multimodal_personality.service, "save_uploaded_video", lambda **kwargs: fake_task)

        upload = UploadFile(filename="demo.mp4", file=BytesIO(b"video-bytes"))
        response = asyncio.run(
            upload_report_file(
                background_tasks=BackgroundTasks(),
                file=upload,
                source_assessment_session_id=assessment.id,
                title=None,
                db=db,
                current_user=SimpleNamespace(id=user.id),
            )
        )
        report = db.query(BigFivePersonalityReport).filter_by(task_id="task-123").one()
    finally:
        db.close()
        engine.dispose()

    assert response.report_id == report.id
    assert report.user_id == user.id
    assert report.source_assessment_session_id == assessment.id
    assert report.status == "running"
    assert report.title == "demo 大五人格报告"


def test_big_five_report_detail_and_delete_enforce_owner(tmp_path):
    engine, db = _build_test_session(tmp_path)
    try:
        owner = _seed_user(db, "owner")
        other = _seed_user(db, "other")
        report = BigFivePersonalityReport(
            task_id="task-owned",
            user_id=owner.id,
            title="Owned",
            status="completed",
            message="done",
            original_filename="owned.mp4",
            video_path="owned.mp4",
            model_version="agtn-mtl-best-lr1e4-drop02",
            scores=BigFiveScores(
                openness=0.61,
                conscientiousness=0.58,
                extraversion=0.54,
                agreeableness=0.57,
                neuroticism=0.49,
            ).model_dump(),
            is_real_result=True,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        response = asyncio.run(get_report(report.id, db=db, current_user=SimpleNamespace(id=owner.id)))
        with pytest.raises(HTTPException) as forbidden_detail:
            asyncio.run(get_report(report.id, db=db, current_user=SimpleNamespace(id=other.id)))

        delete_response = asyncio.run(delete_report(report.id, db=db, current_user=SimpleNamespace(id=owner.id)))
    finally:
        db.close()
        engine.dispose()

    assert response.report_id == report.id
    assert forbidden_detail.value.status_code == 404
    assert delete_response == {"status": "success"}


def test_generate_interpretation_for_real_big_five_report(tmp_path, monkeypatch):
    engine, db = _build_test_session(tmp_path)
    try:
        owner = _seed_user(db, "interpretation-owner")
        report = BigFivePersonalityReport(
            task_id="task-interpretation",
            user_id=owner.id,
            title="可解读报告",
            status="completed",
            message="done",
            original_filename="demo.mp4",
            video_path="demo.mp4",
            model_version="agtn-mtl-best-lr1e4-drop02",
            scores=BigFiveScores(
                openness=0.71,
                conscientiousness=0.62,
                extraversion=0.45,
                agreeableness=0.57,
                neuroticism=0.38,
            ).model_dump(),
            is_real_result=True,
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        monkeypatch.setattr(
            multimodal_personality,
            "generate_big_five_interpretation_sync",
            lambda report: ("# 大五人格详细解读\n\n开放性较高。", "deepseek-test"),
        )
        monkeypatch.setattr(
            multimodal_personality,
            "save_big_five_interpretation_to_file",
            lambda report_id, content: str(tmp_path / f"big-five-{report_id}.md"),
        )

        _generate_interpretation_for_report(db, report.id)
        db.refresh(report)
    finally:
        db.close()
        engine.dispose()

    assert report.interpretation_status == "completed"
    assert "大五人格详细解读" in report.interpretation_content
    assert report.interpretation_model == "deepseek-test"
    assert report.interpretation_file_path.endswith(f"big-five-{report.id}.md")


def test_big_five_interpretation_prompt_requires_compact_report_sections():
    report = BigFivePersonalityReport(
        id=7,
        task_id="task-prompt",
        user_id=1,
        title="视频人格报告",
        status="completed",
        message="done",
        original_filename="demo.mp4",
        video_path="demo.mp4",
        model_version="agtn-mtl-best-lr1e4-drop02",
        scores=BigFiveScores(
            openness=0.72,
            conscientiousness=0.68,
            extraversion=0.42,
            agreeableness=0.55,
            neuroticism=0.61,
        ).model_dump(),
        is_real_result=True,
    )

    prompt = _build_interpretation_prompt(report, "【开放性偏高】知识库证据")

    assert "# 大五人格详细解读" in prompt
    assert "## 01 报告摘要" in prompt
    assert "## 02 综合人格画像" in prompt
    assert "## 03 优势与潜在卡点" in prompt
    assert "## 04 行动建议" in prompt
    assert "## 05 使用边界" in prompt
    assert "不要生成“五维得分速览”表格" in prompt
    assert "不要生成“分维度报告”、Facet 长段落" in prompt
    assert "全文控制在 1200-1800 个中文字符左右" in prompt
    assert "开放性（O）: 72/100（偏高）" in prompt
    assert "视频结果受场景、情绪、拍摄状态影响" in prompt
