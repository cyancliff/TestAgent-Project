"""Utilities for discovering and validating the CFI-V2 dataset."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional at import time
    yaml = None


TRAIT_KEYS = [
    "extraversion",
    "agreeableness",
    "conscientiousness",
    "neuroticism",
    "openness",
]


@dataclass
class PhasePaths:
    """Resolved file paths for a dataset phase."""

    phase: str
    video_dir: Path
    annotation_path: Path
    transcription_path: Path


@dataclass
class ManifestSummary:
    """Summary information for a generated manifest."""

    dataset_name: str
    phase: str
    sample_count: int
    missing_videos: int
    missing_transcripts: int
    output_path: Path


@dataclass
class LoadedManifest:
    """Loaded manifest content."""

    dataset_name: str
    phase: str
    sample_count: int
    missing_videos: int
    missing_transcripts: int
    samples: list[dict[str, Any]]


def load_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Load a YAML dataset config."""
    if yaml is None:
        raise RuntimeError("pyyaml is required to load dataset config files")
    path = Path(config_path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_phase_paths(config: dict[str, Any], phase: str) -> PhasePaths:
    """Resolve configured paths for a single dataset phase."""
    phase_config = config["phases"][phase]
    return PhasePaths(
        phase=phase,
        video_dir=Path(phase_config["video_dir"]),
        annotation_path=Path(phase_config["annotation_path"]),
        transcription_path=Path(phase_config["transcription_path"]),
    )


def load_pickle(path: str | Path) -> Any:
    """Load a pickle file from disk."""
    with Path(path).open("rb") as handle:
        try:
            return pickle.load(handle)
        except UnicodeDecodeError:
            handle.seek(0)
            return pickle.load(handle, encoding="latin1")


def normalize_annotations(annotation_data: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """Keep only the five Big Five traits and normalize their names."""
    normalized = {}
    for trait in TRAIT_KEYS:
        if trait not in annotation_data:
            raise KeyError(f"Missing trait '{trait}' in annotation file")
        normalized[trait] = annotation_data[trait]
    return normalized


def _find_video_path(video_dir: Path, video_name: str) -> Path | None:
    """Find the matching video file for a dataset item."""
    candidates = [
        video_dir / video_name,
        video_dir / f"{video_name}.mp4",
        video_dir / f"{video_name}.avi",
        video_dir / f"{video_name}.mov",
        video_dir / f"{video_name}.mkv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def build_phase_manifest(config: dict[str, Any], phase: str) -> tuple[list[dict[str, Any]], ManifestSummary]:
    """Build a normalized manifest for one phase."""
    dataset_name = config.get("dataset_name", "cfi_v2")
    output_dir = Path(config["output_manifest_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = resolve_phase_paths(config, phase)
    annotation_data = normalize_annotations(load_pickle(paths.annotation_path))
    transcription_data = load_pickle(paths.transcription_path)

    video_names = sorted(annotation_data["openness"].keys())
    samples: list[dict[str, Any]] = []
    missing_videos = 0
    missing_transcripts = 0

    for video_name in video_names:
        video_path = _find_video_path(paths.video_dir, video_name)
        transcript = transcription_data.get(video_name, "")
        if transcript is None:
            transcript = ""
        if video_path is None:
            missing_videos += 1
        if not transcript:
            missing_transcripts += 1

        labels = {trait: float(annotation_data[trait][video_name]) for trait in TRAIT_KEYS}
        samples.append(
            {
                "video_name": video_name,
                "video_path": str(video_path) if video_path else "",
                "transcript": transcript,
                "labels": labels,
                "has_video": video_path is not None,
                "has_transcript": bool(transcript.strip()),
            }
        )

    output_path = output_dir / f"{phase}_manifest.json"
    output_path.write_text(
        json.dumps(
            {
                "dataset_name": dataset_name,
                "phase": phase,
                "sample_count": len(samples),
                "missing_videos": missing_videos,
                "missing_transcripts": missing_transcripts,
                "samples": samples,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    summary = ManifestSummary(
        dataset_name=dataset_name,
        phase=phase,
        sample_count=len(samples),
        missing_videos=missing_videos,
        missing_transcripts=missing_transcripts,
        output_path=output_path,
    )
    return samples, summary


def load_manifest(manifest_path: str | Path) -> LoadedManifest:
    """Load a previously generated JSON manifest."""
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8-sig"))
    return LoadedManifest(
        dataset_name=payload["dataset_name"],
        phase=payload["phase"],
        sample_count=payload["sample_count"],
        missing_videos=payload["missing_videos"],
        missing_transcripts=payload["missing_transcripts"],
        samples=payload["samples"],
    )


def filter_manifest_samples(
    manifest: LoadedManifest,
    require_video: bool = True,
    require_transcript: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Filter manifest samples for downstream processing."""
    samples = []
    for sample in manifest.samples:
        if require_video and not sample.get("has_video", False):
            continue
        if require_transcript and not sample.get("has_transcript", False):
            continue
        samples.append(sample)
        if limit is not None and len(samples) >= limit:
            break
    return samples
