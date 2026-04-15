"""Extract CLIP features for jobs prepared from the manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.feature_extractors.clip_extractor import ClipFeatureExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract CLIP features from preprocessed jobs")
    parser.add_argument("--jobs", required=True, help="Path to feature_jobs.json")
    parser.add_argument(
        "--output-dir",
        default="multimodal_personality/data/cfi_v2/features/clip",
        help="Directory for extracted feature JSON files",
    )
    parser.add_argument("--device", default="cpu", help="Torch device, e.g. cpu or cuda:0")
    parser.add_argument("--limit", type=int, default=None, help="Optional processing limit")
    args = parser.parse_args()

    jobs_payload = json.loads(Path(args.jobs).read_text(encoding="utf-8-sig"))
    jobs = jobs_payload["jobs"]
    if args.limit is not None:
        jobs = jobs[: args.limit]

    extractor = ClipFeatureExtractor(device=args.device)
    success_count = 0
    fail_count = 0

    for job in jobs:
        if not job.get("ready_for_clip"):
            fail_count += 1
            continue
        result = extractor.extract_sample(
            sample=job,
            frames_dir=job["frames_dir"],
            output_dir=args.output_dir,
        )
        if result.success:
            success_count += 1
        else:
            fail_count += 1

    print(f"success={success_count} failed={fail_count} output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
