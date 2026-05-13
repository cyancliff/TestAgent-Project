"""Prepare a manifest that summarizes micro-expression coverage for ablations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_ablation_manifest(*, bundle_dir: str | Path, micro_expression_dir: str | Path) -> dict:
    bundle_root = Path(bundle_dir)
    micro_root = Path(micro_expression_dir)
    samples = []
    micro_count = 0

    for bundle_path in sorted(bundle_root.glob("*.json")):
        bundle = load_json(bundle_path)
        video_name = str(bundle.get("video_name") or bundle_path.stem)
        candidates = [
            micro_root / f"{video_name}.json",
            micro_root / bundle_path.name,
            micro_root / video_name / "micro_expression_feature.json",
        ]
        micro_path = next((path for path in candidates if path.exists()), None)
        has_micro = micro_path is not None
        if has_micro:
            micro_count += 1
        samples.append(
            {
                "video_name": video_name,
                "bundle_path": str(bundle_path),
                "micro_expression_path": None if micro_path is None else str(micro_path),
                "has_micro_expression": has_micro,
            },
        )

    bundle_count = len(samples)
    return {
        "bundle_count": bundle_count,
        "micro_expression_count": micro_count,
        "coverage": 0.0 if bundle_count == 0 else micro_count / bundle_count,
        "samples": samples,
        "next_train_command": (
            "python scripts/train_agtn_mtl.py --train-bundle-dir <bundle_dir> "
            "--use-micro-expression-features --checkpoint <output.pt>"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare micro-expression ablation manifest")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--micro-expression-dir", required=True)
    parser.add_argument("--output", default="reports/micro_expression_ablation_manifest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = build_ablation_manifest(
        bundle_dir=args.bundle_dir,
        micro_expression_dir=args.micro_expression_dir,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"bundles={manifest['bundle_count']} "
        f"micro={manifest['micro_expression_count']} "
        f"coverage={manifest['coverage']:.2%}",
    )
    print(f"saved={output_path}")


if __name__ == "__main__":
    main()
