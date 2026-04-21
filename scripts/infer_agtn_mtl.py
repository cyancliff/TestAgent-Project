"""Run AGTN-MTL checkpoint inference for one or more bundle JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.training import discover_bundle_paths, predict_bundle_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AGTN-MTL inference from bundle JSON files")
    parser.add_argument("--checkpoint", required=True, help="Path to the saved checkpoint")
    parser.add_argument(
        "--bundle",
        nargs="*",
        default=None,
        help="One or more explicit bundle JSON paths",
    )
    parser.add_argument(
        "--bundle-dir",
        default=None,
        help="Resolve bundle JSON files from this directory when --bundle is omitted",
    )
    parser.add_argument("--manifest", default=None, help="Optional manifest used to filter bundle names")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit when resolving from --bundle-dir")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size")
    parser.add_argument("--device", default="cpu", help="Torch device, e.g. cpu or cuda:0")
    parser.add_argument("--output", default=None, help="Optional JSON path for prediction output")
    return parser.parse_args()


def resolve_bundle_inputs(args: argparse.Namespace) -> tuple[list[Path], list[str]]:
    if args.bundle:
        return [Path(path) for path in args.bundle], []
    if not args.bundle_dir:
        raise RuntimeError("either --bundle or --bundle-dir must be provided")
    resolution = discover_bundle_paths(args.bundle_dir, manifest_path=args.manifest, limit=args.limit)
    return resolution.bundle_paths, resolution.missing_bundle_names


def main() -> None:
    args = parse_args()
    bundle_paths, missing_bundle_names = resolve_bundle_inputs(args)
    if not bundle_paths:
        raise RuntimeError("no bundle files were resolved for inference")

    result = predict_bundle_paths(
        args.checkpoint,
        bundle_paths,
        device=args.device,
        batch_size=args.batch_size,
    )
    payload = {
        "checkpoint_path": str(Path(args.checkpoint)),
        "sample_count": result.sample_count,
        "missing_bundle_names": missing_bundle_names,
        "predictions": [
            {
                "video_name": record.video_name,
                "bundle_path": record.bundle_path,
                "scores": record.scores,
                "labels": record.labels,
            }
            for record in result.predictions
        ],
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved={output_path}")

    for record in result.predictions:
        score_text = " ".join(f"{trait}={score:.4f}" for trait, score in record.scores.items())
        print(f"{record.video_name} {score_text}")


if __name__ == "__main__":
    main()
