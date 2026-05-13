"""Render a meeting-friendly table for MOL batch micro-expression samples."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_sample_rows(batch_summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in batch_summary.get("rows", []):
        output_path = str(item.get("output_path") or "")
        payload = _load_json(output_path) if output_path and Path(output_path).exists() else {}
        probabilities = payload.get("probabilities") or {}
        rows.append(
            {
                "video_name": item.get("video_name") or "",
                "class_name": item.get("class_name") or "",
                "success": bool(item.get("success", False)),
                "dominant_expression": item.get("dominant_expression") or "",
                "confidence": _safe_float(item.get("confidence")),
                "feature_dim": int(payload.get("feature_dim") or len(payload.get("feature_vector") or [])),
                "surprise": _safe_float(probabilities.get("surprise")),
                "positive": _safe_float(probabilities.get("positive")),
                "negative": _safe_float(probabilities.get("negative")),
                "summary_text_zh": payload.get("summary_text_zh") or "",
                "output_path": output_path,
            }
        )
    return rows


def _fmt(value: Any) -> str:
    return f"{_safe_float(value):.4f}"


def render_sample_table_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# MOL 微表情样本明细表",
        "",
        "这张表用于组会展示真实 MOL 批量提取结果。微表情只代表短时面部线索，不等同于稳定人格标签。",
        "",
        "| Video | Dataset Label | MOL Dominant | Success | Confidence | Feature Dim | Surprise | Positive | Negative | JSON |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        success = "true" if row.get("success") else "false"
        lines.append(
            "| "
            f"{row.get('video_name', '')} | "
            f"{row.get('class_name', '')} | "
            f"{row.get('dominant_expression', '')} | "
            f"{success} | "
            f"{_fmt(row.get('confidence'))} | "
            f"{row.get('feature_dim', 0)} | "
            f"{_fmt(row.get('surprise'))} | "
            f"{_fmt(row.get('positive'))} | "
            f"{_fmt(row.get('negative'))} | "
            f"`{row.get('output_path', '')}` |"
        )
    lines.extend(
        [
            "",
            "## 口头说明",
            "",
            "- `Dataset Label` 是原始数据集目录标签，`MOL Dominant` 是 MOL 当前模型输出的主导类别。",
            "- `Confidence` 是主导类别概率，不建议在小样本上解读为泛化性能。",
            "- `Feature Dim` 当前为 8 维，已可进入多模态 feature bundle 和消融训练。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_sample_csv(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "video_name",
        "class_name",
        "success",
        "dominant_expression",
        "confidence",
        "feature_dim",
        "surprise",
        "positive",
        "negative",
        "summary_text_zh",
        "output_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write MOL micro-expression sample detail table")
    parser.add_argument("--batch-summary", default="reports/mol_micro_batch_samm_limit6/summary.json")
    parser.add_argument("--output-md", default="reports/MOL微表情样本明细表.md")
    parser.add_argument("--output-csv", default="reports/mol_micro_sample_table.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_sample_rows(_load_json(args.batch_summary))
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_sample_table_markdown(rows), encoding="utf-8")
    write_sample_csv(rows, args.output_csv)
    print(f"samples={len(rows)} markdown={md_path} csv={args.output_csv}")


if __name__ == "__main__":
    main()
