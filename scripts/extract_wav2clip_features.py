"""Extract wav2clip features for jobs prepared from the manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.feature_extractors.wav2clip_extractor import Wav2ClipFeatureExtractor


def resolve_audio_path(job: dict[str, object]) -> str:
    audio_path = str(job.get("audio_path", "") or "")
    if audio_path:
        return audio_path

    artifact_manifest_path = str(job.get("artifact_manifest_path", "") or "")
    if artifact_manifest_path:
        return str(Path(artifact_manifest_path).parent / "audio.wav")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract wav2clip features from preprocessed jobs")
    parser.add_argument("--jobs", required=True, help="Path to feature_jobs.json")
    parser.add_argument(
        "--output-dir",
        default="multimodal_personality/data/cfi_v2/features/wav2clip",
        help="Directory for extracted wav2clip feature JSON files",
    )
    parser.add_argument("--segment-count", type=int, default=15, help="Target temporal segment count")
    parser.add_argument("--limit", type=int, default=None, help="Optional processing limit")
    args = parser.parse_args()

    jobs_payload = json.loads(Path(args.jobs).read_text(encoding="utf-8-sig"))
    jobs = jobs_payload["jobs"]
    if args.limit is not None:
        jobs = jobs[: args.limit]

    extractor = Wav2ClipFeatureExtractor(segment_count=args.segment_count)
    success_count = 0
    fail_count = 0

    for job in jobs:
        audio_path = resolve_audio_path(job)
        if not audio_path:
            fail_count += 1
            continue

        result = extractor.extract_sample(
            video_name=str(job["video_name"]),
            audio_path=audio_path,
            output_dir=args.output_dir,
        )
        if result.success:
            success_count += 1
        else:
            fail_count += 1

    print(f"success={success_count} failed={fail_count} output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
