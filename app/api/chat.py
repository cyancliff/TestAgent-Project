# app/api/chat.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.models.question import SessionLocal, AssessmentSession, AnswerRecord, ChatMessage as ChatMessageModel, User
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


def serialize_messages(messages: List[ChatMessageModel], include_system: bool = False) -> List[dict]:
    result = []
    for msg in messages:
        if not include_system and msg.role == "system":
            continue
        result.append({
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
        })
    return result


def get_chat_messages(db: Session, session_id: int, include_system: bool = True) -> List[ChatMessageModel]:
    query = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).order_by(ChatMessageModel.id.asc())
    if not include_system:
        query = query.filter(ChatMessageModel.role != "system")
    return query.all()


def append_chat_message(db: Session, session_id: int, user_id: int, role: str, content: str) -> ChatMessageModel:
    message = ChatMessageModel(
        session_id=session_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


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

    existing_messages = get_chat_messages(db, payload.session_id, include_system=True)
    if existing_messages:
        visible_messages = serialize_messages(existing_messages, include_system=False)
        welcome_msg = next((msg["content"] for msg in visible_messages if msg["role"] == "assistant"), "")
        return {
            "welcome": welcome_msg,
            "messages": visible_messages,
        }

    context = get_session_context(payload.session_id, db)
    system_prompt = f"""你是一位专业的心理咨询师和心理分析专家。你已经完成了对以下用户的心理测评分析，现在需要基于测评结果与用户进行深入的对话交流。

{context}

你的职责：
1. 根据测评结果，解答用户关于自己心理状态的疑问
2. 提供个性化的心理改善建议
3. 以专业、温暖、支持性的态度与用户交流
4. 如果用户的问题超出测评范围，可以基于心理学常识回答，但要说明这是通用建议

请用中文回复，语气要专业且富有同理心。"""

    welcome_msg = "你好！我是你的AI心理顾问。我已经详细了解了你的测评结果，很高兴能和你交流。你可以问我关于测评结果的任何问题，或者聊聊你当前的心理状态。"

    append_chat_message(db, payload.session_id, current_user.id, "system", system_prompt)
    append_chat_message(db, payload.session_id, current_user.id, "assistant", welcome_msg)

    return {
        "welcome": welcome_msg,
        "messages": serialize_messages(get_chat_messages(db, payload.session_id, include_system=False)),
    }


@router.post("/send")
async def send_message(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """发送消息并获取回复，自动检索 ATMR 知识库增强回答"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == payload.session_id,
        AssessmentSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    existing_messages = get_chat_messages(db, payload.session_id, include_system=True)
    if not existing_messages:
        raise HTTPException(status_code=400, detail="对话未初始化，请先调用/start")

    rag_context = ""
    try:
        rag_context = await retrieve_knowledge(payload.message, max_sections=3, max_chars=2000)
    except Exception as e:
        print(f"[Chat] RAG 检索失败（不影响回复）: {e}")

    append_chat_message(db, payload.session_id, current_user.id, "user", payload.message)
    persisted_messages = serialize_messages(get_chat_messages(db, payload.session_id, include_system=True), include_system=True)

    llm_messages = list(persisted_messages)
    if rag_context:
        llm_messages.append({
            "role": "system",
            "content": f"【ATMR 知识库参考资料】以下是与用户问题相关的 ATMR 心理学专业知识，请结合这些资料回答用户问题，并在适当时引用理论依据：\n\n{rag_context}"
        })

    reply = await generate_reply(llm_messages)
    append_chat_message(db, payload.session_id, current_user.id, "assistant", reply)

    return {
        "reply": reply,
        "messages": serialize_messages(get_chat_messages(db, payload.session_id, include_system=False))
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
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    return {
        "messages": serialize_messages(get_chat_messages(db, session_id, include_system=False))
    }


@router.post("/clear")
async def clear_chat(payload: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """清空对话历史"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == payload.session_id,
        AssessmentSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    db.query(ChatMessageModel).filter(
        ChatMessageModel.session_id == payload.session_id,
        ChatMessageModel.user_id == current_user.id,
    ).delete()
    db.commit()

    return {"status": "success", "message": "对话历史已清空"}
