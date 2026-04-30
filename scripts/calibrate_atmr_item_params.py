"""Cold-start calibrate ATMR item parameters with simulated user responses.

This script is intentionally a controlled simulation tool. It does not claim
psychometric validity from real users; it provides cold-start difficulty and
discrimination estimates so ATMR-CAT can be evaluated before large response
logs are available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIM = {"A": "6", "T": "4", "M": "5", "R": "7"}


def stable_unit(value: str, *, salt: str = "") -> float:
    digest = hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 3:
        return 0.0
    mean_x = mean(xs)
    mean_y = mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 1e-12 or var_y <= 1e-12:
        return 0.0
    return cov / math.sqrt(var_x * var_y)


def module_for_item(item: dict[str, Any]) -> str | None:
    dim = str(item.get("examTypeId") or item.get("dimension_id") or "")
    return next((module for module, dimension_id in MODULE_DIM.items() if dimension_id == dim), None)


def item_text(item: dict[str, Any]) -> str:
    return (item.get("exam") or item.get("content") or "") + " " + " ".join(item.get("options") or [])


def derive_simulation_truth(item: dict[str, Any], *, seed: int) -> dict[str, float]:
    exam_no = str(item.get("examNo") or item.get("exam_no") or "")
    text = item_text(item)
    length_factor = clamp(len(text) / 160.0)
    semantic_factor = 0.0
    for keyword in ["目标", "计划", "责任", "冲突", "压力", "表达", "理解"]:
        semantic_factor += 0.025 if keyword in text else 0.0

    base_difficulty = 0.18 + 0.64 * stable_unit(exam_no, salt=f"difficulty-{seed}")
    true_difficulty = clamp(base_difficulty + (length_factor - 0.5) * 0.12, 0.08, 0.92)

    base_discrimination = 0.35 + 0.65 * stable_unit(exam_no, salt=f"discrimination-{seed}")
    true_discrimination = clamp(base_discrimination + semantic_factor, 0.25, 1.15)
    return {
        "difficulty": round(true_difficulty, 4),
        "discrimination": round(true_discrimination, 4),
    }


def normalized_score_from_response(latent: float, truth: dict[str, float], rng: random.Random, anomaly_rate: float) -> tuple[float, bool]:
    if rng.random() < anomaly_rate:
        return rng.random(), True

    discrimination = max(float(truth["discrimination"]), 0.1)
    difficulty = float(truth["difficulty"])
    noise = rng.gauss(0.0, 0.23 / discrimination)
    response = latent - (difficulty - 0.5) * 0.48 + noise
    return clamp(response), False


def score_to_option_value(normalized: float, score_count: int) -> float:
    if score_count <= 1:
        return 1.0
    index = round(normalized * (score_count - 1))
    return float(index + 1)


def calibrate_item(
    item: dict[str, Any],
    *,
    users: int,
    anomaly_rate: float,
    rng: random.Random,
    truth: dict[str, float],
) -> dict[str, Any]:
    module = module_for_item(item)
    score_count = max(len(item.get("scores") or []), 5)
    latent_values = []
    response_values = []
    anomaly_count = 0
    for _ in range(users):
        latent = rng.betavariate(2.2, 2.2)
        normalized, is_anomaly = normalized_score_from_response(latent, truth, rng, anomaly_rate)
        latent_values.append(latent)
        response_values.append((score_to_option_value(normalized, score_count) - 1.0) / max(score_count - 1, 1))
        anomaly_count += int(is_anomaly)

    avg_response = mean(response_values)
    raw_corr = pearson(latent_values, response_values)
    estimated_difficulty = clamp(1.0 - avg_response, 0.05, 0.95)
    estimated_discrimination = clamp(0.25 + abs(raw_corr) * 0.95, 0.25, 1.2)

    quality = "high" if abs(raw_corr) >= 0.55 else "medium" if abs(raw_corr) >= 0.35 else "low"
    calibrated = dict(item)
    calibrated["difficulty"] = round(estimated_difficulty, 4)
    calibrated["discrimination"] = round(estimated_discrimination, 4)
    calibrated["calibration"] = {
        "method": "simulated-user-cold-start-v1",
        "module": module,
        "simulated_users": users,
        "anomaly_rate": anomaly_rate,
        "mean_normalized_score": round(avg_response, 4),
        "latent_score_correlation": round(raw_corr, 4),
        "quality": quality,
        "anomaly_count": anomaly_count,
    }
    calibrated["simulation_truth"] = {
        "difficulty": truth["difficulty"],
        "discrimination": truth["discrimination"],
    }
    return calibrated


def build_markdown(calibrated_items: list[dict[str, Any]], *, users: int, anomaly_rate: float) -> str:
    module_rows = []
    for module in MODULE_DIM:
        items = [item for item in calibrated_items if (item.get("calibration") or {}).get("module") == module]
        if not items:
            continue
        difficulties = [float(item["difficulty"]) for item in items]
        discriminations = [float(item["discrimination"]) for item in items]
        low_quality = sum(1 for item in items if item["calibration"]["quality"] == "low")
        module_rows.append(
            {
                "module": module,
                "count": len(items),
                "difficulty_mean": mean(difficulties),
                "difficulty_min": min(difficulties),
                "difficulty_max": max(difficulties),
                "discrimination_mean": mean(discriminations),
                "discrimination_min": min(discriminations),
                "discrimination_max": max(discriminations),
                "low_quality": low_quality,
            }
        )

    lines = [
        "# ATMR 题库模拟冷启动校准报告",
        "",
        "## 实验边界",
        "",
        (
            "本报告基于模拟用户响应生成题目难度和区分度的冷启动估计。"
            "该结果用于验证 ATMR-CAT 选题策略在可控条件下的收敛性和鲁棒性，"
            "不用于证明 ATMR 量表的真实心理测量效度。"
        ),
        "",
        f"- 模拟用户数/题：`{users}`",
        f"- 注入异常率：`{anomaly_rate:.2f}`",
        "- 难度估计：由题目平均归一化得分反推，平均得分越低则难度越高。",
        "- 区分度估计：由题目得分与对应维度潜变量的相关性估计。",
        "",
        "## 分维度校准概览",
        "",
        "| 维度 | 题数 | 难度均值 | 难度范围 | 区分度均值 | 区分度范围 | 低质量题数 |",
        "|------|----:|---------:|----------|-----------:|------------|-----------:|",
    ]
    for row in module_rows:
        lines.append(
            "| {module} | {count} | {difficulty_mean:.3f} | {difficulty_min:.3f}-{difficulty_max:.3f} | "
            "{discrimination_mean:.3f} | {discrimination_min:.3f}-{discrimination_max:.3f} | {low_quality} |".format(**row)
        )

    top_items = sorted(
        calibrated_items,
        key=lambda item: float(item.get("discrimination") or 0.0),
        reverse=True,
    )[:10]
    lines.extend(
        [
            "",
            "## 高区分度题目 Top 10",
            "",
            "| 题号 | 维度 | 难度 | 区分度 | 相关性 | 质量 |",
            "|------|------|-----:|-------:|-------:|------|",
        ]
    )
    for item in top_items:
        cal = item["calibration"]
        lines.append(
            f"| {item.get('examNo') or item.get('exam_no')} | {cal['module']} | {float(item['difficulty']):.3f} | "
            f"{float(item['discrimination']):.3f} | {cal['latent_score_correlation']:.3f} | {cal['quality']} |"
        )

    lines.extend(
        [
            "",
            "## 论文表述建议",
            "",
            (
                "建议表述为：在缺少大规模真实作答数据的情况下，本文构建模拟用户响应机制，"
                "对 ATMR 题库参数进行冷启动校准；该机制不替代真实用户数据校准，但可用于"
                "验证自适应选题策略在可控条件下的收敛性、覆盖度和异常鲁棒性。"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Cold-start calibrate ATMR item difficulty/discrimination.")
    parser.add_argument("--questions", default="data/atmr_full_questions.json")
    parser.add_argument("--users", type=int, default=5000)
    parser.add_argument("--anomaly-rate", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=20260429)
    parser.add_argument("--output", default="data/atmr_calibrated_questions.json")
    parser.add_argument("--report-dir", default="reports/atmr_item_calibration")
    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.questions
    items = json.loads(input_path.read_text(encoding="utf-8-sig"))
    rng = random.Random(args.seed)
    calibrated_items = []
    for item in items:
        module = module_for_item(item)
        if module is None:
            calibrated_items.append(item)
            continue
        truth = derive_simulation_truth(item, seed=args.seed)
        calibrated_items.append(
            calibrate_item(
                item,
                users=args.users,
                anomaly_rate=args.anomaly_rate,
                rng=rng,
                truth=truth,
            )
        )

    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(calibrated_items, ensure_ascii=False, indent=2), encoding="utf-8")

    report_dir = PROJECT_ROOT / args.report_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    report_payload = {
        "source": str(input_path),
        "output": str(output_path),
        "users": args.users,
        "anomaly_rate": args.anomaly_rate,
        "seed": args.seed,
        "calibrated_item_count": sum(1 for item in calibrated_items if "calibration" in item),
    }
    (report_dir / "calibration_summary.json").write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (report_dir / "calibration_report.md").write_text(
        build_markdown(calibrated_items, users=args.users, anomaly_rate=args.anomaly_rate),
        encoding="utf-8",
    )
    print(f"output={output_path}")
    print(f"report={report_dir}")


if __name__ == "__main__":
    main()
