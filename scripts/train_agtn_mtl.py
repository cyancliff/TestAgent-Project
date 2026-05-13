"""Train the AGTN-MTL baseline with feature bundle JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.training import discover_bundle_paths, train_baseline_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the AGTN-MTL baseline from bundle JSON files")
    parser.add_argument(
        "--train-bundle-dir",
        default="multimodal_personality/data/cfi_v2/bundles",
        help="Directory containing training bundle JSON files",
    )
    parser.add_argument(
        "--val-bundle-dir",
        default=None,
        help="Optional directory containing validation bundle JSON files (defaults to train-bundle-dir)",
    )
    parser.add_argument("--train-manifest", default=None, help="Optional train manifest used to filter bundle names")
    parser.add_argument("--val-manifest", default=None, help="Optional validation manifest used to filter bundle names")
    parser.add_argument("--train-limit", type=int, default=None, help="Optional limit for training bundle count")
    parser.add_argument("--val-limit", type=int, default=None, help="Optional limit for validation bundle count")
    parser.add_argument(
        "--checkpoint",
        default="multimodal_personality/checkpoints/agtn_mtl_baseline.pt",
        help="Output checkpoint path",
    )
    parser.add_argument("--summary-output", default=None, help="Optional JSON path for the training summary")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Optimizer learning rate")
    parser.add_argument("--weight-decay", type=float, default=0.0, help="Optimizer weight decay")
    parser.add_argument("--device", default="cpu", help="Torch device, e.g. cpu or cuda:0")
    parser.add_argument("--text-seq-len", type=int, default=13, help="Padded transcript sequence length")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Hidden size for fusion layers")
    parser.add_argument("--attention-heads", type=int, default=1, help="Residual channel attention heads")
    parser.add_argument("--graph-metric", default="ones", help="Graph construction metric")
    parser.add_argument("--dropout", type=float, default=0.2, help="Dropout ratio")
    parser.add_argument(
        "--use-micro-expression-features",
        action="store_true",
        help="Enable the optional MOL micro-expression feature branch for ablation training",
    )
    parser.add_argument("--micro-expression-dim", type=int, default=8, help="MOL micro-expression feature size")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train_resolution = discover_bundle_paths(
        args.train_bundle_dir,
        manifest_path=args.train_manifest,
        limit=args.train_limit,
    )
    val_bundle_dir = args.val_bundle_dir or args.train_bundle_dir
    val_resolution = None
    if args.val_manifest or args.val_bundle_dir:
        val_resolution = discover_bundle_paths(
            val_bundle_dir,
            manifest_path=args.val_manifest,
            limit=args.val_limit,
        )

    result = train_baseline_model(
        train_resolution.bundle_paths,
        checkpoint_path=args.checkpoint,
        val_bundle_paths=None if val_resolution is None else val_resolution.bundle_paths,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        device=args.device,
        text_seq_len=args.text_seq_len,
        model_kwargs={
            "hidden_dim": args.hidden_dim,
            "attention_heads": args.attention_heads,
            "graph_metric": args.graph_metric,
            "dropout": args.dropout,
            "use_micro_expression_features": args.use_micro_expression_features,
            "micro_expression_dim": args.micro_expression_dim,
        },
    )

    summary = {
        "checkpoint_path": str(result.checkpoint_path),
        "best_epoch": result.best_epoch,
        "best_loss": result.best_loss,
        "history": result.history,
        "train_bundle_count": len(train_resolution.bundle_paths),
        "missing_train_bundles": train_resolution.missing_bundle_names,
        "val_bundle_count": 0 if val_resolution is None else len(val_resolution.bundle_paths),
        "missing_val_bundles": [] if val_resolution is None else val_resolution.missing_bundle_names,
    }

    summary_path = Path(args.summary_output) if args.summary_output else Path(args.checkpoint).with_suffix(".summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        "trained "
        f"train={len(train_resolution.bundle_paths)} "
        f"val={0 if val_resolution is None else len(val_resolution.bundle_paths)} "
        f"best_epoch={result.best_epoch} "
        f"best_loss={result.best_loss:.6f} "
        f"checkpoint={result.checkpoint_path}",
    )
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
