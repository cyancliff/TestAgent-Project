from app.services.assessment_trust import calculate_answer_confidence


def _build_follow_up(reasons: list[str]) -> str:
    """Legacy helper kept for compatibility with older tests and clients."""
    if any("过快" in reason for reason in reasons):
        return "你这题答得很快，能稍微具体说说你为什么这样选吗？"
    if any("连续" in reason for reason in reasons):
        return "你最近多题选择比较一致，能说说这些选择背后的共同原因吗？"
    if any("极端" in reason for reason in reasons):
        return "你最近的选择比较集中在强烈选项上，能补充一下判断依据吗？"
    return "能稍微具体说说你作出这个选择的原因吗？"


def _option_index(selected_option: str, available_options: list[str] | None) -> int | None:
    if not available_options:
        return None
    try:
        return available_options.index(selected_option)
    except ValueError:
        return None


def _is_extreme_option(selected_option: str, available_options: list[str] | None) -> bool:
    index = _option_index(selected_option, available_options)
    if index is None or not available_options:
        return selected_option.strip().upper().startswith(("A", "E"))
    return index in {0, len(available_options) - 1}


def _metric_float(metrics: dict | None, key: str, default: float = 0.0) -> float:
    try:
        return float((metrics or {}).get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _metric_int(metrics: dict | None, key: str, default: int = 0) -> int:
    try:
        return int((metrics or {}).get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _metric_bool(metrics: dict | None, key: str) -> bool:
    value = (metrics or {}).get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _sanitize_behavior_metrics(behavior_metrics: dict | None) -> dict:
    """Keep only compact per-answer behavior features."""

    if not behavior_metrics:
        return {}

    metrics = behavior_metrics or {}
    option_path = metrics.get("option_change_path") or []
    if not isinstance(option_path, list):
        option_path = []

    return {
        "first_action_latency": round(_metric_float(metrics, "first_action_latency"), 3),
        "mouse_move_count": max(_metric_int(metrics, "mouse_move_count"), 0),
        "mouse_path_length": round(max(_metric_float(metrics, "mouse_path_length"), 0.0), 2),
        "pointer_down_count": max(_metric_int(metrics, "pointer_down_count"), 0),
        "option_change_count": max(_metric_int(metrics, "option_change_count"), 0),
        "option_change_path": [str(item)[:80] for item in option_path[-8:]],
        "focus_blur_count": max(_metric_int(metrics, "focus_blur_count"), 0),
        "idle_time": round(max(_metric_float(metrics, "idle_time"), 0.0), 3),
        "rapid_click_flag": _metric_bool(metrics, "rapid_click_flag"),
    }


def _apply_behavior_rules(
    *,
    behavior_metrics: dict,
    normalized_avg: float,
    normalized_time: float,
) -> tuple[int, list[str]]:
    risk_score = 0
    reasons: list[str] = []
    if not behavior_metrics:
        return risk_score, reasons

    first_action_latency = _metric_float(behavior_metrics, "first_action_latency")
    mouse_move_count = _metric_int(behavior_metrics, "mouse_move_count")
    mouse_path_length = _metric_float(behavior_metrics, "mouse_path_length")
    option_change_count = _metric_int(behavior_metrics, "option_change_count")
    focus_blur_count = _metric_int(behavior_metrics, "focus_blur_count")
    idle_time = _metric_float(behavior_metrics, "idle_time")

    if 0 < first_action_latency < min(max(normalized_avg * 0.08, 0.25), 0.8):
        reasons.append("首次交互过快")
        risk_score += 30

    if normalized_time < normalized_avg * 0.35 and mouse_move_count <= 1 and mouse_path_length < 24:
        reasons.append("作答过程几乎无前台交互")
        risk_score += 20

    if option_change_count >= 4:
        reasons.append("选项反复更改")
        risk_score += 25
    elif option_change_count >= 2:
        reasons.append("选项多次更改")
        risk_score += 12

    if focus_blur_count >= 3:
        reasons.append("作答期间频繁切出页面")
        risk_score += 25
    elif focus_blur_count >= 1:
        reasons.append("作答期间切出页面")
        risk_score += 10

    if idle_time >= max(normalized_avg * 2.5, 20.0):
        reasons.append("作答期间长时间无操作")
        risk_score += 10

    if _metric_bool(behavior_metrics, "rapid_click_flag"):
        reasons.append("短时间连续点击")
        risk_score += 15

    return risk_score, reasons


async def check_anomaly_and_generate_question(
    time_spent: float,
    avg_time: float,
    question_content: str,
    selected_option: str,
    recent_answers: list[dict] | None = None,
    available_options: list[str] | None = None,
    behavior_metrics: dict | None = None,
) -> dict:
    """
    Detect anomalous answers.

    The strategy combines response speed, foreground behavior features,
    short-range consistency, extreme-option concentration, and recent anomaly
    density into one background risk score.
    """
    del question_content  # kept for API compatibility

    reasons: list[str] = []
    risk_score = 0
    recent_answers = recent_answers or []
    behavior_metrics = _sanitize_behavior_metrics(behavior_metrics)

    normalized_avg = max(float(avg_time or 8.0), 3.0)
    normalized_time = max(float(time_spent or 0.0), 0.0)

    if available_options is not None and selected_option not in available_options:
        raise ValueError("所选答案不在题目选项中")

    if normalized_time < normalized_avg * 0.10:
        reasons.append("作答时间明显过快")
        risk_score += 70

    behavior_risk, behavior_reasons = _apply_behavior_rules(
        behavior_metrics=behavior_metrics,
        normalized_avg=normalized_avg,
        normalized_time=normalized_time,
    )
    risk_score += behavior_risk
    reasons.extend(behavior_reasons)

    recent_options = [str(answer.get("selected_option", "")) for answer in recent_answers[-3:]]
    if len(recent_options) >= 3 and all(option == selected_option for option in recent_options):
        reasons.append("连续多题选择同一选项")
        risk_score += 35

    recent_extreme_flags = [
        _is_extreme_option(str(answer.get("selected_option", "")), available_options)
        for answer in recent_answers[-4:]
    ]
    if _is_extreme_option(selected_option, available_options) and len(recent_extreme_flags) >= 3:
        extreme_ratio = (sum(recent_extreme_flags) + 1) / (len(recent_extreme_flags) + 1)
        if extreme_ratio >= 0.8:
            reasons.append("近期极端选项比例过高")
            risk_score += 25

    recent_anomaly_count = sum(1 for answer in recent_answers[-5:] if int(answer.get("is_anomaly", 0) or 0) == 1)
    if recent_anomaly_count >= 2:
        reasons.append("近期异常作答密度较高")
        risk_score += 20

    risk_score = min(risk_score, 100)

    status = "anomaly" if risk_score >= 50 else "normal"
    answer_confidence = calculate_answer_confidence(
        risk_score=risk_score,
        is_anomaly=status == "anomaly",
        user_explanation=None,
    )

    return {
        "status": status,
        "follow_up": None,
        "risk_score": risk_score,
        "reasons": reasons,
        "answer_confidence": answer_confidence,
        "behavior_metrics": behavior_metrics,
    }
