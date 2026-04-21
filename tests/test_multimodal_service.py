from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.schemas.multimodal_personality import BigFiveScores
from app.services.multimodal_personality_service import (
    MultimodalPersonalityService,
    MultimodalPredictionResult,
)


def _build_service(tmp_path, monkeypatch) -> MultimodalPersonalityService:
    root_dir = tmp_path / "uploads" / "multimodal_personality"
    checkpoint_path = tmp_path / "checkpoints" / "agtn_mtl_full.pt"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(b"checkpoint-placeholder")

    monkeypatch.setattr(settings, "MULTIMODAL_ROOT_DIR", str(root_dir))
    monkeypatch.setattr(settings, "MULTIMODAL_VIDEO_DIR", str(root_dir / "videos"))
    monkeypatch.setattr(settings, "MULTIMODAL_TASK_DIR", str(root_dir / "tasks"))
    monkeypatch.setattr(settings, "MULTIMODAL_ARTIFACT_DIR", str(root_dir / "artifacts"))
    monkeypatch.setattr(settings, "MULTIMODAL_CHECKPOINT_PATH", str(checkpoint_path))
    monkeypatch.setattr(settings, "MULTIMODAL_DEVICE", "cpu")
    return MultimodalPersonalityService()


def _install_fake_preprocess(service: MultimodalPersonalityService, monkeypatch) -> None:
    def fake_preprocess(task) -> bool:
        artifact_dir = service._ensure_artifact_dir(task.task_id)
        transcript_path = artifact_dir / "transcript.txt"
        manifest_path = artifact_dir / "manifest.json"
        transcript_path.write_text("hello multimodal world\n", encoding="utf-8")
        manifest_path.write_text(json.dumps({"task_id": task.task_id}), encoding="utf-8")
        task.artifacts = {
            "artifact_dir": str(artifact_dir),
            "frames_dir": str(artifact_dir / "frames"),
            "audio_path": str(artifact_dir / "audio.wav"),
            "transcript_path": str(transcript_path),
            "manifest_path": str(manifest_path),
        }
        task.errors = []
        return True

    monkeypatch.setattr(service, "_run_placeholder_pipeline", fake_preprocess)


def test_run_task_updates_task_with_real_prediction(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    _install_fake_preprocess(service, monkeypatch)

    def fake_inference(task) -> MultimodalPredictionResult:
        return MultimodalPredictionResult(
            success=True,
            model_version=service._REAL_MODEL_VERSION,
            scores=BigFiveScores(
                openness=0.61,
                conscientiousness=0.58,
                extraversion=0.54,
                agreeableness=0.57,
                neuroticism=0.49,
            ),
            artifacts={
                **task.artifacts,
                "bundle_path": str(Path(task.artifacts["artifact_dir"]) / "bundle.json"),
            },
            errors=[],
            used_fallback=False,
        )

    monkeypatch.setattr(service, "_run_real_inference", fake_inference)

    video_path = tmp_path / "demo.mp4"
    video_path.write_bytes(b"fake-video")
    task = service.create_task(video_path=str(video_path))
    result = service.run_task(task.task_id)

    assert result.status == "completed"
    assert result.model_version == service._REAL_MODEL_VERSION
    assert result.scores is not None
    assert result.scores.openness == 0.61
    assert result.artifacts["bundle_path"].endswith("bundle.json")
    assert "真实模型" in result.message
    assert result.errors == []


def test_run_task_keeps_completed_status_when_falling_back(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    _install_fake_preprocess(service, monkeypatch)

    def fake_inference(task) -> MultimodalPredictionResult:
        return MultimodalPredictionResult(
            success=True,
            model_version=service._FALLBACK_MODEL_VERSION,
            scores=service._build_scaffold_scores(),
            artifacts=task.artifacts,
            errors=["checkpoint unavailable"],
            used_fallback=True,
        )

    monkeypatch.setattr(service, "_run_real_inference", fake_inference)

    video_path = tmp_path / "fallback.mp4"
    video_path.write_bytes(b"fake-video")
    task = service.create_task(video_path=str(video_path))
    result = service.run_task(task.task_id)

    assert result.status == "completed"
    assert result.model_version == service._FALLBACK_MODEL_VERSION
    assert result.scores == service._build_scaffold_scores()
    assert "回退" in result.message
    assert result.errors == ["checkpoint unavailable"]
