"""Trust, confidence, and evidence-chain helpers for ATMR reports."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from app.core.constants import DIMENSION_MAX_SCORE, MODULE_DISPLAY_NAMES, MODULE_DIM_MAP, STAGE_QUESTION_COUNT


MODULE_BY_DIMENSION = {dimension_id: module for module, dimension_id in MODULE_DIM_MAP.items()}


def _value(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def confidence_label(confidence: float) -> str:
    if confidence >= 0.8:
        return "较高"
    if confidence >= 0.6:
        return "中等"
    return "较低"


def calculate_answer_confidence(
    *,
    risk_score: int | float | None = None,
    is_anomaly: bool = False,
    user_explanation: str | None = None,
) -> float:
    """Convert behavior risk into a 0-1 item confidence score."""

    del user_explanation  # Legacy argument kept for backward compatibility.
    risk = clamp(_safe_float(risk_score), 0.0, 100.0)
    confidence = 1.0 - risk * 0.0065
    if is_anomaly:
        confidence -= 0.08

    return round(clamp(confidence, 0.2, 1.0), 3)


def build_answer_insight(record: Any, question: Any | None = None) -> dict[str, Any]:
    risk_score = _safe_int(_value(record, "risk_score", 70 if _value(record, "is_anomaly", 0) else 0))
    is_anomaly = bool(_value(record, "is_anomaly", 0))
    confidence = _value(record, "answer_confidence")
    if confidence is None:
        confidence = calculate_answer_confidence(
            risk_score=risk_score,
            is_anomaly=is_anomaly,
            user_explanation=_value(record, "user_explanation"),
        )

    risk_reasons = _value(record, "risk_reasons", []) or []
    if isinstance(risk_reasons, str):
        risk_reasons = [risk_reasons]

    score = _safe_float(_value(record, "score"))
    dim_id = getattr(question, "dimension_id", None) if question is not None else _value(record, "dimension_id")
    module = MODULE_BY_DIMENSION.get(dim_id) or _value(record, "module")

    return {
        "exam_no": _value(record, "exam_no"),
        "module": module,
        "module_name": MODULE_DISPLAY_NAMES.get(module, module) if module else None,
        "trait_label": getattr(question, "trait_label", None) if question is not None else _value(record, "trait_label"),
        "score": score,
        "risk_score": risk_score,
        "risk_reasons": risk_reasons,
        "answer_confidence": round(_safe_float(confidence, 1.0), 3),
        "behavior_metrics": _value(record, "behavior_metrics", {}) or {},
        "is_anomaly": is_anomaly,
        "support_strength": _support_strength(score),
    }


def build_assessment_trust_summary(answer_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not answer_items:
        return {
            "assessment_confidence": 0.0,
            "label": "较低",
            "anomaly_count": 0,
            "risk_score_avg": 0.0,
            "dimension_confidence": {},
            "notes": ["暂无答题记录，无法计算可信度。"],
        }

    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in answer_items:
        module = item.get("module")
        if module:
            by_module[module].append(item)

    dimension_confidence = {}
    all_confidences = []
    all_risks = []
    anomaly_count = 0
    for module in ["A", "T", "M", "R"]:
        records = by_module.get(module, [])
        if not records:
            dimension_confidence[module] = {
                "confidence": 0.0,
                "label": "较低",
                "anomaly_count": 0,
                "question_count": 0,
                "note": "该维度暂无有效答题记录。",
            }
            continue

        confidences = [_safe_float(record.get("answer_confidence"), 1.0) for record in records]
        risks = [_safe_float(record.get("risk_score"), 0.0) for record in records]
        anomalies = sum(1 for record in records if record.get("is_anomaly"))
        completion = min(len(records) / max(STAGE_QUESTION_COUNT.get(module, 10), 1), 1.0)
        module_confidence = clamp(mean(confidences) * (0.85 + 0.15 * completion) - anomalies * 0.015)

        all_confidences.extend(confidences)
        all_risks.extend(risks)
        anomaly_count += anomalies
        dimension_confidence[module] = {
            "confidence": round(module_confidence, 3),
            "label": confidence_label(module_confidence),
            "anomaly_count": anomalies,
            "question_count": len(records),
            "risk_score_avg": round(mean(risks), 1) if risks else 0.0,
            "note": _dimension_note(module_confidence, anomalies),
        }

    assessment_confidence = clamp(mean(all_confidences) - min(anomaly_count * 0.01, 0.12)) if all_confidences else 0.0
    return {
        "assessment_confidence": round(assessment_confidence, 3),
        "label": confidence_label(assessment_confidence),
        "anomaly_count": anomaly_count,
        "risk_score_avg": round(mean(all_risks), 1) if all_risks else 0.0,
        "dimension_confidence": dimension_confidence,
        "notes": _assessment_notes(assessment_confidence, anomaly_count),
    }


def build_confidence_weighted_score_reference(
    records: list[dict[str, Any]],
    *,
    weight_bonus: float = 0.0,
    primary_total_score: float = 0.0,
    max_score: float = DIMENSION_MAX_SCORE,
) -> dict[str, Any]:
    """Calculate a confidence-weighted reference score without replacing raw scoring."""

    if not records:
        return {
            "confidence_weighted_raw_score": 0.0,
            "confidence_weighted_score": 0.0,
            "confidence_weighted_percentage": 0.0,
            "confidence_weighted_delta": 0.0,
        }

    raw_total = sum(_safe_float(record.get("score"), 0.0) for record in records)
    confidence_sum = 0.0
    weighted_score_sum = 0.0
    for record in records:
        confidence_value = record.get("answer_confidence")
        confidence = 1.0 if confidence_value is None else clamp(_safe_float(confidence_value, 1.0))
        confidence_sum += confidence
        weighted_score_sum += confidence * _safe_float(record.get("score"), 0.0)

    weighted_avg = (weighted_score_sum / confidence_sum) if confidence_sum > 0 else raw_total / len(records)
    confidence_weighted_raw_score = weighted_avg * len(records)
    confidence_weighted_score = max(0.0, min(confidence_weighted_raw_score + _safe_float(weight_bonus), max_score))
    max_possible = len(records) * 5.0
    confidence_weighted_percentage = (
        confidence_weighted_score / max_possible * 100 if max_possible > 0 else 0.0
    )
    confidence_weighted_delta = confidence_weighted_score - _safe_float(primary_total_score)

    return {
        "confidence_weighted_raw_score": round(confidence_weighted_raw_score, 2),
        "confidence_weighted_score": round(confidence_weighted_score, 2),
        "confidence_weighted_percentage": round(confidence_weighted_percentage, 1),
        "confidence_weighted_delta": round(confidence_weighted_delta, 2),
    }


def build_evidence_chain(answer_items: list[dict[str, Any]], *, max_per_module: int = 3) -> dict[str, Any]:
    by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in answer_items:
        module = item.get("module")
        if module:
            by_module[module].append(item)

    modules = {}
    highlights = []
    for module in ["A", "T", "M", "R"]:
        records = by_module.get(module, [])
        ranked = sorted(
            records,
            key=lambda item: (
                bool(item.get("is_anomaly")),
                abs(_safe_float(item.get("score"), 3.0) - 3.0),
                _safe_float(item.get("answer_confidence"), 1.0),
            ),
            reverse=True,
        )
        evidence = [_compact_evidence_item(item) for item in ranked[:max_per_module]]
        modules[module] = {
            "module_name": MODULE_DISPLAY_NAMES.get(module, module),
            "evidence": evidence,
        }
        highlights.extend(evidence[:1])

    return {
        "strategy": "ATMR evidence-chain v1",
        "modules": modules,
        "highlights": highlights,
    }


def build_adaptive_metrics(answer_items: list[dict[str, Any]]) -> dict[str, Any]:
    if not answer_items:
        return {"algorithm": "ATMR-CAT", "question_count": 0}

    confidences = [_safe_float(item.get("answer_confidence"), 1.0) for item in answer_items]
    anomaly_count = sum(1 for item in answer_items if item.get("is_anomaly"))
    modules = sorted({item.get("module") for item in answer_items if item.get("module")})
    return {
        "algorithm": "ATMR-CAT",
        "question_count": len(answer_items),
        "covered_modules": modules,
        "coverage_ratio": round(len(modules) / 4.0, 3),
        "mean_answer_confidence": round(mean(confidences), 3),
        "anomaly_ratio": round(anomaly_count / max(len(answer_items), 1), 3),
        "selection_objective": "Bayesian posterior + Fisher information + coverage + difficulty match + discrimination",
    }


def _support_strength(score: float) -> str:
    if score >= 4:
        return "强支持"
    if score >= 3:
        return "中等支持"
    if score >= 2:
        return "弱支持"
    return "不支持"


def _dimension_note(confidence: float, anomaly_count: int) -> str:
    if confidence >= 0.8 and anomaly_count == 0:
        return "该维度作答稳定，结论可作为主要参考。"
    if confidence >= 0.6:
        return "该维度整体可参考，但需结合异常记录谨慎解释。"
    return "该维度证据稳定性不足，建议结合复测或其他证据。"


def _assessment_notes(confidence: float, anomaly_count: int) -> list[str]:
    notes = []
    if confidence >= 0.8:
        notes.append("本次测评作答质量较高，整体画像可信度较好。")
    elif confidence >= 0.6:
        notes.append("本次测评可信度中等，报告结论适合做倾向性参考。")
    else:
        notes.append("本次测评可信度偏低，报告结论需要谨慎使用。")
    if anomaly_count:
        notes.append(f"检测到 {anomaly_count} 条异常作答，相关题目已在评分和解释中降权。")
    return notes


def _compact_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "exam_no": item.get("exam_no"),
        "trait_label": item.get("trait_label"),
        "score": item.get("score"),
        "support_strength": item.get("support_strength"),
        "risk_score": item.get("risk_score", 0),
        "answer_confidence": item.get("answer_confidence", 1.0),
        "behavior_metrics": item.get("behavior_metrics", {}) or {},
        "is_anomaly": bool(item.get("is_anomaly")),
        "risk_reasons": item.get("risk_reasons", []),
    }
