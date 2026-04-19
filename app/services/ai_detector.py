def _build_follow_up(reasons: list[str]) -> str:
    """Build a follow-up question for anomaly answers."""
    if any("过快" in reason for reason in reasons):
        return "你这题答得很快，能稍微具体说说你为什么这样选吗？"
    return "能稍微具体说说你作出这个选择的原因吗？"


async def check_anomaly_and_generate_question(
    time_spent: float,
    avg_time: float,
    question_content: str,
    selected_option: str,
    recent_answers: list[dict] | None = None,
    available_options: list[str] | None = None,
) -> dict:
    """
    Detect anomalous answers.

    The current strategy intentionally keeps only one anomaly rule:
    flag answers that are obviously too fast compared with the baseline average.
    Other historical signals are ignored to reduce false positives.
    """
    del question_content, recent_answers  # kept for API compatibility

    reasons: list[str] = []
    risk_score = 0

    normalized_avg = max(float(avg_time or 8.0), 3.0)
    normalized_time = max(float(time_spent or 0.0), 0.0)

    if available_options is not None and selected_option not in available_options:
        raise ValueError("所选答案不在题目选项中")

    if normalized_time < normalized_avg * 0.10:
        reasons.append("作答时间明显过快")
        risk_score = 70

    status = "anomaly" if risk_score > 0 else "normal"

    return {
        "status": status,
        "follow_up": _build_follow_up(reasons) if status == "anomaly" else None,
        "risk_score": risk_score,
        "reasons": reasons,
    }
