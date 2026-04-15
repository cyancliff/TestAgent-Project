"""Build CLIP feature extraction jobs from a dataset manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.preprocessing.cfi_v2_dataset import filter_manifest_samples, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CLIP feature extraction jobs from a manifest")
    parser.add_argument("--manifest", required=True, help="Path to the train/val/test manifest JSON")
    parser.add_argument(
        "--artifacts-root",
        default="uploads/multimodal_personality/artifacts",
        help="Root directory containing per-video preprocessing artifacts",
    )
    parser.add_argument(
        "--output",
        default="multimodal_personality/data/cfi_v2/feature_jobs.json",
        help="Output JSON path for generated feature jobs",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for job generation")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    manifest = load_manifest(manifest_path)
    samples = filter_manifest_samples(manifest, require_video=True, require_transcript=False, limit=args.limit)
    artifacts_root = Path(args.artifacts_root)

    jobs: list[dict[str, str | bool]] = []
    for sample in samples:
        candidate_dirs = list(artifacts_root.glob(f"*/"))
        frame_dir = ""
        manifest_path = ""
        for candidate_dir in candidate_dirs:
            local_manifest = candidate_dir / "manifest.json"
            if not local_manifest.exists():
                continue
            try:
                payload = json.loads(local_manifest.read_text(encoding="utf-8"))
            except Exception:
                continue
            if Path(payload.get("video_path", "")).name == Path(sample["video_path"]).name:
                frame_dir = str(candidate_dir / "frames")
                manifest_path = str(local_manifest)
                break

        jobs.append(
            {
                "video_name": sample["video_name"],
                "video_path": sample["video_path"],
                "transcript": sample.get("transcript", ""),
                "artifact_manifest_path": manifest_path,
                "frames_dir": frame_dir,
                "ready_for_clip": bool(frame_dir),
            }
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "manifest": str(manifest_path),
                "sample_count": len(jobs),
                "jobs": jobs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    ready_count = sum(1 for job in jobs if job["ready_for_clip"])
    print(f"jobs={len(jobs)} ready_for_clip={ready_count} output={output_path}")


if __name__ == "__main__":
    main()
