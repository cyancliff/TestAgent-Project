async def check_anomaly_and_generate_question(
        time_spent: float,
        avg_time: float,
        question_content: str,
        selected_option: str
) -> dict:
    # 规则 1：乱猜异常 (耗时低于平均值的 30%)
    is_guessing = time_spent < (avg_time * 0.25)

    if not is_guessing:
        return {"status": "normal", "follow_up": None}

    # 判定为异常，返回统一的默认追问文本
    return {"status": "anomaly", "follow_up": "你答得好快呀，能稍微详细说说你选这个的原因吗？"}