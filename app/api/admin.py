"""Lightweight admin APIs for ATMR quality governance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import require_admin
from app.models.assessment import AnswerRecord, AssessmentSession, Question
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class QuestionUpdateRequest(BaseModel):
    trait_label: str | None = Field(default=None, max_length=100)
    difficulty: float | None = Field(default=None, ge=0, le=1)
    discrimination: float | None = Field(default=None, ge=0, le=1)
    avg_time: float | None = Field(default=None, gt=0, le=999)
    is_reverse: bool | None = None
    is_active: bool | None = None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None


def _confidence_value(session: AssessmentSession) -> float | None:
    summary = session.trust_summary or {}
    if not isinstance(summary, dict):
        return None
    if "assessment_confidence" not in summary:
        return None
    return _safe_float(summary.get("assessment_confidence"))


def _confidence_label(value: float | None, summary: dict | None = None) -> str:
    if isinstance(summary, dict) and summary.get("label"):
        return str(summary["label"])
    if value is None:
        return "未知"
    if value >= 0.8:
        return "较高"
    if value >= 0.6:
        return "中等"
    return "较低"


def _page(items: list[dict], page: int, page_size: int) -> dict:
    total = len(items)
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _answer_stats(db: Session, exam_nos: list[str]) -> dict[str, dict[str, float]]:
    if not exam_nos:
        return {}
    rows = (
        db.query(
            AnswerRecord.exam_no,
            func.count(AnswerRecord.id),
            func.coalesce(func.sum(AnswerRecord.is_anomaly), 0),
        )
        .filter(AnswerRecord.exam_no.in_(exam_nos))
        .group_by(AnswerRecord.exam_no)
        .all()
    )
    stats = {}
    for exam_no, answer_count, anomaly_count in rows:
        answer_count = int(answer_count or 0)
        anomaly_count = int(anomaly_count or 0)
        stats[exam_no] = {
            "answer_count": answer_count,
            "anomaly_count": anomaly_count,
            "anomaly_rate": round(anomaly_count / answer_count, 4) if answer_count else 0.0,
        }
    return stats


def _question_payload(question: Question, stats: dict | None = None) -> dict:
    stats = stats or {}
    return {
        "exam_no": question.exam_no,
        "dimension_id": question.dimension_id,
        "content": question.content,
        "trait_label": question.trait_label,
        "difficulty": _safe_float(question.difficulty, 0.5),
        "discrimination": _safe_float(question.discrimination, 0.7),
        "avg_time": _safe_float(question.avg_time, 8.0),
        "is_reverse": bool(question.is_reverse),
        "is_active": bool(question.is_active),
        "answer_count": int(stats.get("answer_count", 0)),
        "anomaly_count": int(stats.get("anomaly_count", 0)),
        "anomaly_rate": stats.get("anomaly_rate", 0.0),
    }


def _session_stats(db: Session, session_ids: list[int]) -> dict[int, dict[str, int]]:
    if not session_ids:
        return {}
    rows = (
        db.query(
            AnswerRecord.session_id,
            func.count(AnswerRecord.id),
            func.coalesce(func.sum(AnswerRecord.is_anomaly), 0),
        )
        .filter(AnswerRecord.session_id.in_(session_ids))
        .group_by(AnswerRecord.session_id)
        .all()
    )
    return {
        int(session_id): {
            "question_count": int(question_count or 0),
            "anomaly_count": int(anomaly_count or 0),
        }
        for session_id, question_count, anomaly_count in rows
    }


def _assessment_list_item(session: AssessmentSession, user: User, stats: dict) -> dict:
    confidence = _confidence_value(session)
    summary = session.trust_summary or {}
    return {
        "session_id": session.id,
        "user_id": user.id,
        "username": user.username,
        "nickname": user.nickname or user.username,
        "title": session.title,
        "status": session.status,
        "started_at": _iso(session.started_at),
        "finished_at": _iso(session.finished_at),
        "question_count": stats.get("question_count", 0),
        "anomaly_count": stats.get("anomaly_count", 0),
        "assessment_confidence": confidence,
        "confidence_label": _confidence_label(confidence, summary if isinstance(summary, dict) else None),
        "has_report": bool(session.report_content),
    }


def _big_five_report_payload(report: BigFivePersonalityReport) -> dict:
    return {
        "report_id": report.id,
        "task_id": report.task_id,
        "title": report.title,
        "status": report.status,
        "message": report.message,
        "original_filename": report.original_filename,
        "source_assessment_session_id": report.source_assessment_session_id,
        "model_version": report.model_version,
        "scores": report.scores,
        "artifacts": report.artifacts or {},
        "errors": report.errors or [],
        "is_real_result": bool(report.is_real_result),
        "quality_summary": report.quality_summary or {},
        "confidence_summary": report.confidence_summary or {},
        "consistency_summary": report.consistency_summary or {},
        "interpretation_status": report.interpretation_status or "pending",
        "interpretation_content": report.interpretation_content,
        "interpretation_model": report.interpretation_model,
        "interpretation_error": report.interpretation_error,
        "interpretation_created_at": _iso(report.interpretation_created_at),
        "created_at": _iso(report.created_at),
        "updated_at": _iso(report.updated_at),
        "completed_at": _iso(report.completed_at),
    }


@router.get("/dashboard")
async def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    users_count = db.query(User).count()
    assessment_count = db.query(AssessmentSession).count()
    completed_sessions = db.query(AssessmentSession).filter(AssessmentSession.status == "completed").all()
    answer_count = db.query(AnswerRecord).count()
    anomaly_count = db.query(AnswerRecord).filter(AnswerRecord.is_anomaly == 1).count()
    big_five_reports = db.query(BigFivePersonalityReport).all()

    confidences = [value for value in (_confidence_value(session) for session in completed_sessions) if value is not None]
    low_confidence_count = sum(1 for value in confidences if value < 0.6)
    model_versions: dict[str, int] = {}
    for report in big_five_reports:
        model_versions[report.model_version or "unknown"] = model_versions.get(report.model_version or "unknown", 0) + 1

    return {
        "users_count": users_count,
        "assessment_count": assessment_count,
        "completed_report_count": len([session for session in completed_sessions if session.report_content]),
        "assessment_confidence_avg": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "answer_count": answer_count,
        "anomaly_count": anomaly_count,
        "anomaly_rate": round(anomaly_count / answer_count, 4) if answer_count else 0.0,
        "low_confidence_report_count": low_confidence_count,
        "big_five_report_count": len(big_five_reports),
        "big_five_failed_count": len([report for report in big_five_reports if report.status == "failed"]),
        "model_summary": {
            "checkpoint_path": settings.MULTIMODAL_CHECKPOINT_PATH,
            "versions": model_versions,
        },
    }


@router.get("/questions")
async def questions(
    dimension_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(Question)
    if dimension_id:
        query = query.filter(Question.dimension_id == dimension_id)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Question.exam_no.ilike(pattern),
                Question.content.ilike(pattern),
                Question.trait_label.ilike(pattern),
            )
        )
    if is_active is not None:
        query = query.filter(Question.is_active == is_active)

    total = query.count()
    rows = (
        query.order_by(Question.dimension_id, Question.exam_no)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    stats = _answer_stats(db, [question.exam_no for question in rows])
    return {
        "items": [_question_payload(question, stats.get(question.exam_no)) for question in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.patch("/questions/{exam_no}")
async def update_question(
    exam_no: str,
    payload: QuestionUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    question = db.query(Question).filter(Question.exam_no == exam_no).first()
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(question, field, value)
    db.commit()
    db.refresh(question)
    return _question_payload(question, _answer_stats(db, [question.exam_no]).get(question.exam_no))


@router.get("/assessment-reports")
async def assessment_reports(
    username: str | None = Query(default=None),
    confidence_label: str | None = Query(default=None),
    min_anomaly_count: int | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AssessmentSession, User).join(User, AssessmentSession.user_id == User.id)
    if username:
        pattern = f"%{username.strip()}%"
        query = query.filter(or_(User.username.ilike(pattern), User.nickname.ilike(pattern)))

    rows = query.order_by(AssessmentSession.started_at.desc()).all()
    stats_map = _session_stats(db, [session.id for session, _ in rows])
    items = [_assessment_list_item(session, user, stats_map.get(session.id, {})) for session, user in rows]
    if confidence_label:
        items = [item for item in items if item["confidence_label"] == confidence_label]
    if min_anomaly_count is not None:
        items = [item for item in items if item["anomaly_count"] >= min_anomaly_count]
    return _page(items, page, page_size)


@router.get("/assessment-reports/{session_id}")
async def assessment_report_detail(
    session_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="测评报告不存在")
    user = db.query(User).filter(User.id == session.user_id).first()
    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).order_by(AnswerRecord.created_at).all()
    questions = db.query(Question).filter(Question.exam_no.in_([record.exam_no for record in records])).all() if records else []
    question_map = {question.exam_no: question for question in questions}
    answers = []
    for record in records:
        question = question_map.get(record.exam_no)
        answers.append(
            {
                "exam_no": record.exam_no,
                "question": question.content if question else None,
                "dimension_id": question.dimension_id if question else None,
                "trait_label": question.trait_label if question else None,
                "selected_option": record.selected_option,
                "score": _safe_float(record.score),
                "time_spent": _safe_float(record.time_spent),
                "is_anomaly": bool(record.is_anomaly),
                "risk_score": int(record.risk_score or 0),
                "risk_reasons": record.risk_reasons or [],
                "answer_confidence": _safe_float(record.answer_confidence, 1.0),
                "behavior_metrics": record.behavior_metrics or {},
            }
        )

    stats = _session_stats(db, [session_id]).get(session_id, {})
    return {
        **_assessment_list_item(session, user, stats),
        "report_content": session.report_content,
        "trust_summary": session.trust_summary or {},
        "adaptive_metrics": session.adaptive_metrics or {},
        "evidence_summary": session.evidence_summary or {},
        "answers": answers,
    }


@router.get("/big-five-reports")
async def big_five_reports(
    username: str | None = Query(default=None),
    status: str | None = Query(default=None),
    model_version: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(BigFivePersonalityReport, User).join(User, BigFivePersonalityReport.user_id == User.id)
    if username:
        pattern = f"%{username.strip()}%"
        query = query.filter(or_(User.username.ilike(pattern), User.nickname.ilike(pattern)))
    if status:
        query = query.filter(BigFivePersonalityReport.status == status)
    if model_version:
        query = query.filter(BigFivePersonalityReport.model_version == model_version)

    rows = query.order_by(BigFivePersonalityReport.created_at.desc()).all()
    items = []
    for report, user in rows:
        confidence = report.confidence_summary or {}
        items.append(
            {
                "report_id": report.id,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname or user.username,
                "title": report.title,
                "status": report.status,
                "model_version": report.model_version,
                "is_real_result": bool(report.is_real_result),
                "overall_confidence": confidence.get("overall_confidence") if isinstance(confidence, dict) else None,
                "created_at": _iso(report.created_at),
                "completed_at": _iso(report.completed_at),
            }
        )
    return _page(items, page, page_size)


@router.get("/big-five-reports/{report_id}")
async def big_five_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="大五人格报告不存在")
    user = db.query(User).filter(User.id == report.user_id).first()
    data = _big_five_report_payload(report)
    data["owner"] = {
        "user_id": user.id if user else report.user_id,
        "username": user.username if user else None,
        "nickname": (user.nickname or user.username) if user else None,
    }
    return data


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="ignore")[:20000]


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


@router.get("/experiments")
async def experiments(_: User = Depends(require_admin)):
    specs = [
        ("ATMR-CAT 默认实验", "ATMR", "reports/atmr_cat_experiments/summary.md", None),
        ("ATMR-CAT 多随机种子", "ATMR", "reports/atmr_cat_multi_seed_experiments/summary.md", None),
        ("ATMR-CAT 异常注入", "ATMR", "reports/atmr_cat_anomaly_sweep_experiments/summary.md", None),
        ("可信度加权稳健性", "ATMR", "reports/atmr_confidence_weighting_experiments/summary.md", None),
        ("bg_features 重训", "多模态", None, "reports/agtn_mtl_bg_v1_lr1e4_drop02_full/test_eval.json"),
        ("多模态消融", "多模态", "reports/multimodal_ablation_experiments/ablation_summary.md", "reports/multimodal_ablation_experiments/ablation_summary.json"),
    ]
    items = []
    for title, category, markdown_path, json_path in specs:
        md_path = PROJECT_ROOT / markdown_path if markdown_path else None
        data_path = PROJECT_ROOT / json_path if json_path else None
        items.append(
            {
                "title": title,
                "category": category,
                "exists": bool((md_path and md_path.exists()) or (data_path and data_path.exists())),
                "markdown_path": markdown_path,
                "json_path": json_path,
                "markdown": _read_text(md_path) if md_path else None,
                "metrics": _read_json(data_path) if data_path else None,
            }
        )
    return {"items": items}
