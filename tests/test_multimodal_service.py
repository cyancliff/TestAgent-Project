from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.core.config import settings
from app.schemas.multimodal_personality import BigFiveScores
import app.services.multimodal_personality_service as multimodal_service_module
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


def test_real_inference_saves_micro_expression_artifact_and_bundle(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    video_path = tmp_path / "micro-demo.mp4"
    video_path.write_bytes(b"fake-video")
    task = service.create_task(video_path=str(video_path))

    artifact_dir = service._ensure_artifact_dir(task.task_id)
    frames_dir = artifact_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    audio_path = artifact_dir / "audio.wav"
    audio_path.write_bytes(b"audio")
    transcript_path = artifact_dir / "transcript.txt"
    transcript_path.write_text("hello micro expression", encoding="utf-8")
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    task.artifacts = {
        "artifact_dir": str(artifact_dir),
        "frames_dir": str(frames_dir),
        "audio_path": str(audio_path),
        "transcript_path": str(transcript_path),
        "manifest_path": str(manifest_path),
    }
    task.errors = []

    class FakeClipExtractor:
        def local_model_available(self):
            return True

        def extract_sample(self, *, sample, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{sample['video_name']}.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "image_features": [[0.1] * 768 for _ in range(15)],
                        "text_features": [0.2] * 768,
                    },
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    class FakeWav2ClipExtractor:
        def extract_sample(self, *, video_name, audio_path, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_name}.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "wav2clip_features": [[0.3] * 512 for _ in range(15)],
                    },
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    class FakeMicroExpressionExtractor:
        def extract_sample(self, *, video_name, video_path, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "micro_expression_feature.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "feature_vector": [0.1, 0.7, 0.2, 0.7, 0.8, 0.5, -0.1, 1.0],
                        "summary": {
                            "dominant_expression": "positive",
                            "dominant_label_zh": "积极",
                            "confidence": 0.7,
                        },
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    scores = {
        "openness": 0.61,
        "conscientiousness": 0.58,
        "extraversion": 0.54,
        "agreeableness": 0.57,
        "neuroticism": 0.49,
    }
    monkeypatch.setattr(service, "_checkpoint_exists", lambda: True)
    monkeypatch.setattr(service, "_get_clip_extractor", lambda: FakeClipExtractor())
    monkeypatch.setattr(service, "_get_wav2clip_extractor", lambda: FakeWav2ClipExtractor())
    monkeypatch.setattr(service, "_get_micro_expression_extractor", lambda: FakeMicroExpressionExtractor())
    monkeypatch.setattr(
        service,
        "_get_loaded_checkpoint",
        lambda: SimpleNamespace(
            model=object(),
            checkpoint={"feature_contract": {}, "model_kwargs": {"text_seq_len": 13}},
            device="cpu",
        ),
    )
    monkeypatch.setattr(
        multimodal_service_module,
        "evaluate_bundle_paths",
        lambda *args, **kwargs: SimpleNamespace(predictions=[SimpleNamespace(scores=scores)]),
    )

    result = service._run_real_inference(task)
    bundle_payload = json.loads(Path(result.artifacts["bundle_path"]).read_text(encoding="utf-8"))
    micro_payload = json.loads(Path(result.artifacts["micro_expression_feature_path"]).read_text(encoding="utf-8"))

    assert result.success is True
    assert result.scores.openness == 0.61
    assert Path(result.artifacts["micro_expression_feature_path"]).name == "micro_expression_feature.json"
    assert micro_payload["summary"]["dominant_label_zh"] == "积极"
    assert bundle_payload["micro_expression_features"] == micro_payload["feature_vector"]
    assert bundle_payload["metadata"]["has_micro_expression"] is True


def test_real_inference_keeps_real_prediction_when_micro_expression_fails(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    video_path = tmp_path / "micro-failure-demo.mp4"
    video_path.write_bytes(b"fake-video")
    task = service.create_task(video_path=str(video_path))

    artifact_dir = service._ensure_artifact_dir(task.task_id)
    frames_dir = artifact_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    audio_path = artifact_dir / "audio.wav"
    audio_path.write_bytes(b"audio")
    transcript_path = artifact_dir / "transcript.txt"
    transcript_path.write_text("hello micro expression", encoding="utf-8")
    manifest_path = artifact_dir / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    task.artifacts = {
        "artifact_dir": str(artifact_dir),
        "frames_dir": str(frames_dir),
        "audio_path": str(audio_path),
        "transcript_path": str(transcript_path),
        "manifest_path": str(manifest_path),
    }
    task.errors = []

    class FakeClipExtractor:
        def local_model_available(self):
            return True

        def extract_sample(self, *, sample, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{sample['video_name']}.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "image_features": [[0.1] * 768 for _ in range(15)],
                        "text_features": [0.2] * 768,
                    },
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    class FakeWav2ClipExtractor:
        def extract_sample(self, *, video_name, audio_path, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{video_name}.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": True,
                        "wav2clip_features": [[0.3] * 512 for _ in range(15)],
                    },
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=True, output_path=str(output_path), errors=[])

    class FailingMicroExpressionExtractor:
        def extract_sample(self, *, video_name, video_path, frames_dir, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / "micro_expression_feature.json"
            output_path.write_text(
                json.dumps(
                    {
                        "success": False,
                        "feature_vector": [0.0] * 8,
                        "summary": {"dominant_label_zh": "暂无", "confidence": 0.0},
                        "errors": ["MOL timeout"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(success=False, output_path=str(output_path), errors=["MOL timeout"])

    scores = {
        "openness": 0.66,
        "conscientiousness": 0.57,
        "extraversion": 0.52,
        "agreeableness": 0.55,
        "neuroticism": 0.44,
    }
    monkeypatch.setattr(service, "_checkpoint_exists", lambda: True)
    monkeypatch.setattr(service, "_get_clip_extractor", lambda: FakeClipExtractor())
    monkeypatch.setattr(service, "_get_wav2clip_extractor", lambda: FakeWav2ClipExtractor())
    monkeypatch.setattr(service, "_get_micro_expression_extractor", lambda: FailingMicroExpressionExtractor())
    monkeypatch.setattr(
        service,
        "_get_loaded_checkpoint",
        lambda: SimpleNamespace(
            model=object(),
            checkpoint={"feature_contract": {}, "model_kwargs": {"text_seq_len": 13}},
            device="cpu",
        ),
    )
    monkeypatch.setattr(
        multimodal_service_module,
        "evaluate_bundle_paths",
        lambda *args, **kwargs: SimpleNamespace(predictions=[SimpleNamespace(scores=scores)]),
    )

    result = service._run_real_inference(task)

    assert result.success is True
    assert result.used_fallback is False
    assert result.scores.openness == 0.66
    assert Path(result.artifacts["bundle_path"]).exists()
    assert Path(result.artifacts["micro_expression_feature_path"]).exists()
    assert "MOL timeout" in result.errors


def test_micro_expression_extractor_uses_configured_timeout(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "MOL_PYTHON_PATH", "")
    monkeypatch.setattr(settings, "MOL_ROOT_DIR", str(tmp_path / "MOL"))
    monkeypatch.setattr(settings, "MOL_MODEL_PATH", str(tmp_path / "MOL" / "model.pth"))
    monkeypatch.setattr(settings, "MOL_DEVICE", "cpu")
    monkeypatch.setattr(settings, "MICRO_EXPRESSION_TIMEOUT_SECONDS", 7)

    extractor = service._get_micro_expression_extractor()

    assert extractor.timeout_seconds == 7


def test_health_exposes_micro_expression_system_tools(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)

    health = service.health()

    assert "micro_expression_enabled" in health["system_tools"]
    assert "mol_root" in health["system_tools"]
    assert "mol_model" in health["system_tools"]


def test_health_requires_local_clip_model_for_model_ready(tmp_path, monkeypatch) -> None:
    service = _build_service(tmp_path, monkeypatch)
    monkeypatch.setattr(
        service._pipeline,
        "get_system_tools",
        lambda: {"ffmpeg": True, "ffprobe": True, "whisper": True},
    )
    monkeypatch.setattr(service, "_dependency_available", lambda module_name: True)
    monkeypatch.setattr(service, "_checkpoint_exists", lambda: True)
    monkeypatch.setattr(service, "_clip_model_available", lambda: False)

    health = service.health()

    assert health["system_tools"]["clip_model"] is False
    assert health["model_ready"] is False
