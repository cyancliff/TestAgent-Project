def _build_follow_up(reasons: list[str]) -> str:
    if any("过快" in reason for reason in reasons):
        return "你这题答得很快，能稍微具体说说你为什么这样选吗？"
    if any("过慢" in reason for reason in reasons):
        return "你这题思考了比较久，方便说说你当时主要在犹豫什么吗？"
    if any("选项重复" in reason for reason in reasons):
        return "你最近几题的选择模式比较一致，能说说你是如何判断这些题目的吗？"
    return "能稍微具体说说你作出这个选择的原因吗？"


async def check_anomaly_and_generate_question(
    time_spent: float,
    avg_time: float,
    question_content: str,
    selected_option: str,
    recent_answers: list[dict] | None = None,
    available_options: list[str] | None = None,
) -> dict:
    recent_answers = recent_answers or []
    reasons = []
    risk_score = 0

    normalized_avg = max(float(avg_time or 8.0), 3.0)
    normalized_time = max(float(time_spent or 0.0), 0.0)

    if available_options is not None and selected_option not in available_options:
        raise ValueError("所选答案不在题目选项中")

    if normalized_time < normalized_avg * 0.20:
        reasons.append("作答时间明显过快")
        risk_score += 70
    elif normalized_time < normalized_avg * 0.35:
        reasons.append("作答时间偏快")
        risk_score += 45

    if normalized_time > max(normalized_avg * 3, 60):
        reasons.append("作答时间异常偏长")
        risk_score += 20

    if recent_answers:
        recent_times = [max(float(item.get("time_spent", 0.0) or 0.0), 0.0) for item in recent_answers]
        recent_options = [item.get("selected_option") for item in recent_answers if item.get("selected_option")]

        fast_recent_count = sum(1 for spent in recent_times[-4:] if spent < normalized_avg * 0.35)
        if fast_recent_count >= 3:
            reasons.append("最近多题连续快速作答")
            risk_score += 30

        repeated_option_count = recent_options[-3:].count(selected_option)
        if repeated_option_count >= 3:
            reasons.append("最近多题重复选择同一选项")
            risk_score += 25

    risk_score = min(risk_score, 100)
    status = "anomaly" if risk_score >= 45 else "normal"

    return {
        "status": status,
        "follow_up": _build_follow_up(reasons) if status == "anomaly" else None,
        "risk_score": risk_score,
        "reasons": reasons,
    }
