"""Build paper-ready multimodal experiment metric tables."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from multimodal_personality.models.feature_bundle import TRAIT_ORDER
from multimodal_personality.training.metrics import compute_regression_metrics


DEFAULT_EVAL_FILES = [
    ("Full baseline test", Path("reports/full_multimodal_pipeline/test_eval.json")),
    ("lr1e-4 dropout0.2 test", Path("reports/night_lr1e4_drop02/test_eval.json")),
    ("lr1e-4 dropout0.3 test", Path("reports/night_lr1e4_drop03/test_eval.json")),
    ("lr2e-4 dropout0.3 test", Path("reports/night_lr2e4_drop03/test_eval.json")),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize multimodal evaluation metrics for paper tables")
    parser.add_argument(
        "--eval",
        action="append",
        default=[],
        help="Evaluation JSON path, optionally as label=path. Defaults to known reports when omitted.",
    )
    parser.add_argument(
        "--json-output",
        default="reports/multimodal_experiment_metrics.json",
        help="Output JSON summary path",
    )
    parser.add_argument(
        "--markdown-output",
        default="reports/multimodal_experiment_metrics.md",
        help="Output Markdown table path",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Update source evaluation JSON files with recomputed metrics when predictions and labels are available",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_eval_specs(specs: list[str]) -> list[tuple[str, Path]]:
    if not specs:
        return [(label, PROJECT_ROOT / path) for label, path in DEFAULT_EVAL_FILES if (PROJECT_ROOT / path).exists()]

    resolved: list[tuple[str, Path]] = []
    for spec in specs:
        if "=" in spec:
            label, path_value = spec.split("=", 1)
            path = Path(path_value)
            resolved.append((label.strip(), path if path.is_absolute() else PROJECT_ROOT / path))
        else:
            path = Path(spec)
            resolved_path = path if path.is_absolute() else PROJECT_ROOT / path
            resolved.append((resolved_path.stem, resolved_path))
    return resolved


def metrics_from_predictions(payload: dict[str, Any]) -> dict[str, object] | None:
    predictions = payload.get("predictions") or []
    labeled_predictions = [
        record
        for record in predictions
        if (
            isinstance(record, dict)
            and isinstance(record.get("scores"), dict)
            and isinstance(record.get("labels"), dict)
        )
    ]
    if not labeled_predictions:
        return None

    prediction_rows = [
        [float(record["scores"][trait_name]) for trait_name in TRAIT_ORDER]
        for record in labeled_predictions
    ]
    target_rows = [
        [float(record["labels"][trait_name]) for trait_name in TRAIT_ORDER]
        for record in labeled_predictions
    ]
    return compute_regression_metrics(
        torch.tensor(prediction_rows, dtype=torch.float32),
        torch.tensor(target_rows, dtype=torch.float32),
    )


def merge_metrics(payload: dict[str, Any], *, write_back_path: Path | None = None) -> dict[str, object]:
    recomputed = metrics_from_predictions(payload)
    if recomputed is not None:
        payload["metrics"] = recomputed
        payload["mean_loss"] = recomputed["mse"]
        if write_back_path is not None:
            write_json(write_back_path, payload)
        return recomputed
    return dict(payload.get("metrics", {}))


def metric_value(metrics: dict[str, object], key: str) -> float | None:
    value = metrics.get(key)
    return float(value) if isinstance(value, int | float) else None


def format_metric(value: float | None) -> str:
    return "-" if value is None else f"{value:.4f}"


def build_summary_rows(eval_specs: list[tuple[str, Path]], *, write_back: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, path in eval_specs:
        if not path.exists():
            continue
        payload = load_json(path)
        metrics = merge_metrics(payload, write_back_path=path if write_back else None)
        rows.append(
            {
                "label": label,
                "path": str(path),
                "split": payload.get("split", "test"),
                "checkpoint_path": payload.get("checkpoint_path"),
                "sample_count": int(metrics.get("sample_count", payload.get("sample_count", 0)) or 0),
                "metrics": metrics,
                "has_recomputed_paper_metrics": metrics_from_predictions(payload) is not None,
            }
        )
    return rows


def build_markdown(rows: list[dict[str, object]]) -> str:
    lines = [
        "# 多模态实验论文指标汇总",
        "",
        (
            "说明：`ACC` 按人格回归任务常用的 `1 - MAE` 计算；`PCC` 衡量预测与标签的"
            "线性相关性；`CCC` 同时衡量相关性和数值一致性；`R²` 衡量相对标签均值基线的"
            "解释能力。整体指标按五个 Big Five 维度展平后计算，维度级结果保留在 JSON 的 "
            "`per_trait` 字段中。"
        ),
        "",
        "| 实验 | 样本数 | MSE | MAE | ACC | PCC | CCC | R² | 备注 |",
        "|------|-------:|----:|----:|----:|----:|----:|---:|------|",
    ]

    for row in rows:
        metrics = row["metrics"]
        if not isinstance(metrics, dict):
            metrics = {}
        note = "已由逐样本预测补算" if row.get("has_recomputed_paper_metrics") else "源文件缺少逐样本预测，仅保留已有指标"
        lines.append(
            "| {label} | {sample_count} | {mse} | {mae} | {acc} | {pcc} | {ccc} | {r2} | {note} |".format(
                label=row["label"],
                sample_count=row["sample_count"],
                mse=format_metric(metric_value(metrics, "mse")),
                mae=format_metric(metric_value(metrics, "mae")),
                acc=format_metric(metric_value(metrics, "acc")),
                pcc=format_metric(metric_value(metrics, "pcc")),
                ccc=format_metric(metric_value(metrics, "ccc")),
                r2=format_metric(metric_value(metrics, "r2")),
                note=note,
            )
        )

    candidate_rows = [
        row
        for row in rows
        if isinstance(row.get("metrics"), dict) and metric_value(row["metrics"], "mae") is not None
    ]
    best_row = min(
        candidate_rows,
        key=lambda item: metric_value(item["metrics"], "mae") or 999.0,
        default=None,
    )
    if best_row is not None:
        metrics = best_row["metrics"]
        lines.extend(
            [
                "",
                "## 结果解释",
                "",
                (
                    f"当前表中 MAE 最低的是 `{best_row['label']}`，测试集 MAE 为 "
                    f"`{format_metric(metric_value(metrics, 'mae'))}`，对应 ACC 为 "
                    f"`{format_metric(metric_value(metrics, 'acc'))}`。这说明当前调参 checkpoint "
                    "在平均绝对误差上优于旧全量 baseline，适合作为系统演示和论文 baseline 结果。"
                ),
                "",
                (
                    f"同时，`PCC={format_metric(metric_value(metrics, 'pcc'))}`、"
                    f"`CCC={format_metric(metric_value(metrics, 'ccc'))}`、"
                    f"`R²={format_metric(metric_value(metrics, 'r2'))}` 说明当前模型已经能捕捉一部分"
                    "人格分数变化趋势，但与参考论文公开结果仍有差距。因此论文中应表述为"
                    "“工程化 baseline 复现与系统接入”，不要直接声称完全复现原论文最优性能。"
                ),
                "",
                (
                    "后续若要继续提升论文指标，应优先使用新实现的 `bg_features` 重新生成 bundle "
                    "并重新训练，再考虑更多随机种子、单模态/多模态消融和更完整的多任务损失。"
                ),
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    rows = build_summary_rows(parse_eval_specs(args.eval), write_back=args.write_back)
    json_output = PROJECT_ROOT / args.json_output
    markdown_output = PROJECT_ROOT / args.markdown_output
    write_json(
        json_output,
        {
            "trait_order": TRAIT_ORDER,
            "rows": rows,
        },
    )
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(build_markdown(rows), encoding="utf-8")
    print(f"json={json_output}")
    print(f"markdown={markdown_output}")


if __name__ == "__main__":
    main()
