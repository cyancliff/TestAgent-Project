"""Background and scene-description association feature extraction."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from multimodal_personality.models.feature_bundle import BG_DIM


@dataclass
class BackgroundFeatureExtractionResult:
    """Result summary for one background feature extraction."""

    video_name: str
    success: bool
    output_path: str
    errors: list[str]


class BackgroundFeatureExtractor:
    """Derive a 256-d background/scene association descriptor from existing artifacts.

    The reference paper uses a scene-description association feature. This extractor
    implements a lightweight, reproducible surrogate from CLIP frame features, CLIP
    transcript features, optional wav2clip features, and transcript statistics.
    """

    feature_dim = BG_DIM
    schema_version = "bg-scene-association-v1"

    @staticmethod
    def _as_2d_array(values: Any) -> np.ndarray:
        if values is None:
            return np.empty((0, 0), dtype=np.float32)
        array = np.asarray(values, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.ndim != 2:
            return np.empty((0, 0), dtype=np.float32)
        return np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)

    @staticmethod
    def _normalize_rows(values: np.ndarray) -> np.ndarray:
        if values.size == 0:
            return values
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        norms[norms < 1e-12] = 1.0
        return values / norms

    @staticmethod
    def _take(values: np.ndarray, size: int) -> list[float]:
        flat = values.astype(np.float32).reshape(-1).tolist() if values.size else []
        if len(flat) >= size:
            return [float(value) for value in flat[:size]]
        return [float(value) for value in flat] + [0.0] * (size - len(flat))

    @staticmethod
    def _stats(values: np.ndarray) -> list[float]:
        if values.size == 0:
            return [0.0] * 8
        flat = values.reshape(-1)
        return [
            float(np.mean(flat)),
            float(np.std(flat)),
            float(np.min(flat)),
            float(np.max(flat)),
            float(np.median(flat)),
            float(np.quantile(flat, 0.25)),
            float(np.quantile(flat, 0.75)),
            float(np.mean(np.abs(flat))),
        ]

    @staticmethod
    def _transcript_stats(transcript: str) -> list[float]:
        text = transcript or ""
        words = re.findall(r"[A-Za-z']+", text)
        sentences = [part for part in re.split(r"[.!?。！？]+", text) if part.strip()]
        unique_words = {word.lower() for word in words}
        char_count = max(len(text), 1)
        word_count = max(len(words), 1)
        punctuation_count = sum(1 for char in text if char in ",.;:!?，。；：！？")
        digit_count = sum(1 for char in text if char.isdigit())
        upper_count = sum(1 for char in text if char.isupper())
        avg_word_len = sum(len(word) for word in words) / word_count
        return [
            min(len(text) / 5000.0, 1.0),
            min(len(words) / 1000.0, 1.0),
            min(len(sentences) / 100.0, 1.0),
            min(avg_word_len / 20.0, 1.0),
            len(unique_words) / word_count,
            punctuation_count / char_count,
            digit_count / char_count,
            upper_count / char_count,
        ]

    def _association_features(self, image_features: np.ndarray, text_features: np.ndarray) -> list[float]:
        if image_features.size == 0 or text_features.size == 0:
            return [0.0] * 32

        width = min(image_features.shape[1], text_features.shape[1])
        image = self._normalize_rows(image_features[:, :width])
        text = self._normalize_rows(text_features[:, :width])
        text_mean = self._normalize_rows(np.mean(text, axis=0, keepdims=True))

        frame_similarity = image @ text_mean.reshape(-1)
        matrix_similarity = image @ text.T
        sentence_similarity = np.mean(matrix_similarity, axis=0) if matrix_similarity.size else np.array([])

        values: list[float] = []
        values.extend(self._stats(frame_similarity))
        values.extend(self._take(frame_similarity, 15))
        values.extend(self._take(sentence_similarity, 9))
        return values[:32]

    def build_features(
        self,
        *,
        clip_payload: dict[str, Any],
        wav2clip_payload: dict[str, Any] | None = None,
        transcript: str = "",
    ) -> list[float]:
        """Build one 256-d descriptor from feature payloads."""

        image_features = self._as_2d_array(clip_payload.get("image_features"))
        text_features = self._as_2d_array(
            clip_payload.get("text_sequence_features") or clip_payload.get("text_features"),
        )
        wav_features = self._as_2d_array(
            None
            if wav2clip_payload is None
            else (
                wav2clip_payload.get("wav2clip_features")
                or wav2clip_payload.get("audio_features")
                or wav2clip_payload.get("features")
            ),
        )

        if image_features.size == 0:
            raise ValueError("image_features are required to derive bg_features")

        image = self._normalize_rows(image_features)
        text = self._normalize_rows(text_features)
        wav = self._normalize_rows(wav_features)

        image_mean = np.mean(image, axis=0)
        image_std = np.std(image, axis=0)
        if image.shape[0] > 1:
            image_motion = np.mean(np.abs(np.diff(image, axis=0)), axis=0)
        else:
            image_motion = np.zeros(image.shape[1], dtype=np.float32)

        text_mean = np.mean(text, axis=0) if text.size else np.array([], dtype=np.float32)
        wav_mean = np.mean(wav, axis=0) if wav.size else np.array([], dtype=np.float32)

        features: list[float] = []
        features.extend(self._take(image_mean, 64))
        features.extend(self._take(image_std, 32))
        features.extend(self._take(image_motion, 32))
        features.extend(self._take(text_mean, 64))
        features.extend(self._association_features(image_features, text_features))
        features.extend(self._take(wav_mean, 24))
        features.extend(self._transcript_stats(transcript))

        if len(features) != self.feature_dim:
            raise RuntimeError(f"bg feature size mismatch: {len(features)} != {self.feature_dim}")

        return [0.0 if not math.isfinite(value) else float(value) for value in features]

    def extract_sample(
        self,
        *,
        video_name: str,
        clip_payload: dict[str, Any],
        output_dir: str | Path,
        wav2clip_payload: dict[str, Any] | None = None,
        transcript: str = "",
    ) -> BackgroundFeatureExtractionResult:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / f"{video_name}.json"
        errors: list[str] = []

        try:
            bg_features = self.build_features(
                clip_payload=clip_payload,
                wav2clip_payload=wav2clip_payload,
                transcript=transcript,
            )
        except Exception as exc:
            errors.append(f"bg feature extraction failed: {exc}")
            output_path.write_text(
                json.dumps(
                    {
                        "video_name": video_name,
                        "success": False,
                        "schema_version": self.schema_version,
                        "feature_dim": self.feature_dim,
                        "errors": errors,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return BackgroundFeatureExtractionResult(
                video_name=video_name,
                success=False,
                output_path=str(output_path),
                errors=errors,
            )

        output_path.write_text(
            json.dumps(
                {
                    "video_name": video_name,
                    "success": True,
                    "schema_version": self.schema_version,
                    "feature_dim": self.feature_dim,
                    "bg_features": bg_features,
                    "sources": {
                        "clip": True,
                        "wav2clip": wav2clip_payload is not None,
                        "transcript": bool(transcript.strip()),
                    },
                    "errors": [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return BackgroundFeatureExtractionResult(
            video_name=video_name,
            success=True,
            output_path=str(output_path),
            errors=[],
        )

