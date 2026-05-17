"""Batch extract MOL micro-expression features from nested frame folders."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.feature_extractors.micro_expression_extractor import MOLMicroExpressionExtractor


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def _has_enough_frames(path: Path, min_frames: int = 8) -> bool:
    return sum(1 for child in path.iterdir() if child.suffix.lower() in IMAGE_SUFFIXES) >= min_frames


def discover_frame_samples(root_dir: str | Path, *, limit: int | None = None) -> list[dict[str, str]]:
    root = Path(root_dir)
    samples: list[dict[str, str]] = []
    for class_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        for frame_dir in sorted(path for path in class_dir.iterdir() if path.is_dir()):
            if not _has_enough_frames(frame_dir):
                continue
            samples.append(
                {
                    "video_name": frame_dir.name,
                    "class_name": class_dir.name,
                    "frames_dir": str(frame_dir),
                },
            )
    samples = sorted(samples, key=lambda item: item["video_name"])
    return samples if limit is None else samples[:limit]


def _load_payload(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_summary_csv(rows: list[dict[str, object]], output_path: Path) -> None:
    fieldnames = [
        "video_name",
        "class_name",
        "success",
        "dominant_expression",
        "dominant_label_zh",
        "confidence",
        "output_path",
        "error_count",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_batch_extraction(
    *,
    root_dir: str | Path,
    output_dir: str | Path,
    extractor: MOLMicroExpressionExtractor,
    limit: int | None,
    resume: bool,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    samples = discover_frame_samples(root_dir, limit=limit)
    rows: list[dict[str, object]] = []
    dominant_counts: dict[str, int] = {}
    success_count = 0

    for sample in samples:
        sample_output_dir = output_root / sample["video_name"]
        output_path = sample_output_dir / "micro_expression_feature.json"
        if resume and output_path.exists():
            payload = _load_payload(output_path)
        else:
            result = extractor.extract_sample(
                video_name=sample["video_name"],
                video_path=sample["frames_dir"],
                frames_dir=sample["frames_dir"],
                output_dir=sample_output_dir,
            )
            payload = _load_payload(result.output_path)

        summary = payload.get("summary") or {}
        success = bool(payload.get("success", False))
        if success:
            success_count += 1
        dominant = str(summary.get("dominant_expression") or "unknown")
        dominant_counts[dominant] = dominant_counts.get(dominant, 0) + 1
        rows.append(
            {
                "video_name": sample["video_name"],
                "class_name": sample["class_name"],
                "success": success,
                "dominant_expression": dominant,
                "dominant_label_zh": summary.get("dominant_label_zh") or "暂无",
                "confidence": float(summary.get("confidence") or 0.0),
                "output_path": str(output_path),
                "error_count": len(payload.get("errors") or []),
            },
        )

    summary_payload = {
        "root_dir": str(root_dir),
        "output_dir": str(output_root),
        "sample_count": len(samples),
        "success_count": success_count,
        "failure_count": len(samples) - success_count,
        "dominant_counts": dominant_counts,
        "rows": rows,
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_summary_csv(rows, output_root / "summary.csv")
    return summary_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch extract MOL micro-expression features")
    parser.add_argument("--root-dir", required=True)
    parser.add_argument("--output-dir", default="reports/mol_micro_batch")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--timeout-seconds", type=int, default=60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extractor = MOLMicroExpressionExtractor(device=args.device, timeout_seconds=args.timeout_seconds)
    summary = run_batch_extraction(
        root_dir=args.root_dir,
        output_dir=args.output_dir,
        extractor=extractor,
        limit=args.limit,
        resume=args.resume,
    )
    print(
        f"samples={summary['sample_count']} "
        f"success={summary['success_count']} "
        f"failure={summary['failure_count']} "
        f"output={summary['output_dir']}",
    )


if __name__ == "__main__":
    main()
