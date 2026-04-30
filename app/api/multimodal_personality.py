"""API endpoints for multimodal Big Five personality reports."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.security import get_current_user
from app.models.assessment import AssessmentSession
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User
from app.schemas.multimodal_personality import (
    BigFiveReportListResponse,
    BigFiveReportResponse,
    MultimodalHealthResponse,
    MultimodalRunRequest,
    MultimodalTaskResponse,
    MultimodalUploadRequest,
)
from app.services.big_five_report_service import (
    generate_big_five_interpretation_sync,
    save_big_five_interpretation_to_file,
)
from app.services.multimodal_evidence import (
    build_atmr_summary_for_session,
    build_consistency_summary,
    build_modality_quality_summary,
    build_prediction_confidence_summary,
)
from app.services.multimodal_personality_service import service

router = APIRouter()

REAL_MODEL_VERSION = "agtn-mtl-best-lr1e4-drop02"


def _to_response(task) -> MultimodalTaskResponse:
    return MultimodalTaskResponse(
        task_id=task.task_id,
        status=task.status,
        message=task.message,
        video_path=task.video_path,
        session_id=task.session_id,
        model_version=task.model_version,
        scores=task.scores,
        artifacts=task.artifacts,
        errors=task.errors,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _scores_payload(scores) -> dict | None:
    if scores is None:
        return None
    if hasattr(scores, "model_dump"):
        return scores.model_dump()
    return dict(scores)


def _is_real_result(task) -> bool:
    return bool(task.status == "completed" and task.scores is not None and task.model_version == REAL_MODEL_VERSION)


def _sync_report_from_task(report: BigFivePersonalityReport, task, db: Session | None = None) -> None:
    report.status = task.status
    report.message = task.message
    report.model_version = task.model_version
    report.scores = _scores_payload(task.scores)
    report.artifacts = dict(task.artifacts or {})
    report.errors = list(task.errors or [])
    report.is_real_result = _is_real_result(task)
    quality_summary = build_modality_quality_summary(report.artifacts, report.errors)
    report.quality_summary = quality_summary
    report.confidence_summary = build_prediction_confidence_summary(
        scores=report.scores,
        quality_summary=quality_summary,
        is_real_result=bool(report.is_real_result),
        used_fallback=not bool(report.is_real_result),
    )
    atmr_summary = build_atmr_summary_for_session(db, report.source_assessment_session_id) if db is not None else {}
    report.consistency_summary = build_consistency_summary(
        big_five_scores=report.scores,
        atmr_summary=atmr_summary,
    )
    if task.status == "completed" and not report.is_real_result:
        report.interpretation_status = "skipped"
        report.interpretation_error = "该报告不是可用于正式解读的真实模型输出。"
    elif task.status == "completed" and report.is_real_result:
        report.interpretation_status = "running"
        report.interpretation_error = None
    elif task.status == "failed":
        report.interpretation_status = "skipped"
        report.interpretation_error = "视频分析失败，未生成 AI 详细解读。"
    report.updated_at = datetime.now(timezone.utc)
    if task.status in {"completed", "failed"}:
        report.completed_at = report.updated_at


def _to_report_response(report: BigFivePersonalityReport) -> BigFiveReportResponse:
    return BigFiveReportResponse(
        report_id=report.id,
        task_id=report.task_id,
        title=report.title,
        status=report.status,
        message=report.message,
        original_filename=report.original_filename,
        source_assessment_session_id=report.source_assessment_session_id,
        model_version=report.model_version,
        scores=report.scores,
        artifacts=report.artifacts or {},
        errors=report.errors or [],
        is_real_result=bool(report.is_real_result),
        quality_summary=report.quality_summary or {},
        confidence_summary=report.confidence_summary or {},
        consistency_summary=report.consistency_summary or {},
        interpretation_status=report.interpretation_status or "pending",
        interpretation_content=report.interpretation_content,
        interpretation_model=report.interpretation_model,
        interpretation_error=report.interpretation_error,
        interpretation_created_at=report.interpretation_created_at,
        created_at=report.created_at,
        updated_at=report.updated_at,
        completed_at=report.completed_at,
    )


def _build_report_title(filename: str | None) -> str:
    stem = Path(filename or "").stem.strip()
    if stem:
        return f"{stem} 大五人格报告"[:100]
    return datetime.now().strftime("大五人格报告 %Y.%m.%d %H:%M")


def _get_owned_report(db: Session, report_id: int, user_id: int) -> BigFivePersonalityReport:
    report = (
        db.query(BigFivePersonalityReport)
        .filter(
            BigFivePersonalityReport.id == report_id,
            BigFivePersonalityReport.user_id == user_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="大五人格报告不存在")
    return report


def _validate_source_session(db: Session, source_assessment_session_id: int | None, user_id: int) -> None:
    if not source_assessment_session_id:
        return
    exists = (
        db.query(AssessmentSession.id)
        .filter(
            AssessmentSession.id == source_assessment_session_id,
            AssessmentSession.user_id == user_id,
        )
        .first()
    )
    if not exists:
        raise HTTPException(status_code=404, detail="来源测评不存在")


def _generate_interpretation_for_report(db: Session, report_id: int) -> None:
    report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
    if not report:
        return

    if not report.is_real_result or report.status != "completed" or not report.scores:
        report.interpretation_status = "skipped"
        report.interpretation_error = "只有真实完成的大五人格报告才能生成 AI 详细解读。"
        report.updated_at = datetime.now(timezone.utc)
        db.commit()
        return

    report.interpretation_status = "running"
    report.interpretation_error = None
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    try:
        content, model = generate_big_five_interpretation_sync(report)
        file_path = save_big_five_interpretation_to_file(report.id, content)
        now = datetime.now(timezone.utc)
        report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
        if not report:
            return
        report.interpretation_status = "completed"
        report.interpretation_content = content
        report.interpretation_file_path = file_path
        report.interpretation_model = model
        report.interpretation_error = None
        report.interpretation_created_at = now
        report.updated_at = now
        db.commit()
    except Exception as exc:
        db.rollback()
        report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
        if report:
            now = datetime.now(timezone.utc)
            report.interpretation_status = "failed"
            report.interpretation_error = str(exc)
            report.updated_at = now
            db.commit()


def run_big_five_interpretation_in_background(report_id: int) -> None:
    """Generate a Big Five AI interpretation for an existing report."""
    db = SessionLocal()
    try:
        _generate_interpretation_for_report(db, report_id)
    finally:
        db.close()


def run_big_five_report_in_background(report_id: int, task_id: str, force_restart: bool = False) -> None:
    """Run the multimodal task and persist its user-facing report state."""
    db = SessionLocal()
    try:
        report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
        if not report:
            return

        report.status = "running"
        report.message = "视频已接收，正在生成大五人格报告。"
        report.updated_at = datetime.now(timezone.utc)
        db.commit()

        task = service.run_task(task_id=task_id, force_restart=force_restart)
        report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
        if not report:
            return

        _sync_report_from_task(report, task, db)
        db.commit()
        db.refresh(report)
        if report.is_real_result:
            _generate_interpretation_for_report(db, report.id)
    except Exception as exc:
        db.rollback()
        report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == report_id).first()
        if report:
            now = datetime.now(timezone.utc)
            report.status = "failed"
            report.message = "大五人格报告生成失败，请稍后重试。"
            report.errors = [str(exc)]
            report.updated_at = now
            report.completed_at = now
            db.commit()
    finally:
        db.close()


@router.get("/health", response_model=MultimodalHealthResponse)
async def health(_: User = Depends(get_current_user)) -> MultimodalHealthResponse:
    """Check whether the multimodal subsystem is reachable."""
    return MultimodalHealthResponse(**service.health())


@router.post("/upload", response_model=MultimodalTaskResponse)
async def upload(
    payload: MultimodalUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MultimodalTaskResponse:
    """Register a local video path for later multimodal analysis."""
    _validate_source_session(db, payload.session_id, current_user.id)
    task = service.create_task(
        video_path=payload.video_path,
        session_id=payload.session_id,
        original_filename=payload.original_filename,
    )
    return _to_response(task)


@router.post("/upload-file", response_model=MultimodalTaskResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MultimodalTaskResponse:
    """Persist an uploaded video file and register a task."""
    _validate_source_session(db, session_id, current_user.id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件必须包含文件名")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    task = service.save_uploaded_video(filename=file.filename, content=content, session_id=session_id)
    return _to_response(task)


@router.post("/run", response_model=MultimodalTaskResponse)
async def run(payload: MultimodalRunRequest, _: User = Depends(get_current_user)) -> MultimodalTaskResponse:
    """Run the scaffold multimodal pipeline for an existing task."""
    try:
        task = service.run_task(task_id=payload.task_id, force_restart=payload.force_restart)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="多模态分析任务不存在") from exc
    return _to_response(task)


@router.get("/result/{task_id}", response_model=MultimodalTaskResponse)
async def result(task_id: str, _: User = Depends(get_current_user)) -> MultimodalTaskResponse:
    """Return the current task status and, if available, prediction scores."""
    try:
        task = service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="多模态分析任务不存在") from exc
    return _to_response(task)


@router.get("/reports", response_model=BigFiveReportListResponse)
async def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BigFiveReportListResponse:
    """List current user's Big Five personality reports."""
    reports = (
        db.query(BigFivePersonalityReport)
        .filter(BigFivePersonalityReport.user_id == current_user.id)
        .order_by(BigFivePersonalityReport.created_at.desc())
        .all()
    )
    return BigFiveReportListResponse(reports=[_to_report_response(report) for report in reports])


