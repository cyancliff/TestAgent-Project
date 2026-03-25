import httpx
from app.core.config import settings


async def check_anomaly_and_generate_question(
        time_spent: float,
        avg_time: float,
        question_content: str,
        selected_option: str
) -> dict:
    # 规则 1：乱猜异常 (耗时低于平均值的 30%)
    is_guessing = time_spent < (avg_time * 0.3)

    if not is_guessing:
        return {"status": "normal", "follow_up": None}

    # 判定为异常，组装 Prompt
    prompt = f"""
    你是一个温柔的心理测评辅助AI。受试者刚刚回答了以下问题：
    题目：“{question_content}”
    他的选择：“{selected_option}”

    【警告】：系统检测到他作答仅用了 {time_spent} 秒，存在“未充分思考/乱猜”的嫌疑。
    请生成一句简短、温柔的追问（不超过30字），引导他解释为什么选这个，绝对不要带有审问语气。
    """

    # 异步调用 DeepSeek (非阻塞)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 50
                },
                timeout=10.0
            )
            response.raise_for_status()
            result = response.json()
            follow_up_text = result["choices"][0]["message"]["content"].strip()
            return {"status": "anomaly", "follow_up": follow_up_text}
        except Exception as e:
            print(f"调用 DeepSeek 失败: {e}")
            return {"status": "anomaly", "follow_up": "你答得好快呀，能稍微详细说说你选这个的原因吗？"}