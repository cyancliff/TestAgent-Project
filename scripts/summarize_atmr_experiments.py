"""Collect ATMR experiment outputs into one paper-ready summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize ATMR-CAT experiment JSON files.")
    parser.add_argument("--input", default="reports/atmr_cat_experiments/atmr_cat_experiment.json")
    parser.add_argument("--output", default="reports/atmr_cat_experiments/summary.md")
    args = parser.parse_args()

    payload = json.loads((PROJECT_ROOT / args.input).read_text(encoding="utf-8-sig"))
    rows = payload.get("rows", [])
    lines = [
        "# ATMR-CAT 实验结论汇总",
        "",
        "| 每维题数 | 策略 | 潜变量 MAE | 后验不确定性 | 覆盖度 |",
        "|---------:|------|-----------:|-------------:|-------:|",
    ]
    for row in rows:
        lines.append(
            f"| {row.get('questions_per_module', 10)} | {row['strategy']} | {row['mae_to_latent']:.4f} | "
            f"{row['final_uncertainty']:.4f} | {row['coverage']:.4f} |"
        )
    grouped_counts = sorted({row.get("questions_per_module", 10) for row in rows})
    lines.extend(["", "## 分题量结论", ""])
    for count in grouped_counts:
        group = [row for row in rows if row.get("questions_per_module", 10) == count]
        best_mae = min(group, key=lambda row: row.get("mae_to_latent", 999), default=None)
        best_coverage = max(group, key=lambda row: row.get("coverage", -1), default=None)
        if best_mae and best_coverage:
            lines.append(
                f"- 每维 `{count}` 题：MAE 最低为 `{best_mae['strategy']}`（`{best_mae['mae_to_latent']:.4f}`），"
                f"覆盖度最高为 `{best_coverage['strategy']}`（`{best_coverage['coverage']:.4f}`）。"
            )
    lines.extend(
        [
            "",
            "建议将该结果作为自适应选题冷启动有效性的仿真实验证据；"
            "若准确性未显著优于随机策略，应重点表述覆盖度、收敛速度和解释证据多样性。",
        ]
    )
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"saved={output}")


if __name__ == "__main__":
    main()
