"""Run robustness experiments for ATMR confidence-weighted reference scores."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIM = {"A": "6", "T": "4", "M": "5", "R": "7"}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def answer_confidence(risk_score: int | float, is_anomaly: bool) -> float:
    risk = max(0.0, min(float(risk_score or 0), 100.0))
    confidence = 1.0 - risk * 0.0065
    if is_anomaly:
        confidence -= 0.08
    return round(clamp(confidence, 0.2, 1.0), 3)


def load_questions(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    questions = []
    for item in payload:
        dim = str(item.get("examTypeId") or item.get("dimension_id") or "")
        module = next((key for key, value in MODULE_DIM.items() if value == dim), None)
        if not module:
            continue
        scores = [float(score) for score in item.get("scores", []) if str(score).strip()]
        questions.append(
            {
                "exam_no": item.get("examNo") or item.get("exam_no"),
                "module": module,
                "scores": scores or [1, 2, 3, 4, 5],
                "difficulty": float((item.get("simulation_truth") or {}).get("difficulty", item.get("difficulty") or 0.5)),
                "discrimination": float(
                    (item.get("simulation_truth") or {}).get("discrimination", item.get("discrimination") or 0.7)
                ),
            }
        )
    return questions


def simulate_clean_score(latent: float, question: dict, rng: random.Random) -> float:
    discrimination = max(float(question.get("discrimination") or 0.7), 0.1)
    difficulty = float(question.get("difficulty") or 0.5)
    noise = rng.gauss(0, 0.20 / discrimination)
    normalized = clamp(latent - (difficulty - 0.5) * 0.48 + noise)
    index = round(normalized * (len(question["scores"]) - 1))
    return float(question["scores"][index])


def corrupt_answer(clean_score: float, question: dict, rng: random.Random) -> dict:
    anomaly_type = rng.choice(["random_choice", "extreme_choice", "rapid_click", "repeated_pattern", "many_changes"])
    scores = [float(score) for score in question["scores"]]

    if anomaly_type == "random_choice":
        score = rng.choice(scores)
        risk_score = 70
        reasons = ["随机式异常作答"]
    elif anomaly_type == "extreme_choice":
        score = rng.choice([scores[0], scores[-1]])
        risk_score = 65
        reasons = ["极端选项集中"]
    elif anomaly_type == "rapid_click":
        score = rng.choice(scores)
        risk_score = 85
        reasons = ["作答时间明显过快", "短时间连续点击"]
    elif anomaly_type == "repeated_pattern":
        score = scores[-1]
        risk_score = 55
        reasons = ["连续多题选择同一选项"]
    else:
        score = clean_score
        risk_score = 50
        reasons = ["选项反复更改"]

    return {
        "score": score,
        "is_anomaly": True,
        "risk_score": risk_score,
        "risk_reasons": reasons,
        "answer_confidence": answer_confidence(risk_score, True),
    }


def clean_answer(score: float) -> dict:
    return {
        "score": score,
        "is_anomaly": False,
        "risk_score": 0,
        "risk_reasons": [],
        "answer_confidence": 1.0,
    }


def confidence_weighted_total(records: list[dict]) -> float:
    confidence_sum = sum(float(record.get("answer_confidence", 1.0)) for record in records)
    raw_total = sum(float(record["score"]) for record in records)
    if confidence_sum <= 0:
        return raw_total
    weighted_avg = sum(float(record["score"]) * float(record.get("answer_confidence", 1.0)) for record in records)
    weighted_avg /= confidence_sum
    return weighted_avg * len(records)


def top_module(scores_by_module: dict[str, float]) -> str:
    return max(sorted(scores_by_module), key=lambda module: scores_by_module[module])


def run_once(
    questions_by_module: dict[str, list[dict]],
    *,
    users: int,
    anomaly_rate: float,
    seed: int,
    questions_per_module: int,
) -> dict:
    rng = random.Random(seed)
    raw_errors = []
    weighted_errors = []
    normal_drifts = []
    confidence_values = []
    raw_top1_hits = 0
    weighted_top1_hits = 0

    for _ in range(users):
        latent = {module: rng.random() for module in MODULE_DIM}
        clean_totals = {}
        raw_totals = {}
        weighted_totals = {}
        user_confidences = []
        user_anomaly_count = 0

        for module, module_questions in questions_by_module.items():
            selected_questions = module_questions[:questions_per_module]
            clean_records = []
            corrupted_records = []
            for question in selected_questions:
                clean_score = simulate_clean_score(latent[module], question, rng)
                clean_records.append(clean_answer(clean_score))
                if rng.random() < anomaly_rate:
                    corrupted = corrupt_answer(clean_score, question, rng)
                    user_anomaly_count += 1
                else:
                    corrupted = clean_answer(clean_score)
                corrupted_records.append(corrupted)
                user_confidences.append(float(corrupted["answer_confidence"]))

            clean_total = sum(record["score"] for record in clean_records)
            raw_total = sum(record["score"] for record in corrupted_records)
            weighted_total = confidence_weighted_total(corrupted_records)
            clean_totals[module] = clean_total
            raw_totals[module] = raw_total
            weighted_totals[module] = weighted_total
            raw_errors.append(abs(raw_total - clean_total))
            weighted_errors.append(abs(weighted_total - clean_total))
            normal_drifts.append(abs(weighted_total - raw_total))

        clean_top = top_module(clean_totals)
        raw_top1_hits += int(top_module(raw_totals) == clean_top)
        weighted_top1_hits += int(top_module(weighted_totals) == clean_top)
        assessment_confidence = mean(user_confidences) - min(0.01 * user_anomaly_count, 0.12)
        confidence_values.append(clamp(assessment_confidence))

    raw_mae = mean(raw_errors)
    weighted_mae = mean(weighted_errors)
    return {
        "seed": seed,
        "users": users,
        "questions_per_module": questions_per_module,
        "anomaly_rate": anomaly_rate,
        "raw_mae_to_clean": round(raw_mae, 4),
        "weighted_mae_to_clean": round(weighted_mae, 4),
        "improvement": round(raw_mae - weighted_mae, 4),
        "normal_drift": round(mean(normal_drifts), 4),
        "top1_consistency_raw": round(raw_top1_hits / users, 4),
        "top1_consistency_weighted": round(weighted_top1_hits / users, 4),
        "assessment_confidence_avg": round(mean(confidence_values), 4),
    }


def summarize(rows: list[dict]) -> list[dict]:
    grouped: dict[float, list[dict]] = {}
    for row in rows:
        grouped.setdefault(float(row["anomaly_rate"]), []).append(row)

    summary = []
    for anomaly_rate, items in sorted(grouped.items()):
        summary.append(
            {
                "anomaly_rate": anomaly_rate,
                "raw_mae_to_clean": round(mean(item["raw_mae_to_clean"] for item in items), 4),
                "weighted_mae_to_clean": round(mean(item["weighted_mae_to_clean"] for item in items), 4),
                "improvement": round(mean(item["improvement"] for item in items), 4),
                "normal_drift": round(mean(item["normal_drift"] for item in items), 4),
                "top1_consistency_raw": round(mean(item["top1_consistency_raw"] for item in items), 4),
                "top1_consistency_weighted": round(mean(item["top1_consistency_weighted"] for item in items), 4),
                "assessment_confidence_avg": round(mean(item["assessment_confidence_avg"] for item in items), 4),
            }
        )
    return summary


def build_markdown(rows: list[dict], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "| 异常注入率 | 普通得分 MAE | 可信度加权 MAE | 改善幅度 | 正常/参考漂移 | Top-1 一致率(普通) | Top-1 一致率(加权) | 平均整体可信度 |",
        "|----------:|-------------:|----------------:|---------:|-------------:|------------------:|------------------:|---------------:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['anomaly_rate']:.2f} | {row['raw_mae_to_clean']:.4f} | "
            f"{row['weighted_mae_to_clean']:.4f} | {row['improvement']:.4f} | "
            f"{row['normal_drift']:.4f} | {row['top1_consistency_raw']:.4f} | "
            f"{row['top1_consistency_weighted']:.4f} | {row['assessment_confidence_avg']:.4f} |"
        )
    lines.extend(
        [
            "",
            "说明：原始 ATMR 得分仍作为主画像结果；可信度加权得分只作为稳健性参考和异常干扰实验对照。",
            "该实验验证的是可控异常干扰下的鲁棒性，不用于证明 ATMR 量表的真实心理效度。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ATMR confidence-weighted reference scores under anomalies.")
    parser.add_argument("--questions", default="data/atmr_calibrated_questions.json")
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--question-count", type=int, default=10)
    parser.add_argument("--anomaly-rates", default="0,0.05,0.10,0.20,0.30")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--output-dir", default="reports/atmr_confidence_weighting_experiments")
    args = parser.parse_args()

    questions = load_questions(PROJECT_ROOT / args.questions)
    questions_by_module = {
        module: [question for question in questions if question["module"] == module]
        for module in MODULE_DIM
    }
    anomaly_rates = [float(part.strip()) for part in args.anomaly_rates.split(",") if part.strip()]
    seeds = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]

    rows = []
    for anomaly_rate in anomaly_rates:
        for seed in seeds:
            rows.append(
                run_once(
                    questions_by_module,
                    users=args.users,
                    anomaly_rate=anomaly_rate,
                    seed=seed,
                    questions_per_module=args.question_count,
                )
            )

    summary = summarize(rows)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "confidence_weighting_experiment.json").write_text(
        json.dumps(
            {
                "question_file": str(PROJECT_ROOT / args.questions),
                "users": args.users,
                "question_count": args.question_count,
                "seeds": seeds,
                "rows": rows,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "confidence_weighting_experiment.md").write_text(
        build_markdown(rows, "ATMR 可信度加权逐种子实验"),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        build_markdown(summary, "ATMR 可信度加权稳健性实验汇总"),
        encoding="utf-8",
    )
    print(f"saved={output_dir}")


if __name__ == "__main__":
    main()