@router.post("/reports/upload-file", response_model=BigFiveReportResponse)
async def upload_report_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_assessment_session_id: int | None = Form(default=None),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BigFiveReportResponse:
    """Upload a video and create an independent Big Five personality report."""
    _validate_source_session(db, source_assessment_session_id, current_user.id)
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件必须包含文件名")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")

    task = service.save_uploaded_video(
        filename=file.filename,
        content=content,
        session_id=source_assessment_session_id,
    )
    now = datetime.now(timezone.utc)
    report = BigFivePersonalityReport(
        task_id=task.task_id,
        user_id=current_user.id,
        source_assessment_session_id=source_assessment_session_id,
        title=(title or "").strip()[:100] or _build_report_title(file.filename),
        status="running",
        message="视频已接收，正在生成大五人格报告。",
        original_filename=file.filename,
        video_path=task.video_path,
        model_version=task.model_version,
        scores=None,
        artifacts=dict(task.artifacts or {}),
        errors=list(task.errors or []),
        is_real_result=False,
        quality_summary={},
        confidence_summary={},
        consistency_summary={},
        interpretation_status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    background_tasks.add_task(run_big_five_report_in_background, report.id, task.task_id, False)
    return _to_report_response(report)


@router.post("/reports/{report_id}/run-background", response_model=BigFiveReportResponse)
async def retry_report(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BigFiveReportResponse:
    """Retry report generation in the background."""
    report = _get_owned_report(db, report_id, current_user.id)
    report.status = "running"
    report.message = "正在重新生成大五人格报告。"
    report.errors = []
    report.quality_summary = {}
    report.confidence_summary = {}
    report.consistency_summary = {}
    report.interpretation_status = "pending"
    report.interpretation_content = None
    report.interpretation_file_path = None
    report.interpretation_model = None
    report.interpretation_error = None
    report.interpretation_created_at = None
    report.completed_at = None
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    background_tasks.add_task(run_big_five_report_in_background, report.id, report.task_id, True)
    return _to_report_response(report)


@router.post("/reports/{report_id}/interpretation/run-background", response_model=BigFiveReportResponse)
async def retry_report_interpretation(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BigFiveReportResponse:
    """Retry AI interpretation generation in the background."""
    report = _get_owned_report(db, report_id, current_user.id)
    if not report.is_real_result or report.status != "completed" or not report.scores:
        raise HTTPException(status_code=400, detail="只有真实完成的大五人格报告才能生成 AI 详细解读")

    report.interpretation_status = "running"
    report.interpretation_error = None
    report.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(report)

    background_tasks.add_task(run_big_five_interpretation_in_background, report.id)
    return _to_report_response(report)


@router.get("/reports/{report_id}", response_model=BigFiveReportResponse)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BigFiveReportResponse:
    """Return one Big Five personality report."""
    report = _get_owned_report(db, report_id, current_user.id)
    if report.scores and (not report.quality_summary or not report.confidence_summary or not report.consistency_summary):
        quality_summary = build_modality_quality_summary(report.artifacts or {}, report.errors or [])
        report.quality_summary = report.quality_summary or quality_summary
        report.confidence_summary = report.confidence_summary or build_prediction_confidence_summary(
            scores=report.scores,
            quality_summary=quality_summary,
            is_real_result=bool(report.is_real_result),
            used_fallback=not bool(report.is_real_result),
        )
        atmr_summary = build_atmr_summary_for_session(db, report.source_assessment_session_id)
        report.consistency_summary = report.consistency_summary or build_consistency_summary(
            big_five_scores=report.scores,
            atmr_summary=atmr_summary,
        )
        report.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(report)
    return _to_report_response(report)


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a Big Five personality report record."""
    report = _get_owned_report(db, report_id, current_user.id)
    db.delete(report)
    db.commit()
    return {"status": "success"}
