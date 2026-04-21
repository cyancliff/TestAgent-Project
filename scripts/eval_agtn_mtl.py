"""Evaluate a saved AGTN-MTL checkpoint against bundle JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.training import discover_bundle_paths, evaluate_bundle_paths, load_checkpoint_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate an AGTN-MTL checkpoint with bundle JSON files")
    parser.add_argument("--checkpoint", required=True, help="Path to the saved checkpoint")
    parser.add_argument(
        "--bundle-dir",
        default="multimodal_personality/data/cfi_v2/bundles",
        help="Directory containing evaluation bundle JSON files",
    )
    parser.add_argument("--manifest", default=None, help="Optional manifest used to filter evaluation bundle names")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for evaluation bundle count")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size")
    parser.add_argument("--device", default="cpu", help="Torch device, e.g. cpu or cuda:0")
    parser.add_argument("--output", default=None, help="Optional JSON path for evaluation metrics and predictions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    resolution = discover_bundle_paths(args.bundle_dir, manifest_path=args.manifest, limit=args.limit)
    if not resolution.bundle_paths:
        raise RuntimeError("no bundle files were resolved for evaluation")

    loaded = load_checkpoint_model(args.checkpoint, device=args.device)
    text_seq_len = int(loaded.checkpoint.get("model_kwargs", {}).get("text_seq_len", 13))
    result = evaluate_bundle_paths(
        loaded.model,
        resolution.bundle_paths,
        device=loaded.device,
        batch_size=args.batch_size,
        text_seq_len=text_seq_len,
        fill_missing_modalities=True,
        require_labels=True,
    )

    payload = {
        "checkpoint_path": str(Path(args.checkpoint)),
        "bundle_count": len(resolution.bundle_paths),
        "missing_bundle_names": resolution.missing_bundle_names,
        "mean_loss": result.mean_loss,
        "metrics": result.metrics,
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

    print(
        f"evaluated samples={result.sample_count} "
        f"mse={result.metrics.get('mse', 0.0):.6f} "
        f"mae={result.metrics.get('mae', 0.0):.6f} "
        f"checkpoint={args.checkpoint}",
    )


if __name__ == "__main__":
    main()
