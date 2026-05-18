"""Write a Chinese markdown summary for MOL micro-expression experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _run_metrics(run: dict) -> dict:
    if isinstance(run.get("eval_metrics"), dict):
        return run["eval_metrics"]
    evaluation = run.get("evaluation") or {}
    return evaluation.get("metrics") or {}


def _format_float(value) -> str:
    if value is None:
        return "暂无"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "暂无"


def _format_counts(counts: dict | None) -> str:
    if not counts:
        return "暂无"
    return "，".join(f"{key}: {value}" for key, value in sorted(counts.items()))


def render_report_markdown(*, batch_summary: dict, ablation_summary: dict) -> str:
    lines = [
        "# MOL 微表情组会实验总结",
        "",
        "## 1. 当前接入状态",
        "",
        "- 已将 MOL 作为可选微表情模块接入多模态在线服务。",
        "- 在线服务会保存 `micro_expression_feature.json`，报告 API 会返回结构化 `micro_expression_summary`。",
        "- 聊天上下文已能读取微表情结果，并把它标注为短时面部线索。",
        "",
        "## 2. 批量提取结果",
        "",
        f"- 样本数：{batch_summary.get('sample_count', 0)}",
        f"- 成功数：{batch_summary.get('success_count', 0)}",
        f"- 失败数：{batch_summary.get('failure_count', 0)}",
        f"- 主导微表情分布：{_format_counts(batch_summary.get('dominant_counts'))}",
        "",
        "## 3. 小样本消融结果",
        "",
        "| Run | 是否使用微表情 | Best Loss | MAE | PCC | ACC |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]

    for run in ablation_summary.get("runs", []):
        metrics = _run_metrics(run)
        uses_micro = "是" if run.get("uses_micro_expression_features") else "否"
        lines.append(
            "| "
            f"{run.get('name', 'unknown')} | "
            f"{uses_micro} | "
            f"{_format_float(run.get('best_loss'))} | "
            f"{_format_float(metrics.get('mae'))} | "
            f"{_format_float(metrics.get('pcc'))} | "
            f"{_format_float(metrics.get('acc'))} |"
        )

    lines.extend(
        [
            "",
            "## 4. 初步结论",
            "",
            "- 当前结果首先证明微表情链路已经可以从真实帧数据批量产出 JSON，并进入主系统报告与对话。",
            "- no_micro / with_micro 的小样本消融入口已经跑通，后续可以替换为正式训练集和验证集。",
            "- 本次烟测样本很小，指标只用于检查实验流程，不能作为最终结论。",
            "",
            "## 5. 后续消融入口",
            "",
            "- 扩大训练/验证 bundle 数量，固定随机种子重复运行。",
            "- 比较 `no_micro`、`with_micro`，并补充只使用微表情分支或冻结主干的扩展实验。",
            "- 在表格中同时报告 MAE、ACC、PCC、CCC 和 R2，避免只看单个指标。",
            "",
            "## 6. 解释边界",
            "",
            "微表情只作为短时面部线索，不能直接代表稳定人格标签；最终解释仍以多模态主模型、实验样本量和报告使用边界为准。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Chinese MOL micro-expression experiment report")
    parser.add_argument("--batch-summary", required=True)
    parser.add_argument("--ablation-summary", required=True)
    parser.add_argument("--output", default="reports/MOL微表情组会实验总结.md")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    markdown = render_report_markdown(
        batch_summary=_load_json(args.batch_summary),
        ablation_summary=_load_json(args.ablation_summary),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"saved={output_path}")


if __name__ == "__main__":
    main()
