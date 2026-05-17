"""Check whether the MOL micro-expression meeting deliverables are present."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_BATCH_SUMMARY = Path("reports/mol_micro_batch_samm_limit6/summary.json")
DEFAULT_ABLATION_SUMMARY = Path("reports/micro_expression_ablation_smoke/ablation_summary.json")
DEFAULT_REPORT = Path("reports/MOL微表情组会实验总结.md")
DEFAULT_SAMPLE_TABLE = Path("reports/MOL微表情样本明细表.md")
DEFAULT_DOCS = [
    Path("docs/MOL微表情接入说明.md"),
    Path("docs/MOL微表情组会交付包.md"),
    Path("docs/MOL微表情复现实验命令清单.md"),
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _path_status(paths: list[Path]) -> tuple[list[str], list[str]]:
    checked = [str(path) for path in paths]
    missing = [str(path) for path in paths if not path.exists()]
    return checked, missing


def _summarize_batch(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"sample_count": 0, "success_count": 0, "failure_count": 0, "dominant_counts": {}}
    payload = _load_json(path)
    return {
        "sample_count": int(payload.get("sample_count") or 0),
        "success_count": int(payload.get("success_count") or 0),
        "failure_count": int(payload.get("failure_count") or 0),
        "dominant_counts": payload.get("dominant_counts") or {},
    }


def _summarize_ablation(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"runs": []}
    payload = _load_json(path)
    runs = []
    for run in payload.get("runs", []):
        metrics = run.get("eval_metrics") or (run.get("evaluation") or {}).get("metrics") or {}
        runs.append(
            {
                "name": run.get("name", "unknown"),
                "uses_micro_expression_features": bool(run.get("uses_micro_expression_features")),
                "best_loss": run.get("best_loss"),
                "mae": metrics.get("mae"),
                "pcc": metrics.get("pcc"),
                "acc": metrics.get("acc"),
            }
        )
    return {"runs": runs}


def check_deliverables(
    *,
    batch_summary_path: str | Path = DEFAULT_BATCH_SUMMARY,
    ablation_summary_path: str | Path = DEFAULT_ABLATION_SUMMARY,
    report_path: str | Path = DEFAULT_REPORT,
    sample_table_path: str | Path = DEFAULT_SAMPLE_TABLE,
    doc_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    batch_path = Path(batch_summary_path)
    ablation_path = Path(ablation_summary_path)
    report = Path(report_path)
    sample_table = Path(sample_table_path)
    docs = [Path(path) for path in (doc_paths if doc_paths is not None else DEFAULT_DOCS)]
    required_paths = [batch_path, ablation_path, report, sample_table, *docs]
    checked_paths, missing_paths = _path_status(required_paths)
    batch = _summarize_batch(batch_path)
    ablation = _summarize_ablation(ablation_path)
    run_names = {run["name"] for run in ablation["runs"]}
    ready = (
        not missing_paths
        and batch["sample_count"] > 0
        and batch["success_count"] > 0
        and batch["failure_count"] == 0
        and {"no_micro", "with_micro"}.issubset(run_names)
    )
    return {
        "ready": ready,
        "checked_paths": checked_paths,
        "missing_paths": missing_paths,
        "batch": batch,
        "ablation": ablation,
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "暂无"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_markdown_report(result: dict[str, Any]) -> str:
    batch = result.get("batch") or {}
    ablation = result.get("ablation") or {}
    lines = [
        "# MOL 微表情交付包自检报告",
        "",
        f"状态：{'通过' if result.get('ready') else '未通过'}",
        "",
        "## 1. 批量提取",
        "",
        f"- 样本数：{batch.get('sample_count', 0)}",
        f"- 成功数：{batch.get('success_count', 0)}",
        f"- 失败数：{batch.get('failure_count', 0)}",
        "",
        "## 2. 消融入口",
        "",
        "| Run | 使用微表情 | Best Loss | MAE | PCC | ACC |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for run in ablation.get("runs", []):
        uses_micro = "是" if run.get("uses_micro_expression_features") else "否"
        lines.append(
            "| "
            f"{run.get('name', 'unknown')} | "
            f"{uses_micro} | "
            f"{_format_value(run.get('best_loss'))} | "
            f"{_format_value(run.get('mae'))} | "
            f"{_format_value(run.get('pcc'))} | "
            f"{_format_value(run.get('acc'))} |"
        )

    lines.extend(["", "## 3. 路径检查", ""])
    for path in result.get("checked_paths", []):
        mark = "缺失" if path in set(result.get("missing_paths", [])) else "存在"
        lines.append(f"- {mark}：`{path}`")
    if result.get("missing_paths"):
        lines.extend(["", "## 4. 需要补齐", ""])
        for path in result["missing_paths"]:
            lines.append(f"- `{path}`")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check MOL micro-expression deliverables")
    parser.add_argument("--batch-summary", default=str(DEFAULT_BATCH_SUMMARY))
    parser.add_argument("--ablation-summary", default=str(DEFAULT_ABLATION_SUMMARY))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--sample-table", default=str(DEFAULT_SAMPLE_TABLE))
    parser.add_argument("--output-json", default="reports/micro_expression_deliverable_check.json")
    parser.add_argument("--output-md", default="reports/MOL微表情交付包自检报告.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = check_deliverables(
        batch_summary_path=args.batch_summary,
        ablation_summary_path=args.ablation_summary,
        report_path=args.report,
        sample_table_path=args.sample_table,
    )
    json_path = Path(args.output_json)
    md_path = Path(args.output_md)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(result), encoding="utf-8")
    print(f"ready={str(result['ready']).lower()} json={json_path} markdown={md_path}")


if __name__ == "__main__":
    main()
