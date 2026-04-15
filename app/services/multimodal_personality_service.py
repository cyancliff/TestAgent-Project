"""Service layer for the standalone multimodal personality scaffold."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.core.config import settings
from app.schemas.multimodal_personality import BigFiveScores

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from multimodal_personality.inference.pipeline import MultimodalInferencePipeline


@dataclass
class MultimodalTaskRecord:
    """In-memory task record used by the scaffold service."""

    task_id: str
    status: str
    message: str
    video_path: str
    session_id: Optional[int]
    model_version: str
    scores: Optional[BigFiveScores]
    artifacts: dict[str, str]
    errors: list[str]
    created_at: datetime
    updated_at: datetime


class MultimodalPersonalityService:
    """Temporary in-memory service before DB-backed persistence is added."""

    _MODEL_VERSION = "scaffold-v1"

    def __init__(self) -> None:
        self._tasks: dict[str, MultimodalTaskRecord] = {}
        self._lock = Lock()
        self._root_dir = Path(settings.MULTIMODAL_ROOT_DIR)
        self._video_dir = Path(settings.MULTIMODAL_VIDEO_DIR)
        self._task_dir = Path(settings.MULTIMODAL_TASK_DIR)
        self._artifact_dir = Path(settings.MULTIMODAL_ARTIFACT_DIR)
        for path in (self._root_dir, self._video_dir, self._task_dir, self._artifact_dir):
            path.mkdir(parents=True, exist_ok=True)
        self._pipeline = MultimodalInferencePipeline(model_version=self._MODEL_VERSION)
        self._load_existing_tasks()

    def _task_file(self, task_id: str) -> Path:
        return self._task_dir / f"{task_id}.json"

    def _serialize_task(self, task: MultimodalTaskRecord) -> dict[str, object]:
        return {
            "task_id": task.task_id,
            "status": task.status,
            "message": task.message,
            "video_path": task.video_path,
            "session_id": task.session_id,
            "model_version": task.model_version,
            "scores": task.scores.model_dump() if task.scores else None,
            "artifacts": task.artifacts,
            "errors": task.errors,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }

    def _persist_task(self, task: MultimodalTaskRecord) -> None:
        self._task_file(task.task_id).write_text(
            json.dumps(self._serialize_task(task), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _deserialize_task(self, payload: dict[str, object]) -> MultimodalTaskRecord:
        scores_payload = payload.get("scores")
        scores = BigFiveScores(**scores_payload) if isinstance(scores_payload, dict) else None
        return MultimodalTaskRecord(
            task_id=str(payload["task_id"]),
            status=str(payload["status"]),
            message=str(payload["message"]),
            video_path=str(payload["video_path"]),
            session_id=payload.get("session_id"),
            model_version=str(payload.get("model_version", self._MODEL_VERSION)),
            scores=scores,
            artifacts=dict(payload.get("artifacts", {})),
            errors=list(payload.get("errors", [])),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            updated_at=datetime.fromisoformat(str(payload["updated_at"])),
        )

    def _load_existing_tasks(self) -> None:
        for task_file in self._task_dir.glob("*.json"):
            try:
                payload = json.loads(task_file.read_text(encoding="utf-8"))
                task = self._deserialize_task(payload)
                self._tasks[task.task_id] = task
            except Exception:
                continue

    def save_uploaded_video(
        self,
        filename: str,
        content: bytes,
        session_id: Optional[int] = None,
    ) -> MultimodalTaskRecord:
        """Persist an uploaded video file and register a task."""
        suffix = Path(filename).suffix or ".mp4"
        stored_name = f"{uuid4().hex}{suffix}"
        stored_path = self._video_dir / stored_name
        stored_path.write_bytes(content)
        return self.create_task(
            video_path=str(stored_path),
            session_id=session_id,
            original_filename=filename,
        )

    def create_task(
        self,
        video_path: str,
        session_id: Optional[int] = None,
        original_filename: Optional[str] = None,
    ) -> MultimodalTaskRecord:
        """Register a task for a local video path."""
        normalized_path = str(Path(video_path))
        now = datetime.now(timezone.utc)
        message = "任务已创建，等待执行多模态人格分析。"
        if original_filename:
            message = f"任务已创建，已接收视频文件 {original_filename}。"
        task = MultimodalTaskRecord(
            task_id=uuid4().hex,
            status="pending",
            message=message,
            video_path=normalized_path,
            session_id=session_id,
            model_version=self._MODEL_VERSION,
            scores=None,
            artifacts={},
            errors=[],
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._tasks[task.task_id] = task
            self._persist_task(task)
        return task

    def _ensure_artifact_dir(self, task_id: str) -> Path:
        artifact_dir = self._artifact_dir / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _run_placeholder_pipeline(self, task: MultimodalTaskRecord) -> bool:
        artifact_dir = self._ensure_artifact_dir(task.task_id)
        pipeline_artifacts = self._pipeline.run(video_path=task.video_path, artifact_dir=str(artifact_dir))
        task.artifacts = {
            "artifact_dir": pipeline_artifacts.artifact_dir,
            "transcript_path": pipeline_artifacts.transcript_path,
            "manifest_path": pipeline_artifacts.manifest_path,
        }
        task.errors = list(pipeline_artifacts.errors)
        return pipeline_artifacts.success

    def run_task(self, task_id: str, force_restart: bool = False) -> MultimodalTaskRecord:
        """Execute a placeholder multimodal analysis flow."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)

            if task.status == "completed" and not force_restart:
                return task

            task.status = "running"
            task.message = "正在执行占位版多模态人格分析流程。"
            task.updated_at = datetime.now(timezone.utc)
            self._persist_task(task)

            pipeline_ok = self._run_placeholder_pipeline(task)
            if pipeline_ok:
                task.scores = BigFiveScores(
                    openness=0.50,
                    conscientiousness=0.50,
                    extraversion=0.50,
                    agreeableness=0.50,
                    neuroticism=0.50,
                )
                task.status = "completed"
                task.message = "预处理完成，当前仍为占位版分数，下一步将替换为真实模型推理。"
            else:
                task.scores = None
                task.status = "failed"
                task.message = "预处理失败，请先补齐音视频依赖后再重试。"
            task.updated_at = datetime.now(timezone.utc)
            self._persist_task(task)
            return task

    def get_task(self, task_id: str) -> MultimodalTaskRecord:
        """Return a task record by identifier."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)
            return task

    def health(self) -> dict[str, object]:
        """Return the scaffold health information."""
        with self._lock:
            task_count = len(self._tasks)
        return {
            "status": "ok",
            "module": "multimodal_personality",
            "model_ready": False,
            "task_count": task_count,
            "system_tools": self._pipeline.get_system_tools(),
        }


service = MultimodalPersonalityService()
