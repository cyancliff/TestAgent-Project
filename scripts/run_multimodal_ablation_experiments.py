"""Run multimodal ablation experiments from an existing full bundle set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.training import (
    discover_bundle_paths,
    evaluate_bundle_paths,
    load_checkpoint_model,
    train_baseline_model,
)


ABLATIONS: dict[str, dict[str, bool]] = {
    "text_only": {"visual": False, "audio": False, "text": True, "bg": False},
    "visual_only": {"visual": True, "audio": False, "text": False, "bg": False},
    "audio_only": {"visual": False, "audio": True, "text": False, "bg": False},
}

REFERENCE_EVALS = {
    "trimodal_no_bg": Path("reports/night_lr1e4_drop02/test_eval.json"),
    "trimodal_with_bg": Path("reports/agtn_mtl_bg_v1_lr1e4_drop02_full/test_eval.json"),
}

REFERENCE_LABELS = {
    "text_only": "文本单模态",
    "visual_only": "视觉单模态",
    "audio_only": "音频单模态",
    "trimodal_no_bg": "三模态",
    "trimodal_with_bg": "三模态+bg",
}


def zero_rows(rows: list[Any] | None) -> list[Any]:
    if not rows:
        return [[0.0] * 768]
    zeroed = []
    for row in rows:
        if isinstance(row, list):
            zeroed.append([0.0] * len(row))
        else:
            zeroed.append(row)
    return zeroed


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_ablation_bundle(payload: dict[str, Any], variant: str) -> dict[str, Any]:
    flags = ABLATIONS[variant]
    mutated = dict(payload)
    mutated["clip_video"] = payload.get("clip_video", [])
    mutated["clip_text"] = payload.get("clip_text", [])
    mutated["wav2clip"] = payload.get("wav2clip")
    mutated["bg_features"] = payload.get("bg_features")

    if not flags["visual"]:
        mutated["clip_video"] = zero_rows(payload.get("clip_video"))
    if not flags["text"]:
        mutated["clip_text"] = []
    if not flags["audio"]:
        mutated["wav2clip"] = None
    if not flags["bg"]:
        mutated["bg_features"] = None

    metadata = dict(mutated.get("metadata") or {})
    metadata["ablation_variant"] = variant
    metadata["uses_visual"] = flags["visual"]
    metadata["uses_audio"] = flags["audio"]
    metadata["uses_text"] = flags["text"]
    metadata["uses_bg"] = flags["bg"]
    mutated["metadata"] = metadata
    return mutated


def materialize_variant_bundles(
    *,
    source_root: Path,
    output_root: Path,
    variant: str,
    splits: list[str],
) -> None:
    for split in splits:
        source_dir = source_root / split
        target_dir = output_root / variant / "bundles" / split
        target_dir.mkdir(parents=True, exist_ok=True)
        source_files = sorted(source_dir.glob("*.json"))
        pending = [path for path in source_files if not (target_dir / path.name).exists()]
        for source_file in pending:
            payload = load_json(source_file)
            write_json(target_dir / source_file.name, build_ablation_bundle(payload, variant))


def train_and_eval_variant(
    *,
    variant: str,
    output_root: Path,
    manifests: dict[str, Path],
    device: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    dropout: float,
    train_limit: int | None,
    val_limit: int | None,
    test_limit: int | None,
) -> dict[str, Any]:
    variant_root = output_root / variant
    train_dir = variant_root / "bundles" / "train"
    val_dir = variant_root / "bundles" / "val"
    test_dir = variant_root / "bundles" / "test"

    checkpoint = variant_root / "agtn_mtl.pt"
    train_summary_path = variant_root / "train_summary.json"
    val_eval_path = variant_root / "val_eval.json"
    test_eval_path = variant_root / "test_eval.json"

    train_resolution = discover_bundle_paths(train_dir, manifest_path=manifests["train"], limit=train_limit)
    val_resolution = discover_bundle_paths(val_dir, manifest_path=manifests["val"], limit=val_limit)
    test_resolution = discover_bundle_paths(test_dir, manifest_path=manifests["test"], limit=test_limit)

    result = train_baseline_model(
        train_resolution.bundle_paths,
        checkpoint_path=checkpoint,
        val_bundle_paths=val_resolution.bundle_paths,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        weight_decay=0.0,
        device=device,
        text_seq_len=13,
        model_kwargs={
            "hidden_dim": 128,
            "attention_heads": 1,
            "graph_metric": "ones",
            "dropout": dropout,
        },
    )
    write_json(
        train_summary_path,
        {
            "checkpoint_path": str(result.checkpoint_path),
            "best_epoch": result.best_epoch,
            "best_loss": result.best_loss,
            "history": result.history,
            "train_bundle_count": len(train_resolution.bundle_paths),
            "val_bundle_count": len(val_resolution.bundle_paths),
            "test_bundle_count": len(test_resolution.bundle_paths),
        },
    )

    loaded = load_checkpoint_model(checkpoint, device=device)
    val_result = evaluate_bundle_paths(
        loaded.model,
        val_resolution.bundle_paths,
        device=loaded.device,
        batch_size=batch_size,
        text_seq_len=13,
        fill_missing_modalities=True,
        require_labels=True,
    )
    test_result = evaluate_bundle_paths(
        loaded.model,
        test_resolution.bundle_paths,
        device=loaded.device,
        batch_size=batch_size,
        text_seq_len=13,
        fill_missing_modalities=True,
        require_labels=True,
    )

    write_json(
        val_eval_path,
        {
            "split": "val",
            "checkpoint_path": str(checkpoint),
            "sample_count": val_result.sample_count,
            "mean_loss": val_result.mean_loss,
            "metrics": val_result.metrics,
        },
    )
    write_json(
        test_eval_path,
        {
            "split": "test",
            "checkpoint_path": str(checkpoint),
            "sample_count": test_result.sample_count,
            "mean_loss": test_result.mean_loss,
            "metrics": test_result.metrics,
        },
    )

    return {
        "variant": variant,
        "label": REFERENCE_LABELS[variant],
        "test_eval_path": str(test_eval_path),
        "metrics": test_result.metrics,
    }


def build_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# 多模态消融实验汇总",
        "",
        "| 变体 | MSE | MAE | ACC | PCC | CCC | R² |",
        "|------|----:|----:|----:|----:|----:|---:|",
    ]
    for row in rows:
        metrics = row["metrics"]
        lines.append(
            f"| {row['label']} | {metrics['mse']:.4f} | {metrics['mae']:.4f} | {metrics['acc']:.4f} | "
            f"{metrics['pcc']:.4f} | {metrics['ccc']:.4f} | {metrics['r2']:.4f} |"
        )
    lines.extend(
        [
            "",
            "说明：`三模态` 复用现有 baseline，对应无显式 bg 特征；`三模态+bg` 复用已完成的真实 bg_features 全量重训结果。",
            "单模态结果由当前脚本从完整 bundle 生成消融版本后重新训练得到。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multimodal ablation experiments from full bundles.")
    parser.add_argument("--source-bundle-root", default="reports/agtn_mtl_bg_v1_lr1e4_drop02_full/bundles")
    parser.add_argument("--output-root", default="reports/multimodal_ablation_experiments")
    parser.add_argument("--variants", default="text_only,visual_only,audio_only")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--train-limit", type=int, default=None)
    parser.add_argument("--val-limit", type=int, default=None)
    parser.add_argument("--test-limit", type=int, default=None)
    args = parser.parse_args()

    source_root = PROJECT_ROOT / args.source_bundle_root
    output_root = PROJECT_ROOT / args.output_root
    variants = [part.strip() for part in args.variants.split(",") if part.strip()]
    manifests = {
        "train": PROJECT_ROOT / "multimodal_personality/data/cfi_v2/manifests/train_manifest.json",
        "val": PROJECT_ROOT / "multimodal_personality/data/cfi_v2/manifests/val_manifest.json",
        "test": PROJECT_ROOT / "multimodal_personality/data/cfi_v2/manifests/test_manifest.json",
    }

    materialize_variant_bundles(
        source_root=source_root,
        output_root=output_root,
        variant=variants[0],
        splits=[],
    )
    for variant in variants:
        if variant not in ABLATIONS:
            raise ValueError(f"unsupported variant: {variant}")
        materialize_variant_bundles(
            source_root=source_root,
            output_root=output_root,
            variant=variant,
            splits=["train", "val", "test"],
        )

    rows = []
    for variant in variants:
        rows.append(
            train_and_eval_variant(
                variant=variant,
                output_root=output_root,
                manifests=manifests,
                device=args.device,
                epochs=args.epochs,
                batch_size=args.batch_size,
                learning_rate=args.learning_rate,
                dropout=args.dropout,
                train_limit=args.train_limit,
                val_limit=args.val_limit,
                test_limit=args.test_limit,
            )
        )

    for variant, relative_path in REFERENCE_EVALS.items():
        payload = load_json(PROJECT_ROOT / relative_path)
        rows.append(
            {
                "variant": variant,
                "label": REFERENCE_LABELS[variant],
                "test_eval_path": str(PROJECT_ROOT / relative_path),
                "metrics": payload["metrics"],
            }
        )

    summary_rows = sorted(rows, key=lambda row: ["text_only", "visual_only", "audio_only", "trimodal_no_bg", "trimodal_with_bg"].index(row["variant"]))
    write_json(
        output_root / "ablation_summary.json",
        {
            "rows": summary_rows,
        },
    )
    (output_root / "ablation_summary.md").write_text(build_markdown(summary_rows), encoding="utf-8")
    print(f"saved={output_root}")


if __name__ == "__main__":
    main()
