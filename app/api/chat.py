# app/api/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.models.question import SessionLocal, AssessmentSession, AnswerRecord
import os
import httpx

router = APIRouter()

# Kimi API 配置
KIMI_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
KIMI_BASE_URL = "https://api.deepseek.com/v1"
KIMI_MODEL = "deepseek-chat"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: int
    user_id: int
    message: str


class ChatResponse(BaseModel):
    reply: str
    messages: List[ChatMessage]


# 存储对话历史（简化版，用内存存储，生产环境应使用数据库）
chat_histories = {}


def get_session_context(session_id: int, db: Session) -> str:
    """获取测评报告和答题记录作为上下文"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        return ""

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()

    context = f"""【用户心理测评报告】
{session.report_content or "暂无报告"}

【答题记录】
"""
    for r in records:
        context += f"- {r.exam_no}: 选择'{r.selected_option}', 得分{r.score}, 耗时{r.time_spent}s"
        if r.is_anomaly:
            context += f" [异常: {r.ai_follow_up}]"
        context += "\n"

    return context


@router.post("/start")
async def start_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """初始化对话，挂载测评上下文"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == payload.session_id,
        AssessmentSession.user_id == payload.user_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 构建系统提示词
    context = get_session_context(payload.session_id, db)
    system_prompt = f"""你是一位专业的心理咨询师和心理分析专家。你已经完成了对以下用户的心理测评分析，现在需要基于测评结果与用户进行深入的对话交流。

{context}

你的职责：
1. 根据测评结果，解答用户关于自己心理状态的疑问
2. 提供个性化的心理改善建议
3. 以专业、温暖、支持性的态度与用户交流
4. 如果用户的问题超出测评范围，可以基于心理学常识回答，但要说明这是通用建议

请用中文回复，语气要专业且富有同理心。"""

    # 初始化对话历史
    chat_histories[payload.session_id] = [
        {"role": "system", "content": system_prompt}
    ]

    # 生成欢迎语
    welcome_msg = "你好！我是你的AI心理顾问。我已经详细了解了你的测评结果，很高兴能和你交流。你可以问我关于测评结果的任何问题，或者聊聊你当前的心理状态。"

    chat_histories[payload.session_id].append({
        "role": "assistant",
        "content": welcome_msg
    })

    return {
        "welcome": welcome_msg,
        "messages": chat_histories[payload.session_id][1:]  # 不返回system消息
    }


@router.post("/send")
async def send_message(payload: ChatRequest, db: Session = Depends(get_db)):
    """发送消息并获取回复"""
    if payload.session_id not in chat_histories:
        raise HTTPException(status_code=400, detail="对话未初始化，请先调用/start")

    # 添加用户消息
    chat_histories[payload.session_id].append({
        "role": "user",
        "content": payload.message
    })

    # 调用 Kimi API 生成回复
    reply = await generate_reply(chat_histories[payload.session_id])

    # 添加助手回复
    chat_histories[payload.session_id].append({
        "role": "assistant",
        "content": reply
    })

    return {
        "reply": reply,
        "messages": [m for m in chat_histories[payload.session_id] if m["role"] != "system"]
    }


async def generate_reply(messages: List[dict]) -> str:
    """调用 Kimi K2.5 API 生成回复"""
    print(f"[DEBUG] KIMI_API_KEY 是否存在: {bool(KIMI_API_KEY)}")
    print(f"[DEBUG] KIMI_API_KEY 前10位: {KIMI_API_KEY[:10] if KIMI_API_KEY else '空'}")

    if not KIMI_API_KEY:
        print("[DEBUG] 未配置 API Key，使用备用回复")
        return "【错误】未配置 KIMI_API_KEY 环境变量"

    try:
        print(f"[DEBUG] 开始调用 Kimi API，消息数: {len(messages)}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{KIMI_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {KIMI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": KIMI_MODEL,
                    "messages": messages,
                    "temperature": 1,
                    "max_tokens": 2000
                }
            )
            print(f"[DEBUG] Kimi API 响应状态: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            print(f"[DEBUG] Kimi 回复长度: {len(reply)}")
            return reply
    except httpx.HTTPStatusError as e:
        error_msg = f"Kimi API 错误: {e.response.status_code} - {e.response.text}"
        print(f"[DEBUG] {error_msg}")
        return f"【API错误】{error_msg}"
    except Exception as e:
        error_msg = f"调用 Kimi API 失败: {str(e)}"
        print(f"[DEBUG] {error_msg}")
        return f"【异常】{error_msg}"


@router.get("/history/{session_id}")
async def get_chat_history(session_id: int, user_id: int, db: Session = Depends(get_db)):
    """获取对话历史"""
    if session_id not in chat_histories:
        return {"messages": []}

    return {
        "messages": [m for m in chat_histories[session_id] if m["role"] != "system"]
    }


@router.post("/clear")
async def clear_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """清空对话历史"""
    if payload.session_id in chat_histories:
        del chat_histories[payload.session_id]

    return {"status": "success", "message": "对话历史已清空"}
