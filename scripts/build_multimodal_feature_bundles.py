"""Build model-ready multimodal feature bundles from extracted artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.models.feature_bundle import MultimodalFeatureBundle
from multimodal_personality.preprocessing.cfi_v2_dataset import filter_manifest_samples, load_manifest


def load_optional_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build model-ready multimodal feature bundle JSON files")
    parser.add_argument("--manifest", required=True, help="Path to the dataset manifest JSON")
    parser.add_argument(
        "--clip-dir",
        default="multimodal_personality/data/cfi_v2/features/clip",
        help="Directory containing CLIP feature JSON files",
    )
    parser.add_argument(
        "--wav2clip-dir",
        default="multimodal_personality/data/cfi_v2/features/wav2clip",
        help="Directory containing wav2clip feature JSON files",
    )
    parser.add_argument(
        "--bg-dir",
        default="multimodal_personality/data/cfi_v2/features/bg",
        help="Directory containing bg feature JSON files",
    )
    parser.add_argument(
        "--output-dir",
        default="multimodal_personality/data/cfi_v2/bundles",
        help="Directory for output bundle JSON files",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for generated bundles")
    parser.add_argument(
        "--require-clip",
        action="store_true",
        help="Skip samples that do not already have a CLIP feature file",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    samples = filter_manifest_samples(manifest, require_video=True, require_transcript=False, limit=args.limit)

    clip_dir = Path(args.clip_dir)
    wav2clip_dir = Path(args.wav2clip_dir)
    bg_dir = Path(args.bg_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    built = 0
    skipped = 0
    for sample in samples:
        clip_path = clip_dir / f"{sample['video_name']}.json"
        clip_payload = load_optional_json(clip_path)
        if clip_payload is None:
            skipped += 1
            if args.require_clip:
                continue
            clip_payload = {
                "success": False,
                "image_features": [],
                "text_features": [],
            }

        wav2clip_payload = load_optional_json(wav2clip_dir / f"{sample['video_name']}.json")
        bg_payload = load_optional_json(bg_dir / f"{sample['video_name']}.json")

        try:
            bundle = MultimodalFeatureBundle.from_current_artifacts(
                sample=sample,
                clip_payload=clip_payload,
                wav2clip_payload=wav2clip_payload,
                bg_payload=bg_payload,
            )
        except ValueError as exc:
            print(f"skip {sample['video_name']} reason={exc}")
            skipped += 1
            continue

        bundle.write_json(output_dir / f"{sample['video_name']}.json")
        built += 1

    print(f"bundles={built} skipped={skipped} output_dir={output_dir}")


if __name__ == "__main__":
    main()
