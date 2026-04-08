# app/api/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.models.question import SessionLocal, AssessmentSession, AnswerRecord, User
from app.services.rag_service import retrieve_knowledge
from app.core.security import get_current_user
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
    message: str = ""


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
async def start_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """初始化对话，挂载测评上下文"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == payload.session_id,
        AssessmentSession.user_id == current_user.id
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
async def send_message(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """发送消息并获取回复，自动检索 ATMR 知识库增强回答"""
    if payload.session_id not in chat_histories:
        raise HTTPException(status_code=400, detail="对话未初始化，请先调用/start")

    # RAG 检索：根据用户问题从 ATMR 知识库中检索相关知识
    rag_context = ""
    try:
        rag_context = await retrieve_knowledge(payload.message, max_sections=3, max_chars=2000)
    except Exception as e:
        print(f"[Chat] RAG 检索失败（不影响回复）: {e}")

    # 如果检索到知识库内容，注入为一条临时 system 消息
    if rag_context:
        chat_histories[payload.session_id].append({
            "role": "system",
            "content": f"【ATMR 知识库参考资料】以下是与用户问题相关的 ATMR 心理学专业知识，"
                       f"请结合这些资料回答用户问题，并在适当时引用理论依据：\n\n{rag_context}"
        })

    # 添加用户消息
    chat_histories[payload.session_id].append({
        "role": "user",
        "content": payload.message
    })

    # 调用 LLM API 生成回复
    reply = await generate_reply(chat_histories[payload.session_id])

    # 清理临时注入的 RAG system 消息，避免对话历史膨胀
    chat_histories[payload.session_id] = [
        m for m in chat_histories[payload.session_id]
        if not (m["role"] == "system" and "ATMR 知识库参考资料" in m.get("content", ""))
    ]

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
    if not KIMI_API_KEY:
        return "【错误】未配置 KIMI_API_KEY 环境变量"

    try:
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
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        return f"【API错误】Kimi API 错误: {e.response.status_code}"
    except Exception as e:
        return f"【异常】调用 Kimi API 失败: {str(e)}"


@router.get("/history/{session_id}")
async def get_chat_history(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取对话历史"""
    # 验证 session 属于当前用户
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    if session_id not in chat_histories:
        return {"messages": []}

    return {
        "messages": [m for m in chat_histories[session_id] if m["role"] != "system"]
    }


@router.post("/clear")
async def clear_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """清空对话历史"""
    if payload.session_id in chat_histories:
        del chat_histories[payload.session_id]

    return {"status": "success", "message": "对话历史已清空"}
