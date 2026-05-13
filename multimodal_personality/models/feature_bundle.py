"""Feature bundle contract for the reference-style multimodal model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import torch


FRAME_COUNT = 15
CLIP_VIDEO_DIM = 768
WAV2CLIP_DIM = 512
CLIP_TEXT_DIM = 768
BG_DIM = 256
MICRO_EXPRESSION_DIM = 8
TRAIT_DIM = 5
TRAIT_ORDER = [
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
]


def _ensure_2d_sequence(values: list[Any], feature_dim: int, field_name: str) -> list[list[float]]:
    if not values:
        return []

    first = values[0]
    if isinstance(first, (int, float)):
        if len(values) != feature_dim:
            msg = f"{field_name} expected a 1D vector with {feature_dim} values, received {len(values)}"
            raise ValueError(msg)
        return [[float(value) for value in values]]

    sequence = []
    for row in values:
        if len(row) != feature_dim:
            msg = f"{field_name} expected rows of size {feature_dim}, received row of size {len(row)}"
            raise ValueError(msg)
        sequence.append([float(value) for value in row])
    return sequence


def _ensure_1d_vector(values: list[Any], feature_dim: int, field_name: str) -> list[float]:
    if len(values) != feature_dim:
        msg = f"{field_name} expected {feature_dim} values, received {len(values)}"
        raise ValueError(msg)
    return [float(value) for value in values]


def _pad_or_truncate_rows(values: list[list[float]], target_rows: int, feature_dim: int) -> list[list[float]]:
    normalized = [row[:feature_dim] for row in values[:target_rows]]
    padding = [[0.0] * feature_dim for _ in range(max(target_rows - len(normalized), 0))]
    return normalized + padding


@dataclass
class MultimodalFeatureBundle:
    """Serializable container for the four model inputs plus optional labels."""

    video_name: str
    video_path: str = ""
    labels: list[float] | None = None
    clip_video: list[list[float]] = field(default_factory=list)
    clip_text: list[list[float]] = field(default_factory=list)
    wav2clip: list[list[float]] | None = None
    bg_features: list[float] | None = None
    micro_expression_features: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if self.labels is not None:
            self.labels = _ensure_1d_vector(self.labels, TRAIT_DIM, "labels")

        self.clip_video = _ensure_2d_sequence(self.clip_video, CLIP_VIDEO_DIM, "clip_video")
        if not self.clip_video:
            raise ValueError("clip_video cannot be empty")

        self.clip_text = _ensure_2d_sequence(self.clip_text, CLIP_TEXT_DIM, "clip_text")

        if self.wav2clip is not None:
            self.wav2clip = _ensure_2d_sequence(self.wav2clip, WAV2CLIP_DIM, "wav2clip")
        if self.bg_features is not None:
            self.bg_features = _ensure_1d_vector(self.bg_features, BG_DIM, "bg_features")
        if self.micro_expression_features is not None:
            self.micro_expression_features = _ensure_1d_vector(
                self.micro_expression_features,
                MICRO_EXPRESSION_DIM,
                "micro_expression_features",
            )

    def to_serializable(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)

    def write_json(self, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_serializable(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def to_tensors(
        self,
        *,
        text_seq_len: int = 13,
        frame_count: int = FRAME_COUNT,
        fill_missing_modalities: bool = True,
    ) -> dict[str, torch.Tensor]:
        self.validate()

        clip_video = torch.tensor(
            _pad_or_truncate_rows(self.clip_video, target_rows=frame_count, feature_dim=CLIP_VIDEO_DIM),
            dtype=torch.float32,
        )

        clip_text = self.clip_text or ([[0.0] * CLIP_TEXT_DIM] if fill_missing_modalities else [])
        if not clip_text:
            raise ValueError("clip_text is missing and fill_missing_modalities=False")
        clip_text = torch.tensor(
            _pad_or_truncate_rows(clip_text, target_rows=text_seq_len, feature_dim=CLIP_TEXT_DIM),
            dtype=torch.float32,
        )

        wav2clip = self.wav2clip
        if wav2clip is None:
            if not fill_missing_modalities:
                raise ValueError("wav2clip is missing and fill_missing_modalities=False")
            wav2clip = [[0.0] * WAV2CLIP_DIM for _ in range(frame_count)]
        wav2clip = torch.tensor(
            _pad_or_truncate_rows(wav2clip, target_rows=frame_count, feature_dim=WAV2CLIP_DIM),
            dtype=torch.float32,
        )

        bg_features = self.bg_features
        if bg_features is None:
            if not fill_missing_modalities:
                raise ValueError("bg_features is missing and fill_missing_modalities=False")
            bg_features = [0.0] * BG_DIM
        bg_features = torch.tensor(bg_features, dtype=torch.float32)

        micro_expression_features = self.micro_expression_features
        if micro_expression_features is None:
            if not fill_missing_modalities:
                raise ValueError("micro_expression_features is missing and fill_missing_modalities=False")
            micro_expression_features = [0.0] * MICRO_EXPRESSION_DIM
        micro_expression_features = torch.tensor(micro_expression_features, dtype=torch.float32)

        tensors: dict[str, torch.Tensor] = {
            "clip_video": clip_video,
            "wav2clip": wav2clip,
            "clip_text": clip_text,
            "bg_features": bg_features,
            "micro_expression_features": micro_expression_features,
        }
        if self.labels is not None:
            tensors["labels"] = torch.tensor(self.labels, dtype=torch.float32)
        return tensors

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MultimodalFeatureBundle":
        bundle = cls(**payload)
        bundle.validate()
        return bundle

    @classmethod
    def from_json_file(cls, path: str | Path) -> "MultimodalFeatureBundle":
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return cls.from_dict(payload)

    @classmethod
    def from_current_artifacts(
        cls,
        *,
        sample: dict[str, Any],
        clip_payload: dict[str, Any],
        wav2clip_payload: dict[str, Any] | None = None,
        bg_payload: dict[str, Any] | None = None,
        micro_expression_payload: dict[str, Any] | None = None,
    ) -> "MultimodalFeatureBundle":
        labels = sample.get("labels")
        metadata = {
            "source": "current_artifacts",
            "trait_order": TRAIT_ORDER,
            "clip_success": bool(clip_payload.get("success", False)),
            "has_wav2clip": wav2clip_payload is not None,
            "has_bg_features": bg_payload is not None,
            "has_micro_expression": micro_expression_payload is not None
            and bool(
                micro_expression_payload.get("feature_vector")
                or micro_expression_payload.get("micro_expression_features")
                or micro_expression_payload.get("features"),
            ),
        }

        clip_text = clip_payload.get("text_sequence_features") or clip_payload.get("text_features") or []

        wav2clip = None
        if wav2clip_payload is not None:
            wav2clip = (
                wav2clip_payload.get("wav2clip_features")
                or wav2clip_payload.get("audio_features")
                or wav2clip_payload.get("features")
            )

        bg_features = None
        if bg_payload is not None:
            bg_features = (
                bg_payload.get("bg_features")
                or bg_payload.get("descriptor_features")
                or bg_payload.get("features")
            )

        micro_expression_features = None
        if micro_expression_payload is not None:
            micro_expression_features = (
                micro_expression_payload.get("feature_vector")
                or micro_expression_payload.get("micro_expression_features")
                or micro_expression_payload.get("features")
            )

        bundle = cls(
            video_name=sample["video_name"],
            video_path=sample.get("video_path", ""),
            labels=[float(labels[key]) for key in TRAIT_ORDER] if isinstance(labels, dict) else labels,
            clip_video=clip_payload.get("image_features", []),
            clip_text=clip_text,
            wav2clip=wav2clip,
            bg_features=bg_features,
            micro_expression_features=micro_expression_features,
            metadata=metadata,
        )
        bundle.validate()
        return bundle
