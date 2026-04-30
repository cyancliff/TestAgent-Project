"""Run simulation experiments for ATMR-CAT vs fixed/random selection."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIM = {"A": "6", "T": "4", "M": "5", "R": "7"}


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
                "difficulty": float(item.get("difficulty") or 0.5),
                "discrimination": float(item.get("discrimination") or 0.7),
                "true_difficulty": float((item.get("simulation_truth") or {}).get("difficulty", item.get("difficulty") or 0.5)),
                "true_discrimination": float(
                    (item.get("simulation_truth") or {}).get("discrimination", item.get("discrimination") or 0.7)
                ),
                "feature": _question_feature(item),
            }
        )
    return questions


def _question_feature(item: dict) -> list[float]:
    text = (item.get("exam") or "") + " " + " ".join(item.get("options") or [])
    length = min(len(text) / 120.0, 1.0)
    return [
        length,
        1.0 if "人" in text else 0.0,
        1.0 if "目标" in text or "计划" in text else 0.0,
        1.0 if "责任" in text or "承诺" in text else 0.0,
        1.0 if "情绪" in text or "冲突" in text else 0.0,
    ]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def simulate_answer(latent: float, question: dict, rng: random.Random, anomaly_rate: float) -> tuple[float, bool]:
    if rng.random() < anomaly_rate:
        return rng.choice(question["scores"]), True
    true_discrimination = max(float(question.get("true_discrimination") or question["discrimination"]), 0.1)
    true_difficulty = float(question.get("true_difficulty") or question["difficulty"])
    noise = rng.gauss(0, 0.23 / true_discrimination)
    normalized = max(0.0, min(1.0, latent - (true_difficulty - 0.5) * 0.48 + noise))
    index = round(normalized * (len(question["scores"]) - 1))
    return question["scores"][index], False


def select_question(strategy: str, candidates: list[dict], answered: list[dict], ability: float, uncertainty: float, rng: random.Random) -> dict:
    if strategy == "random":
        return rng.choice(candidates)
    if strategy == "fixed" or not answered:
        return candidates[0]

    answered_features = [item["question"]["feature"] for item in answered]
    best = None
    best_score = -1.0
    uncertainty_ratio = min(uncertainty / 0.25, 1.0)
    w_fisher = 0.15 + 0.25 * uncertainty_ratio
    w_coverage = 0.40 - 0.15 * uncertainty_ratio
    w_difficulty = 0.25 - 0.05 * uncertainty_ratio
    w_discrimination = 0.20 - 0.05 * uncertainty_ratio

    for question in candidates:
        difficulty = question["difficulty"]
        discrimination = question["discrimination"]
        fisher = min((discrimination**2) * math.exp(-((difficulty - ability) ** 2) / (2 * 0.15)), 1.0)
        coverage = 1.0 - mean([abs(cosine(question["feature"], feature)) for feature in answered_features])
        difficulty_match = 1.0 - abs(difficulty - ability)
        score = w_fisher * fisher + w_coverage * coverage + w_difficulty * difficulty_match + w_discrimination * discrimination
        if score > best_score:
            best = question
            best_score = score
    return best or candidates[0]


def run_strategy(
    questions: list[dict],
    strategy: str,
    users: int,
    anomaly_rate: float,
    seed: int,
    questions_per_module: int,
) -> dict:
    rng = random.Random(seed)
    errors = []
    final_uncertainties = []
    coverage_scores = []
    anomaly_hits = 0
    for _ in range(users):
        latent = {module: rng.random() for module in MODULE_DIM}
        for module in MODULE_DIM:
            module_questions = [question for question in questions if question["module"] == module]
            answered = []
            ability = 0.5
            uncertainty = 0.25
            while len(answered) < min(questions_per_module, len(module_questions)):
                candidates = [question for question in module_questions if question["exam_no"] not in {item["question"]["exam_no"] for item in answered}]
                question = select_question(strategy, candidates, answered, ability, uncertainty, rng)
                score, is_anomaly = simulate_answer(latent[module], question, rng, anomaly_rate)
                weight = 0.45 if is_anomaly else 1.0
                normalized_score = (score - 1.0) / 4.0
                obs_precision = question["discrimination"] * 2.0 * weight
                prior_precision = 1.0 / uncertainty
                posterior_precision = prior_precision + obs_precision
                ability = (prior_precision * ability + obs_precision * normalized_score) / posterior_precision
                uncertainty = 1.0 / posterior_precision
                answered.append({"question": question, "score": score, "is_anomaly": is_anomaly})
                anomaly_hits += int(is_anomaly)
            errors.append(abs(ability - latent[module]))
            final_uncertainties.append(uncertainty)
            if len(answered) > 1:
                similarities = [
                    abs(cosine(answered[i]["question"]["feature"], answered[j]["question"]["feature"]))
                    for i in range(len(answered))
                    for j in range(i)
                ]
                coverage_scores.append(1.0 - mean(similarities))
    return {
        "strategy": strategy,
        "users": users,
        "questions_per_module": questions_per_module,
        "anomaly_rate": anomaly_rate,
        "mae_to_latent": round(mean(errors), 4),
        "final_uncertainty": round(mean(final_uncertainties), 4),
        "coverage": round(mean(coverage_scores), 4),
        "anomaly_answers": anomaly_hits,
    }


def build_markdown(rows: list[dict]) -> str:
    lines = [
        "# ATMR-CAT 自适应选题仿真实验",
        "",
        "| 每维题数 | 策略 | 用户数 | 异常率 | 潜变量 MAE | 后验不确定性 | 题目覆盖度 | 异常答案数 |",
        "|---------:|------|------:|------:|-----------:|-------------:|-----------:|-----------:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['questions_per_module']} | {row['strategy']} | {row['users']} | {row['anomaly_rate']:.2f} | {row['mae_to_latent']:.4f} | "
            f"{row['final_uncertainty']:.4f} | {row['coverage']:.4f} | {row['anomaly_answers']} |"
        )
    lines.extend(
        [
            "",
            "说明：潜变量 MAE 越低越好；后验不确定性越低说明画像收敛更快；题目覆盖度越高说明重复测量越少。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare fixed, random, and ATMR-CAT selection with simulated users.")
    parser.add_argument("--questions", default="data/atmr_full_questions.json")
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--anomaly-rate", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--question-counts",
        default="10",
        help="Comma-separated questions per module, e.g. 4,6,8,10.",
    )
    parser.add_argument("--output-dir", default="reports/atmr_cat_experiments")
    args = parser.parse_args()

    questions = load_questions(PROJECT_ROOT / args.questions)
    question_counts = [int(part.strip()) for part in args.question_counts.split(",") if part.strip()]
    rows = []
    for count_index, questions_per_module in enumerate(question_counts):
        rows.extend(
            run_strategy(
                questions,
                strategy,
                args.users,
                args.anomaly_rate,
                args.seed + count_index * 10 + index,
                questions_per_module,
            )
            for index, strategy in enumerate(["fixed", "random", "atmr_cat"])
        )
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "atmr_cat_experiment.json").write_text(
        json.dumps(
            {
                "question_file": str(PROJECT_ROOT / args.questions),
                "question_counts": question_counts,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "atmr_cat_experiment.md").write_text(build_markdown(rows), encoding="utf-8")
    print(f"saved={output_dir}")


if __name__ == "__main__":
    main()
