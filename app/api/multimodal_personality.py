"""Standalone API endpoints for multimodal personality analysis."""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.multimodal_personality import (
    MultimodalHealthResponse,
    MultimodalRunRequest,
    MultimodalTaskResponse,
    MultimodalUploadRequest,
)
from app.services.multimodal_personality_service import service

router = APIRouter()


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


@router.get("/health", response_model=MultimodalHealthResponse)
async def health() -> MultimodalHealthResponse:
    """Check whether the multimodal subsystem is reachable."""
    return MultimodalHealthResponse(**service.health())


@router.post("/upload", response_model=MultimodalTaskResponse)
async def upload(payload: MultimodalUploadRequest) -> MultimodalTaskResponse:
    """Register a local video path for later multimodal analysis."""
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
) -> MultimodalTaskResponse:
    """Persist an uploaded video file and register a task."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="上传文件必须包含文件名")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件不能为空")
    task = service.save_uploaded_video(filename=file.filename, content=content, session_id=session_id)
    return _to_response(task)


@router.post("/run", response_model=MultimodalTaskResponse)
async def run(payload: MultimodalRunRequest) -> MultimodalTaskResponse:
    """Run the scaffold multimodal pipeline for an existing task."""
    try:
        task = service.run_task(task_id=payload.task_id, force_restart=payload.force_restart)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="多模态分析任务不存在") from exc
    return _to_response(task)


@router.get("/result/{task_id}", response_model=MultimodalTaskResponse)
async def result(task_id: str) -> MultimodalTaskResponse:
    """Return the current task status and, if available, prediction scores."""
    try:
        task = service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="多模态分析任务不存在") from exc
    return _to_response(task)
