"""Scaffold pipeline for multimodal personality preprocessing and inference."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import importlib.util


@dataclass
class PipelineArtifacts:
    """Artifacts produced by the preprocessing and inference pipeline."""

    artifact_dir: str
    transcript_path: str
    manifest_path: str
    success: bool
    errors: list[str]


class MultimodalInferencePipeline:
    """Placeholder pipeline that will later host the real paper reproduction flow."""

    def __init__(self, model_version: str = "scaffold-v1") -> None:
        self.model_version = model_version
        self._whisper_model = None

    def _discover_binary(self, binary_name: str) -> str | None:
        """Find a binary from PATH or common Winget installation locations."""
        direct = shutil.which(binary_name)
        if direct:
            return direct

        local_app_data = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages"
        if local_app_data.exists():
            matches = sorted(local_app_data.glob(f"**/{binary_name}.exe"))
            if matches:
                return str(matches[0])
        return None

    def _check_system_tools(self) -> dict[str, bool]:
        """Report whether external tools needed by the real pipeline are available."""
        return {
            "ffmpeg": self._discover_binary("ffmpeg") is not None,
            "ffprobe": self._discover_binary("ffprobe") is not None,
            "whisper": importlib.util.find_spec("whisper") is not None,
        }

    def get_system_tools(self) -> dict[str, bool]:
        """Expose system tool availability to the service layer."""
        return self._check_system_tools()

    def _extract_frames(self, video_path: str, frames_dir: Path) -> tuple[bool, str | None]:
        """Extract 15 uniformly sampled frames using ffmpeg."""
        ffmpeg_bin = self._discover_binary("ffmpeg")
        if not ffmpeg_bin:
            return False, "ffmpeg is not installed or not in PATH"
        output_pattern = frames_dir / "frame_%03d.jpg"
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            video_path,
            "-vf",
            "select='not(mod(n,10))',scale=336:336",
            "-vsync",
            "vfr",
            "-frames:v",
            "15",
            str(output_pattern),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0:
            return False, result.stderr.strip() or "ffmpeg frame extraction failed"
        return True, None

    def _extract_audio(self, video_path: str, audio_path: Path) -> tuple[bool, str | None]:
        """Extract mono 16k wav audio using ffmpeg."""
        ffmpeg_bin = self._discover_binary("ffmpeg")
        if not ffmpeg_bin:
            return False, "ffmpeg is not installed or not in PATH"
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0:
            return False, result.stderr.strip() or "ffmpeg audio extraction failed"
        return True, None

    def _load_whisper_model(self):
        """Lazy-load the Whisper model used for local transcription."""
        if self._whisper_model is not None:
            return self._whisper_model
        import whisper

        self._whisper_model = whisper.load_model("tiny")
        return self._whisper_model

    def _transcribe_audio(self, audio_path: Path, transcript_path: Path) -> tuple[bool, str | None]:
        """Transcribe audio with a local Whisper model."""
        if importlib.util.find_spec("whisper") is None:
            return False, "whisper is not installed"
        try:
            ffmpeg_bin = self._discover_binary("ffmpeg")
            if ffmpeg_bin:
                ffmpeg_dir = str(Path(ffmpeg_bin).parent)
                current_path = os.environ.get("PATH", "")
                if ffmpeg_dir not in current_path.split(os.pathsep):
                    os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path
            model = self._load_whisper_model()
            result = model.transcribe(str(audio_path), fp16=False)
            text = (result.get("text") or "").strip()
            transcript_path.write_text(text + ("\n" if text else ""), encoding="utf-8")
            return True, None
        except Exception as exc:
            return False, f"whisper transcription failed: {exc}"

    def run(self, video_path: str, artifact_dir: str) -> PipelineArtifacts:
        """Run a placeholder preprocessing pipeline and emit basic artifacts."""
        artifact_root = Path(artifact_dir)
        artifact_root.mkdir(parents=True, exist_ok=True)
        frames_dir = artifact_root / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        audio_path = artifact_root / "audio.wav"

        transcript_path = artifact_root / "transcript.txt"
        manifest_path = artifact_root / "manifest.json"
        transcript_path.write_text("", encoding="utf-8")

        tools = self._check_system_tools()
        errors: list[str] = []
        stages = [
            {"name": "extract_frames", "status": "pending"},
            {"name": "extract_audio", "status": "pending"},
            {"name": "transcribe_audio", "status": "pending"},
            {"name": "extract_features", "status": "pending"},
            {"name": "run_model", "status": "pending"},
        ]

        if not Path(video_path).exists():
            errors.append(f"video not found: {video_path}")
            stages[0]["status"] = "failed"
            stages[1]["status"] = "failed"
            stages[2]["status"] = "blocked"
            stages[3]["status"] = "blocked"
            stages[4]["status"] = "blocked"
        elif not tools["ffmpeg"]:
            errors.append("ffmpeg is not installed or not in PATH")
            stages[0]["status"] = "failed"
            stages[1]["status"] = "failed"
            stages[2]["status"] = "blocked"
            stages[3]["status"] = "blocked"
            stages[4]["status"] = "blocked"
        else:
            frame_ok, frame_error = self._extract_frames(video_path=video_path, frames_dir=frames_dir)
            stages[0]["status"] = "completed" if frame_ok else "failed"
            if frame_error:
                errors.append(frame_error)

            audio_ok, audio_error = self._extract_audio(video_path=video_path, audio_path=audio_path)
            stages[1]["status"] = "completed" if audio_ok else "failed"
            if audio_error:
                errors.append(audio_error)

            if audio_ok:
                transcribe_ok, transcribe_error = self._transcribe_audio(audio_path=audio_path, transcript_path=transcript_path)
                stages[2]["status"] = "completed" if transcribe_ok else "failed"
                if transcribe_error:
                    errors.append(transcribe_error)
                    stages[3]["status"] = "blocked"
                    stages[4]["status"] = "blocked"
                else:
                    stages[3]["status"] = "pending"
                    stages[4]["status"] = "pending"
            else:
                stages[2]["status"] = "blocked"
                stages[3]["status"] = "blocked"
                stages[4]["status"] = "blocked"

        success = not errors
        manifest = {
            "video_path": video_path,
            "artifact_dir": str(artifact_root),
            "model_version": self.model_version,
            "system_tools": tools,
            "success": success,
            "errors": errors,
            "pipeline_stages": stages,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        return PipelineArtifacts(
            artifact_dir=str(artifact_root),
            transcript_path=str(transcript_path),
            manifest_path=str(manifest_path),
            success=success,
            errors=errors,
        )
