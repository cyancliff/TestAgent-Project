"""Run the bg_features retraining comparison pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_step(command: list[str], *, dry_run: bool) -> None:
    printable = " ".join(command)
    print(f"[step] {printable}")
    if dry_run:
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate bg_features bundles, retrain, evaluate, and summarize.")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--train-limit", type=int, default=None)
    parser.add_argument("--val-limit", type=int, default=None)
    parser.add_argument("--test-limit", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--output-dir", default="reports/agtn_mtl_bg_v1_lr1e4_drop02")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = PROJECT_ROOT / args.output_dir
    checkpoint = output_dir / "agtn_mtl_bg_v1_lr1e4_drop02.pt"
    train_manifest = "multimodal_personality/data/cfi_v2/manifests/train_manifest.json"
    val_manifest = "multimodal_personality/data/cfi_v2/manifests/val_manifest.json"
    test_manifest = "multimodal_personality/data/cfi_v2/manifests/test_manifest.json"
    bundle_dir = "multimodal_personality/data/cfi_v2/bundles_bg_v1"

    output_dir.mkdir(parents=True, exist_ok=True)
    for manifest, limit in [(train_manifest, args.train_limit), (val_manifest, args.val_limit), (test_manifest, args.test_limit)]:
        command = [
            sys.executable,
            "scripts/build_multimodal_feature_bundles.py",
            "--manifest",
            manifest,
            "--output-dir",
            bundle_dir,
            "--require-clip",
        ]
        if limit:
            command.extend(["--limit", str(limit)])
        run_step(command, dry_run=args.dry_run)

    train_command = [
        sys.executable,
        "scripts/train_agtn_mtl.py",
        "--train-bundle-dir",
        bundle_dir,
        "--val-bundle-dir",
        bundle_dir,
        "--train-manifest",
        train_manifest,
        "--val-manifest",
        val_manifest,
        "--checkpoint",
        str(checkpoint),
        "--summary-output",
        str(output_dir / "train_summary.json"),
        "--epochs",
        str(args.epochs),
        "--batch-size",
        str(args.batch_size),
        "--learning-rate",
        str(args.learning_rate),
        "--dropout",
        str(args.dropout),
        "--device",
        args.device,
    ]
    if args.train_limit:
        train_command.extend(["--train-limit", str(args.train_limit)])
    if args.val_limit:
        train_command.extend(["--val-limit", str(args.val_limit)])
    run_step(train_command, dry_run=args.dry_run)

    eval_command = [
        sys.executable,
        "scripts/eval_agtn_mtl.py",
        "--checkpoint",
        str(checkpoint),
        "--bundle-dir",
        bundle_dir,
        "--manifest",
        test_manifest,
        "--output",
        str(output_dir / "test_eval.json"),
        "--device",
        args.device,
    ]
    if args.test_limit:
        eval_command.extend(["--limit", str(args.test_limit)])
    run_step(eval_command, dry_run=args.dry_run)

    run_step(
        [
            sys.executable,
            "scripts/summarize_multimodal_experiments.py",
            "--eval",
            "lr1e-4 dropout0.2 test=reports/night_lr1e4_drop02/test_eval.json",
            "--eval",
            f"bg_features v1 test={output_dir / 'test_eval.json'}",
            "--markdown-output",
            str(output_dir / "multimodal_bg_comparison.md"),
            "--json-output",
            str(output_dir / "multimodal_bg_comparison.json"),
        ],
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
