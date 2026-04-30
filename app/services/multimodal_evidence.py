"""Quality, confidence, and ATMR-Big Five consistency helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.core.constants import MODULE_DISPLAY_NAMES, MODULE_DIM_MAP
from app.models.assessment import AnswerRecord, Question


BIG_FIVE_LABELS = {
    "openness": "开放性",
    "conscientiousness": "尽责性",
    "extraversion": "外向性",
    "agreeableness": "宜人性",
    "neuroticism": "神经质",
}


def _read_json(path_value: str | None) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _score_label(score: float) -> str:
    if score >= 0.8:
        return "较高"
    if score >= 0.6:
        return "中等"
    return "较低"


def _numeric_list_2d(values: Any) -> list[list[float]]:
    if not isinstance(values, list):
        return []
    if values and isinstance(values[0], (int, float)):
        return [[float(value) for value in values]]
    return [
        [float(value) for value in row]
        for row in values
        if isinstance(row, list) and all(isinstance(value, (int, float)) for value in row)
    ]


def _sequence_activity(rows: list[list[float]]) -> float:
    if not rows:
        return 0.0
    non_zero_rows = [row for row in rows if any(abs(value) > 1e-8 for value in row)]
    return len(non_zero_rows) / max(len(rows), 1)


def build_modality_quality_summary(artifacts: dict[str, str] | None, errors: list[str] | None = None) -> dict[str, Any]:
    artifacts = artifacts or {}
    errors = errors or []
    clip_payload = _read_json(artifacts.get("clip_feature_path"))
    wav_payload = _read_json(artifacts.get("wav2clip_feature_path"))
    bg_payload = _read_json(artifacts.get("bg_feature_path"))

    transcript_value = artifacts.get("transcript_path")
    transcript_path = Path(transcript_value) if transcript_value else None
    transcript = (
        transcript_path.read_text(encoding="utf-8", errors="ignore")
        if transcript_path is not None and transcript_path.is_file()
        else ""
    )
    words = re.findall(r"[A-Za-z\u4e00-\u9fff]+", transcript)
    sentences = [part for part in re.split(r"[.!?。！？]+", transcript) if part.strip()]

    image_rows = _numeric_list_2d(clip_payload.get("image_features"))
    text_rows = _numeric_list_2d(clip_payload.get("text_sequence_features") or clip_payload.get("text_features"))
    wav_rows = _numeric_list_2d(
        wav_payload.get("wav2clip_features") or wav_payload.get("audio_features") or wav_payload.get("features")
    )

    visual_score = min(len(image_rows) / 15.0, 1.0) * 0.65 + _sequence_activity(image_rows) * 0.35
    audio_score = min(len(wav_rows) / 15.0, 1.0) * 0.65 + _sequence_activity(wav_rows) * 0.35
    text_score = min(len(words) / 80.0, 1.0) * 0.55 + min(len(sentences) / 8.0, 1.0) * 0.25 + _sequence_activity(text_rows) * 0.20
    bg_score = 1.0 if bg_payload.get("success") and bg_payload.get("bg_features") else 0.0

    modality_scores = {
        "visual": round(max(0.0, min(1.0, visual_score)), 3),
        "audio": round(max(0.0, min(1.0, audio_score)), 3),
        "text": round(max(0.0, min(1.0, text_score)), 3),
        "background": round(bg_score, 3),
    }
    available_scores = [value for key, value in modality_scores.items() if key != "background" or value > 0]
    overall = mean(available_scores) if available_scores else 0.0
    if errors:
        overall = max(0.0, overall - min(len(errors) * 0.05, 0.2))

    return {
        "schema_version": "modality-quality-v1",
        "overall_quality": round(overall, 3),
        "label": _score_label(overall),
        "modalities": modality_scores,
        "signals": {
            "frame_count": len(image_rows),
            "audio_segment_count": len(wav_rows),
            "transcript_word_count": len(words),
            "transcript_sentence_count": len(sentences),
            "has_bg_features": bool(bg_score),
            "error_count": len(errors),
        },
    }


def build_prediction_confidence_summary(
    *,
    scores: dict[str, float] | None,
    quality_summary: dict[str, Any] | None,
    is_real_result: bool,
    used_fallback: bool = False,
) -> dict[str, Any]:
    if not scores:
        return {
            "overall_confidence": 0.0,
            "label": "较低",
            "trait_confidence": {},
            "notes": ["暂无大五人格分数，无法计算预测置信度。"],
        }

    quality = float((quality_summary or {}).get("overall_quality", 0.0))
    base = quality * (0.9 if is_real_result else 0.35)
    if used_fallback:
        base *= 0.35

    trait_confidence = {}
    for trait, value in scores.items():
        extremity = abs(float(value) - 0.5) * 2
        confidence = max(0.2, min(1.0, base * 0.78 + extremity * 0.12 + 0.08))
        trait_confidence[trait] = {
            "confidence": round(confidence, 3),
            "label": _score_label(confidence),
            "trait_label": BIG_FIVE_LABELS.get(trait, trait),
        }

    overall = mean([item["confidence"] for item in trait_confidence.values()]) if trait_confidence else 0.0
    return {
        "schema_version": "big-five-confidence-v1",
        "overall_confidence": round(overall, 3),
        "label": _score_label(overall),
        "trait_confidence": trait_confidence,
        "notes": [
            "置信度由模态质量、真实模型状态和分数稳定性共同估计。",
            "该指标用于提示解释边界，不代表临床诊断可靠性。",
        ],
    }


def build_atmr_summary_for_session(db: Session, session_id: int | None) -> dict[str, Any]:
    if not session_id:
        return {}
    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()
    if not records:
        return {}

    exam_nos = [record.exam_no for record in records]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {question.exam_no: question for question in questions}

    module_scores: dict[str, list[float]] = {module: [] for module in MODULE_DIM_MAP}
    for record in records:
        question = question_map.get(record.exam_no)
        if not question:
            continue
        for module, dimension_id in MODULE_DIM_MAP.items():
            if question.dimension_id == dimension_id:
                module_scores[module].append(float(record.score or 0))
                break

    return {
        module: {
            "name": MODULE_DISPLAY_NAMES[module],
            "avg_score": round(mean(scores), 3) if scores else 0.0,
            "normalized": round((mean(scores) - 1.0) / 4.0, 3) if scores else 0.0,
            "question_count": len(scores),
        }
        for module, scores in module_scores.items()
    }


def build_consistency_summary(
    *,
    big_five_scores: dict[str, float] | None,
    atmr_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if not big_five_scores or not atmr_summary:
        return {
            "schema_version": "atmr-big-five-consistency-v1",
            "overall_status": "中性不足",
            "overall_score": 0.0,
            "items": [],
            "notes": ["缺少 ATMR 来源测评或大五人格分数，无法形成互证分析。"],
        }

    pairs = [
        ("A", "openness", 0.55, "欣赏型与开放性共同反映对新体验和可能性的接纳。"),
        ("A", "agreeableness", 0.45, "欣赏型与宜人性共同反映对他人价值和合作氛围的敏感度。"),
        ("T", "conscientiousness", 0.55, "目标型与尽责性共同反映计划、推进和目标执行倾向。"),
        ("T", "extraversion", 0.35, "目标型与外向性可共同反映外部表达和主动推进方式。"),
        ("M", "agreeableness", 0.60, "包容型与宜人性共同反映关系协商、理解和合作倾向。"),
        ("M", "neuroticism", -0.35, "包容型较高且神经质较低时，通常提示情绪承载更稳定。"),
        ("R", "conscientiousness", 0.70, "责任型与尽责性共同反映承诺、秩序和稳定履责倾向。"),
    ]

    items = []
    weighted_scores = []
    for module, trait, weight, rationale in pairs:
        atmr_value = float((atmr_summary.get(module) or {}).get("normalized", 0.0))
        trait_value = float(big_five_scores.get(trait, 0.5))
        if weight < 0:
            trait_value = 1.0 - trait_value
        distance = abs(atmr_value - trait_value)
        consistency = max(0.0, 1.0 - distance)
        status = "互相支持" if consistency >= 0.72 else "存在张力" if consistency < 0.48 else "中性不足"
        weighted_scores.append(consistency * abs(weight))
        items.append(
            {
                "atmr_module": module,
                "atmr_label": MODULE_DISPLAY_NAMES.get(module, module),
                "big_five_trait": trait,
                "big_five_label": BIG_FIVE_LABELS.get(trait, trait),
                "consistency": round(consistency, 3),
                "status": status,
                "rationale": rationale,
            }
        )

    overall = sum(weighted_scores) / sum(abs(pair[2]) for pair in pairs)
    return {
        "schema_version": "atmr-big-five-consistency-v1",
        "overall_status": "互相支持" if overall >= 0.72 else "存在张力" if overall < 0.48 else "中性不足",
        "overall_score": round(overall, 3),
        "items": items,
        "notes": [
            "一致性分析只说明两条证据链是否相互支持，不表示 ATMR 与 Big Five 可以直接等价换算。",
            "当出现张力时，应优先回看作答可信度、视频质量和具体场景。"
        ],
    }
