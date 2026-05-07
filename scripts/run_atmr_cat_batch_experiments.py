"""Run batch ATMR-CAT simulation sweeps across seeds and anomaly rates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

from run_atmr_cat_experiments import PROJECT_ROOT, load_questions, run_strategy


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_csv_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def summarize_rows(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[int, float, str], list[dict]] = {}
    for row in rows:
        key = (int(row["questions_per_module"]), float(row["anomaly_rate"]), str(row["strategy"]))
        grouped.setdefault(key, []).append(row)

    summary: list[dict] = []
    for (question_count, anomaly_rate, strategy), items in sorted(grouped.items()):
        mae_values = [float(item["mae_to_latent"]) for item in items]
        uncertainty_values = [float(item["final_uncertainty"]) for item in items]
        coverage_values = [float(item["coverage"]) for item in items]
        summary.append(
            {
                "questions_per_module": question_count,
                "anomaly_rate": anomaly_rate,
                "strategy": strategy,
                "seed_count": len(items),
                "mae_to_latent_mean": round(mean(mae_values), 4),
                "mae_to_latent_std": round(pstdev(mae_values), 4) if len(mae_values) > 1 else 0.0,
                "final_uncertainty_mean": round(mean(uncertainty_values), 4),
                "final_uncertainty_std": round(pstdev(uncertainty_values), 4) if len(uncertainty_values) > 1 else 0.0,
                "coverage_mean": round(mean(coverage_values), 4),
                "coverage_std": round(pstdev(coverage_values), 4) if len(coverage_values) > 1 else 0.0,
            }
        )
    return summary


def build_markdown(title: str, summary: list[dict]) -> str:
    lines = [
        f"# {title}",
        "",
        "| 每维题数 | 异常率 | 策略 | 种子数 | MAE 均值 | MAE 标准差 | 后验不确定性均值 | 覆盖度均值 |",
        "|---------:|------:|------|------:|---------:|-----------:|-----------------:|-----------:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['questions_per_module']} | {row['anomaly_rate']:.2f} | {row['strategy']} | "
            f"{row['seed_count']} | {row['mae_to_latent_mean']:.4f} | {row['mae_to_latent_std']:.4f} | "
            f"{row['final_uncertainty_mean']:.4f} | {row['coverage_mean']:.4f} |"
        )

    grouped_settings = sorted({(row["questions_per_module"], row["anomaly_rate"]) for row in summary})
    lines.extend(["", "## 分设置结论", ""])
    for question_count, anomaly_rate in grouped_settings:
        current = [
            row
            for row in summary
            if int(row["questions_per_module"]) == int(question_count)
            and float(row["anomaly_rate"]) == float(anomaly_rate)
        ]
        best_mae = min(current, key=lambda row: row["mae_to_latent_mean"])
        best_coverage = max(current, key=lambda row: row["coverage_mean"])
        lines.append(
            f"- 每维 `{question_count}` 题、异常率 `{anomaly_rate:.2f}`："
            f"MAE 最优为 `{best_mae['strategy']}`（`{best_mae['mae_to_latent_mean']:.4f}`），"
            f"覆盖度最优为 `{best_coverage['strategy']}`（`{best_coverage['coverage_mean']:.4f}`）。"
        )

    lines.extend(
        [
            "",
            "说明：该批实验用于验证 ATMR-CAT 在不同随机种子和异常注入条件下的稳定性。",
            "若 MAE 优势不显著，应重点表述覆盖度、收敛性与题目证据多样性的稳定收益。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run batched ATMR-CAT simulation sweeps.")
    parser.add_argument("--questions", default="data/atmr_calibrated_questions.json")
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--anomaly-rates", default="0.08")
    parser.add_argument("--seeds", default="42,43,44,45,46")
    parser.add_argument("--question-counts", default="10")
    parser.add_argument("--output-dir", default="reports/atmr_cat_batch_experiments")
    parser.add_argument("--title", default="ATMR-CAT 批量仿真实验")
    args = parser.parse_args()

    questions = load_questions(PROJECT_ROOT / args.questions)
    anomaly_rates = parse_csv_floats(args.anomaly_rates)
    seeds = parse_csv_ints(args.seeds)
    question_counts = parse_csv_ints(args.question_counts)

    rows: list[dict] = []
    for question_count in question_counts:
        for anomaly_rate in anomaly_rates:
            for seed in seeds:
                for index, strategy in enumerate(["fixed", "random", "atmr_cat"]):
                    rows.append(
                        run_strategy(
                            questions,
                            strategy=strategy,
                            users=args.users,
                            anomaly_rate=anomaly_rate,
                            seed=seed + index,
                            questions_per_module=question_count,
                        )
                    )

    summary = summarize_rows(rows)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "atmr_cat_batch_experiment.json").write_text(
        json.dumps(
            {
                "question_file": str(PROJECT_ROOT / args.questions),
                "users": args.users,
                "anomaly_rates": anomaly_rates,
                "seeds": seeds,
                "question_counts": question_counts,
                "rows": rows,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(build_markdown(args.title, summary), encoding="utf-8")
    print(f"saved={output_dir}")


if __name__ == "__main__":
    main()
