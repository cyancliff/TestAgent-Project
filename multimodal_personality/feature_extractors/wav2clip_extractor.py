"""wav2clip-based audio feature extraction helpers."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import importlib.util

import numpy as np


@dataclass
class AudioFeatureExtractionResult:
    """Result summary for one audio feature extraction job."""

    video_name: str
    success: bool
    output_path: str
    errors: list[str]


class Wav2ClipFeatureExtractor:
    """Feature extraction wrapper for wav2clip audio embeddings."""

    def __init__(self, segment_count: int = 15, feature_dim: int = 512) -> None:
        self.segment_count = segment_count
        self.feature_dim = feature_dim

    def availability(self) -> dict[str, bool]:
        """Report whether the local environment can run wav2clip extraction."""
        return {
            "wav2clip": importlib.util.find_spec("wav2clip") is not None,
            "librosa": importlib.util.find_spec("librosa") is not None,
            "numpy": importlib.util.find_spec("numpy") is not None,
        }

    @staticmethod
    def _write_payload(output_path: Path, payload: dict[str, Any]) -> None:
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _write_failure(
        self,
        *,
        output_path: Path,
        video_name: str,
        audio_path: str,
        errors: list[str],
        availability: dict[str, bool],
    ) -> AudioFeatureExtractionResult:
        self._write_payload(
            output_path,
            {
                "video_name": video_name,
                "audio_path": audio_path,
                "success": False,
                "errors": errors,
                "availability": availability,
            },
        )
        return AudioFeatureExtractionResult(
            video_name=video_name,
            success=False,
            output_path=str(output_path),
            errors=errors,
        )

    def _load_audio(self, audio_path: str | Path) -> tuple[np.ndarray, int]:
        import librosa

        audio, sample_rate = librosa.load(str(audio_path), sr=None, mono=True)
        return np.asarray(audio, dtype=np.float32), int(sample_rate)

    def _patch_librosa_frame_signature(self) -> None:
        """Adapt wav2clip's legacy positional call style to newer librosa versions."""
        import librosa

        frame_fn = librosa.util.frame
        signature = inspect.signature(frame_fn)
        parameters = list(signature.parameters.values())
        if len(parameters) < 3 or parameters[1].kind is not inspect.Parameter.KEYWORD_ONLY:
            return

        def compat_frame(
            x: np.ndarray,
            frame_length: int | None = None,
            hop_length: int | None = None,
            *args: Any,
            **kwargs: Any,
        ) -> np.ndarray:
            local_frame_length = frame_length
            local_hop_length = hop_length
            if args:
                if local_frame_length is None and len(args) >= 1:
                    local_frame_length = args[0]
                if local_hop_length is None and len(args) >= 2:
                    local_hop_length = args[1]

            if local_frame_length is None or local_hop_length is None:
                return frame_fn(x, **kwargs)

            return frame_fn(
                x,
                frame_length=int(local_frame_length),
                hop_length=int(local_hop_length),
                **kwargs,
            )

        librosa.util.frame = compat_frame

    def _embed_audio(self, audio: np.ndarray) -> np.ndarray:
        self._patch_librosa_frame_signature()
        import wav2clip

        frame_length = max(int(audio.shape[0] // self.segment_count), 1)
        model = wav2clip.get_model(frame_length=frame_length, hop_length=frame_length)
        embeddings = wav2clip.embed_audio(audio, model)
        return np.asarray(embeddings, dtype=np.float32)

    def _normalize_embeddings(self, embeddings: np.ndarray) -> tuple[list[list[float]], int]:
        array = np.asarray(embeddings, dtype=np.float32).squeeze()
        if array.ndim != 2:
            raise ValueError(f"Expected a 2D wav2clip embedding matrix, received shape={array.shape!r}")

        if array.shape[1] == self.feature_dim:
            sequence = array
        elif array.shape[0] == self.feature_dim:
            sequence = np.swapaxes(array, 0, 1)
        else:
            raise ValueError(
                f"Unable to infer wav2clip feature dimension {self.feature_dim} from shape {array.shape!r}",
            )

        original_segment_count = int(sequence.shape[0])
        if original_segment_count > self.segment_count:
            sequence = sequence[: self.segment_count]
        elif original_segment_count < self.segment_count:
            padding = np.zeros((self.segment_count - original_segment_count, self.feature_dim), dtype=np.float32)
            sequence = np.vstack([sequence, padding])

        return sequence.tolist(), original_segment_count

    def extract_sample(
        self,
        *,
        video_name: str,
        audio_path: str | Path,
        output_dir: str | Path,
    ) -> AudioFeatureExtractionResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{video_name}.json"
        audio_path = str(audio_path)
        errors: list[str] = []

        availability = self.availability()
        if not all(availability.values()):
            missing = [name for name, ok in availability.items() if not ok]
            errors.append(f"missing dependencies: {', '.join(missing)}")
            return self._write_failure(
                output_path=output_path,
                video_name=video_name,
                audio_path=audio_path,
                errors=errors,
                availability=availability,
            )

        if not Path(audio_path).exists():
            errors.append(f"audio not found: {audio_path}")
            return self._write_failure(
                output_path=output_path,
                video_name=video_name,
                audio_path=audio_path,
                errors=errors,
                availability=availability,
            )

        try:
            audio, sample_rate = self._load_audio(audio_path)
            embeddings = self._embed_audio(audio)
            wav2clip_features, original_segment_count = self._normalize_embeddings(embeddings)
        except Exception as exc:
            errors.append(f"wav2clip extraction failed: {exc}")
            return self._write_failure(
                output_path=output_path,
                video_name=video_name,
                audio_path=audio_path,
                errors=errors,
                availability=availability,
            )

        payload = {
            "video_name": video_name,
            "audio_path": audio_path,
            "success": True,
            "model_name": "wav2clip",
            "segment_count": self.segment_count,
            "original_segment_count": original_segment_count,
            "audio_feature_dim": self.feature_dim,
            "sample_rate": sample_rate,
            "wav2clip_features": wav2clip_features,
            "errors": [],
        }
        self._write_payload(output_path, payload)
        return AudioFeatureExtractionResult(
            video_name=video_name,
            success=True,
            output_path=str(output_path),
            errors=[],
        )
