"""Run multimodal preprocessing for samples listed in a manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.multimodal_personality_service import service
from multimodal_personality.preprocessing.cfi_v2_dataset import filter_manifest_samples, load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess CFI-V2 videos from a manifest")
    parser.add_argument("--manifest", required=True, help="Path to the manifest JSON")
    parser.add_argument("--limit", type=int, default=10, help="Number of samples to preprocess")
    parser.add_argument(
        "--require-transcript",
        action="store_true",
        help="Only preprocess samples that already have transcript text in the manifest",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    samples = filter_manifest_samples(
        manifest,
        require_video=True,
        require_transcript=args.require_transcript,
        limit=args.limit,
    )

    completed = 0
    failed = 0
    for index, sample in enumerate(samples, start=1):
        task = service.create_task(video_path=sample["video_path"])
        task = service.run_task(task.task_id, force_restart=True)
        print(
            f"[{index}/{len(samples)}] {sample['video_name']} "
            f"status={task.status} errors={len(task.errors)} artifact_dir={task.artifacts.get('artifact_dir', '')}"
        )
        if task.status == "completed":
            completed += 1
        else:
            failed += 1

    print(f"[summary] total={len(samples)} completed={completed} failed={failed}")


if __name__ == "__main__":
    main()
