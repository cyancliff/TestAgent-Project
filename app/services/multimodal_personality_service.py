"""Service layer for standalone multimodal personality analysis."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from app.core.config import settings
from app.schemas.multimodal_personality import BigFiveScores

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    import torch
except ImportError:  # pragma: no cover - exercised through availability checks
    torch = None

from multimodal_personality.feature_extractors.clip_extractor import ClipFeatureExtractor
from multimodal_personality.feature_extractors.wav2clip_extractor import Wav2ClipFeatureExtractor
from multimodal_personality.inference.pipeline import MultimodalInferencePipeline
from multimodal_personality.models.feature_bundle import MultimodalFeatureBundle
from multimodal_personality.training.baseline import LoadedCheckpoint, evaluate_bundle_paths, load_checkpoint_model


@dataclass
class MultimodalTaskRecord:
    """Task record persisted to the local task directory."""

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


@dataclass
class MultimodalPredictionResult:
    """Prediction outcome produced after preprocessing succeeds."""

    success: bool
    model_version: str
    scores: BigFiveScores
    artifacts: dict[str, str]
    errors: list[str]
    used_fallback: bool = False


class MultimodalPersonalityService:
    """Local-file-backed service for multimodal personality analysis."""

    _SCAFFOLD_MODEL_VERSION = "scaffold-v1"
    _FALLBACK_MODEL_VERSION = "scaffold-fallback"
    _REAL_MODEL_VERSION = "agtn-mtl-full-baseline"

    def __init__(self) -> None:
        self._tasks: dict[str, MultimodalTaskRecord] = {}
        self._lock = Lock()
        self._root_dir = self._resolve_project_path(settings.MULTIMODAL_ROOT_DIR)
        self._video_dir = self._resolve_project_path(settings.MULTIMODAL_VIDEO_DIR)
        self._task_dir = self._resolve_project_path(settings.MULTIMODAL_TASK_DIR)
        self._artifact_dir = self._resolve_project_path(settings.MULTIMODAL_ARTIFACT_DIR)
        self._checkpoint_path = self._resolve_project_path(settings.MULTIMODAL_CHECKPOINT_PATH)
        self._runtime_device = self._resolve_runtime_device(settings.MULTIMODAL_DEVICE)

        for path in (self._root_dir, self._video_dir, self._task_dir, self._artifact_dir):
            path.mkdir(parents=True, exist_ok=True)

        self._pipeline = MultimodalInferencePipeline(model_version=self._SCAFFOLD_MODEL_VERSION)
        self._clip_extractor: ClipFeatureExtractor | None = None
        self._wav2clip_extractor: Wav2ClipFeatureExtractor | None = None
        self._loaded_checkpoint: LoadedCheckpoint | None = None
        self._load_existing_tasks()

    @staticmethod
    def _resolve_project_path(path_value: str | Path) -> Path:
        candidate = Path(path_value)
        if candidate.is_absolute():
            return candidate
        return PROJECT_ROOT / candidate

    @staticmethod
    def _dependency_available(module_name: str) -> bool:
        return importlib.util.find_spec(module_name) is not None

    @staticmethod
    def _resolve_runtime_device(device_name: str):
        if torch is None:
            return "cpu"

        requested = (device_name or "auto").strip().lower()
        if requested == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if requested.startswith("cuda") and not torch.cuda.is_available():
            return torch.device("cpu")
        return torch.device(requested)

    @staticmethod
    def _build_scaffold_scores() -> BigFiveScores:
        return BigFiveScores(
            openness=0.50,
            conscientiousness=0.50,
            extraversion=0.50,
            agreeableness=0.50,
            neuroticism=0.50,
        )

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
            model_version=str(payload.get("model_version", self._SCAFFOLD_MODEL_VERSION)),
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

    def _read_json(self, path: str | Path) -> dict[str, Any]:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))

    def _checkpoint_exists(self) -> bool:
        return self._checkpoint_path.exists()

    def _get_clip_extractor(self) -> ClipFeatureExtractor:
        if self._clip_extractor is None:
            self._clip_extractor = ClipFeatureExtractor(
                device=str(self._runtime_device),
                max_sentences=13,
            )
        return self._clip_extractor

    def _get_wav2clip_extractor(self) -> Wav2ClipFeatureExtractor:
        if self._wav2clip_extractor is None:
            self._wav2clip_extractor = Wav2ClipFeatureExtractor(segment_count=15, feature_dim=512)
        return self._wav2clip_extractor

    def _get_loaded_checkpoint(self) -> LoadedCheckpoint:
        if self._loaded_checkpoint is None:
            self._loaded_checkpoint = load_checkpoint_model(
                self._checkpoint_path,
                device=self._runtime_device,
            )
        return self._loaded_checkpoint

    def _fallback_prediction(
        self,
        *,
        errors: list[str],
        artifacts: dict[str, str],
    ) -> MultimodalPredictionResult:
        return MultimodalPredictionResult(
            success=True,
            model_version=self._FALLBACK_MODEL_VERSION,
            scores=self._build_scaffold_scores(),
            artifacts=artifacts,
            errors=errors,
            used_fallback=True,
        )

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
            model_version=self._SCAFFOLD_MODEL_VERSION,
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
        frames_dir = artifact_dir / "frames"
        audio_path = artifact_dir / "audio.wav"
        pipeline_artifacts = self._pipeline.run(video_path=task.video_path, artifact_dir=str(artifact_dir))
        task.artifacts = {
            "artifact_dir": pipeline_artifacts.artifact_dir,
            "frames_dir": str(frames_dir),
            "audio_path": str(audio_path),
            "transcript_path": pipeline_artifacts.transcript_path,
            "manifest_path": pipeline_artifacts.manifest_path,
        }
        task.errors = list(pipeline_artifacts.errors)
        return pipeline_artifacts.success

    def _run_real_inference(self, task: MultimodalTaskRecord) -> MultimodalPredictionResult:
        artifacts = dict(task.artifacts)
        errors = list(task.errors)

        if not self._checkpoint_exists():
            errors.append(f"checkpoint not found: {self._checkpoint_path}")
            return self._fallback_prediction(errors=errors, artifacts=artifacts)

        artifact_dir = Path(artifacts["artifact_dir"])
        frames_dir = artifact_dir / "frames"
        audio_path = artifact_dir / "audio.wav"
        transcript_path = artifact_dir / "transcript.txt"
        feature_root = artifact_dir / "features"
        clip_feature_dir = feature_root / "clip"
        wav2clip_feature_dir = feature_root / "wav2clip"
        bundle_path = artifact_dir / "bundle.json"

        transcript = transcript_path.read_text(encoding="utf-8", errors="ignore") if transcript_path.exists() else ""
        video_name = Path(task.video_path).name
        sample = {
            "video_name": video_name,
            "video_path": task.video_path,
            "transcript": transcript,
        }

        try:
            clip_result = self._get_clip_extractor().extract_sample(
                sample=sample,
                frames_dir=frames_dir,
                output_dir=clip_feature_dir,
            )
            artifacts["clip_feature_path"] = clip_result.output_path
            errors.extend(clip_result.errors)
            if not clip_result.success:
                return self._fallback_prediction(errors=errors, artifacts=artifacts)

            clip_payload = self._read_json(clip_result.output_path)

            wav2clip_payload = None
            if audio_path.exists():
                wav2clip_result = self._get_wav2clip_extractor().extract_sample(
                    video_name=video_name,
                    audio_path=audio_path,
                    output_dir=wav2clip_feature_dir,
                )
                artifacts["wav2clip_feature_path"] = wav2clip_result.output_path
                errors.extend(wav2clip_result.errors)
                if wav2clip_result.success:
                    wav2clip_payload = self._read_json(wav2clip_result.output_path)
            else:
                errors.append(f"audio artifact missing: {audio_path}")

            bundle = MultimodalFeatureBundle.from_current_artifacts(
                sample=sample,
                clip_payload=clip_payload,
                wav2clip_payload=wav2clip_payload,
                bg_payload=None,
            )
            bundle.write_json(bundle_path)
            artifacts["bundle_path"] = str(bundle_path)

            loaded = self._get_loaded_checkpoint()
            model_kwargs = dict(loaded.checkpoint.get("model_kwargs", {}))
            text_seq_len = int(model_kwargs.get("text_seq_len", 13))
            inference_result = evaluate_bundle_paths(
                loaded.model,
                [bundle_path],
                device=loaded.device,
                batch_size=1,
                text_seq_len=text_seq_len,
                fill_missing_modalities=True,
                require_labels=False,
            )
            if not inference_result.predictions:
                errors.append("checkpoint inference returned no predictions")
                return self._fallback_prediction(errors=errors, artifacts=artifacts)

            scores = BigFiveScores(**inference_result.predictions[0].scores)
            return MultimodalPredictionResult(
                success=True,
                model_version=self._REAL_MODEL_VERSION,
                scores=scores,
                artifacts=artifacts,
                errors=errors,
                used_fallback=False,
            )
        except Exception as exc:
            errors.append(f"real inference failed: {exc}")
            return self._fallback_prediction(errors=errors, artifacts=artifacts)

    def run_task(self, task_id: str, force_restart: bool = False) -> MultimodalTaskRecord:
        """Run preprocessing and, when available, real checkpoint inference."""
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise KeyError(task_id)

            if task.status == "completed" and not force_restart:
                return task

            task.status = "running"
            task.message = "正在执行多模态预处理和模型推理。"
            task.updated_at = datetime.now(timezone.utc)
            self._persist_task(task)

        pipeline_ok = self._run_placeholder_pipeline(task)
        if pipeline_ok:
            prediction = self._run_real_inference(task)
            task.scores = prediction.scores
            task.artifacts = prediction.artifacts
            task.errors = prediction.errors
            task.model_version = prediction.model_version
            task.status = "completed" if prediction.success else "failed"
            if prediction.used_fallback:
                task.message = "预处理完成，但真实模型不可用，已回退到占位分数。"
            else:
                task.message = "多模态分析完成，已返回真实模型预测结果。"
        else:
            task.scores = None
            task.model_version = self._SCAFFOLD_MODEL_VERSION
            task.status = "failed"
            task.message = "预处理失败，请检查输入视频与本地依赖后重试。"

        task.updated_at = datetime.now(timezone.utc)
        with self._lock:
            self._tasks[task.task_id] = task
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
        """Return health information for the multimodal subsystem."""
        with self._lock:
            task_count = len(self._tasks)

        system_tools = {
            **self._pipeline.get_system_tools(),
            "torch": self._dependency_available("torch"),
            "transformers": self._dependency_available("transformers"),
            "pil": self._dependency_available("PIL"),
            "wav2clip": self._dependency_available("wav2clip"),
            "librosa": self._dependency_available("librosa"),
            "checkpoint": self._checkpoint_exists(),
            "cuda": bool(torch is not None and torch.cuda.is_available()),
        }
        model_ready = all(
            (
                system_tools["ffmpeg"],
                system_tools["whisper"],
                system_tools["torch"],
                system_tools["transformers"],
                system_tools["pil"],
                system_tools["checkpoint"],
            ),
        )
        return {
            "status": "ok",
            "module": "multimodal_personality",
            "model_ready": model_ready,
            "task_count": task_count,
            "system_tools": system_tools,
        }


service = MultimodalPersonalityService()
