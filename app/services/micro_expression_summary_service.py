"""Helpers for turning MOL micro-expression artifacts into UI/API summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


INTERPRETATION_BOUNDARY_ZH = "微表情只作为短时面部线索，不能直接代表稳定人格标签。"


def _empty_summary(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "dominant_expression": None,
        "dominant_label_zh": "暂无",
        "confidence": 0.0,
        "summary_text_zh": reason,
        "interpretation_boundary_zh": INTERPRETATION_BOUNDARY_ZH,
        "probabilities": {},
        "errors": [reason],
    }


def load_micro_expression_summary_from_artifacts(artifacts: dict | None) -> dict[str, Any] | None:
    """Load a compact display payload from ``micro_expression_feature.json`` if present."""
    path_value = (artifacts or {}).get("micro_expression_feature_path")
    if not path_value:
        return None

    try:
        payload = json.loads(Path(path_value).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return _empty_summary(f"微表情结果读取失败：{exc}")

    if not isinstance(payload, dict):
        return _empty_summary("微表情结果格式无效。")

    errors = [str(error) for error in (payload.get("errors") or [])]
    if not payload.get("success", False):
        reason = "；".join(errors[:2]) or "微表情模块未返回可用结果。"
        return _empty_summary(reason)

    summary = payload.get("summary") or {}
    confidence = summary.get("confidence")
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError):
        confidence_value = 0.0

    return {
        "available": True,
        "dominant_expression": summary.get("dominant_expression"),
        "dominant_label_zh": summary.get("dominant_label_zh") or "暂无",
        "confidence": confidence_value,
        "summary_text_zh": payload.get("summary_text_zh") or "暂无可用微表情摘要。",
        "interpretation_boundary_zh": payload.get("interpretation_boundary_zh") or INTERPRETATION_BOUNDARY_ZH,
        "probabilities": payload.get("probabilities") or {},
        "errors": errors,
    }
