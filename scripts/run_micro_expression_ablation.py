"""Run no-micro vs with-micro small-sample ablations."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.models.feature_bundle import MICRO_EXPRESSION_DIM
from multimodal_personality.training import (
    discover_bundle_paths,
    evaluate_bundle_paths,
    load_checkpoint_model,
    train_baseline_model,
)


@dataclass(frozen=True)
class AblationRunConfig:
    name: str
    train_bundle_paths: list[Path]
    val_bundle_paths: list[Path]
    checkpoint_path: Path
    epochs: int
    batch_size: int
    device: str
    model_kwargs: dict[str, object]


def build_ablation_plan(
    *,
    train_bundle_dir: str | Path,
    val_bundle_dir: str | Path,
    output_dir: str | Path,
    epochs: int,
    batch_size: int,
    device: str,
    hidden_dim: int,
) -> list[AblationRunConfig]:
    train_resolution = discover_bundle_paths(train_bundle_dir)
    val_resolution = discover_bundle_paths(val_bundle_dir)
    output_root = Path(output_dir)

    base_kwargs = {
        "hidden_dim": hidden_dim,
        "micro_expression_dim": MICRO_EXPRESSION_DIM,
    }
    runs = [
        ("no_micro", False),
        ("with_micro", True),
    ]
    return [
        AblationRunConfig(
            name=name,
            train_bundle_paths=list(train_resolution.bundle_paths),
            val_bundle_paths=list(val_resolution.bundle_paths),
            checkpoint_path=output_root / name / "checkpoint.pt",
            epochs=epochs,
            batch_size=batch_size,
            device=device,
            model_kwargs={**base_kwargs, "use_micro_expression_features": use_micro},
        )
        for name, use_micro in runs
    ]


def _run_to_summary(config: AblationRunConfig) -> dict[str, object]:
    train_result = train_baseline_model(
        config.train_bundle_paths,
        checkpoint_path=config.checkpoint_path,
        val_bundle_paths=config.val_bundle_paths,
        epochs=config.epochs,
        batch_size=config.batch_size,
        device=config.device,
        model_kwargs=config.model_kwargs,
    )
    loaded = load_checkpoint_model(train_result.checkpoint_path, device=config.device)
    eval_result = evaluate_bundle_paths(
        loaded.model,
        config.val_bundle_paths,
        device=loaded.device,
        batch_size=config.batch_size,
        require_labels=True,
    )

    return {
        "name": config.name,
        "uses_micro_expression_features": bool(config.model_kwargs["use_micro_expression_features"]),
        "checkpoint_path": str(train_result.checkpoint_path),
        "best_epoch": train_result.best_epoch,
        "best_loss": train_result.best_loss,
        "history": train_result.history,
        "train_bundle_count": len(config.train_bundle_paths),
        "val_bundle_count": len(config.val_bundle_paths),
        "eval_sample_count": eval_result.sample_count,
        "eval_loss": eval_result.mean_loss,
        "eval_metrics": eval_result.metrics,
    }


def run_ablation(
    *,
    train_bundle_dir: str | Path,
    val_bundle_dir: str | Path,
    output_dir: str | Path,
    epochs: int,
    batch_size: int,
    device: str,
    hidden_dim: int,
) -> dict[str, object]:
    plan = build_ablation_plan(
        train_bundle_dir=train_bundle_dir,
        val_bundle_dir=val_bundle_dir,
        output_dir=output_dir,
        epochs=epochs,
        batch_size=batch_size,
        device=device,
        hidden_dim=hidden_dim,
    )
    summary = {
        "train_bundle_dir": str(Path(train_bundle_dir)),
        "val_bundle_dir": str(Path(val_bundle_dir)),
        "runs": [_run_to_summary(config) for config in plan],
    }

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    summary_path = output_root / "ablation_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run micro-expression ablation experiments")
    parser.add_argument("--train-bundle-dir", required=True, help="Directory containing training bundle JSON files")
    parser.add_argument("--val-bundle-dir", required=True, help="Directory containing validation bundle JSON files")
    parser.add_argument("--output-dir", required=True, help="Directory for checkpoints and ablation_summary.json")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Mini-batch size")
    parser.add_argument("--device", default="cpu", help="Torch device, e.g. cpu or cuda:0")
    parser.add_argument("--hidden-dim", type=int, default=128, help="Hidden size for fusion layers")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    summary = run_ablation(
        train_bundle_dir=args.train_bundle_dir,
        val_bundle_dir=args.val_bundle_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        device=args.device,
        hidden_dim=args.hidden_dim,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
