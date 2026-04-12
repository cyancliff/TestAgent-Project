# app/api/chat.py

import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.question import (
    AnswerRecord,
    AssessmentSession,
    ChatSession,
    User,
)
from app.models.question import (
    ChatMessage as ChatMessageModel,
)
from app.services.rag_service import retrieve_knowledge

router = APIRouter()

# LLM API 配置
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = "https://api.deepseek.com/v1"
LLM_MODEL = "deepseek-chat"


# --- Schema ---
class ChatMessageSchema(BaseModel):
    role: str
    content: str
    timestamp: str | None = None


class CreateChatSessionRequest(BaseModel):
    assessment_session_id: int | None = None
    title: str | None = None


class UpdateChatSessionRequest(BaseModel):
    assessment_session_id: int | None = None
    title: str | None = None


class ChatSendRequest(BaseModel):
    message: str


# --- 辅助函数 ---
def serialize_messages(messages: list[ChatMessageModel], include_system: bool = False) -> list[dict]:
    result = []
    for msg in messages:
        if not include_system and msg.role == "system":
            continue
        result.append(
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            }
        )
    return result


def get_chat_messages(db: Session, chat_session_id: int, include_system: bool = True) -> list[ChatMessageModel]:
    query = (
        db.query(ChatMessageModel)
        .filter(ChatMessageModel.chat_session_id == chat_session_id)
        .order_by(ChatMessageModel.id.asc())
    )
    if not include_system:
        query = query.filter(ChatMessageModel.role != "system")
    return query.all()


def append_chat_message(db: Session, chat_session_id: int, user_id: int, role: str, content: str) -> ChatMessageModel:
    message = ChatMessageModel(
        chat_session_id=chat_session_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_assessment_context(assessment_session_id: int, db: Session) -> str:
    """获取测评报告和答题记录作为上下文"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == assessment_session_id).first()
    if not session:
        return ""

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == assessment_session_id).all()

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


def build_system_prompt(assessment_context: str = "") -> str:
    """构建系统提示词"""
    if assessment_context:
        return f"""你是一位专业的心理咨询师和心理分析专家。你已经完成了对以下用户的心理测评分析，现在需要基于测评结果与用户进行深入的对话交流。

{assessment_context}

你的职责：
1. 根据测评结果，解答用户关于自己心理状态的疑问
2. 提供个性化的心理改善建议
3. 以专业、温暖、支持性的态度与用户交流
4. 如果用户的问题超出测评范围，可以基于心理学常识回答，但要说明这是通用建议

请用中文回复，语气要专业且富有同理心。"""
    else:
        return """你是一位专业的心理咨询师和心理分析专家。用户当前没有关联具体的测评结果，请基于心理学专业知识为用户提供通用的心理咨询服务。

你的职责：
1. 以专业、温暖、支持性的态度与用户交流
2. 基于心理学常识回答用户的问题
3. 提供实用的心理改善建议
4. 如果需要更个性化的分析，建议用户关联一份测评结果

请用中文回复，语气要专业且富有同理心。"""


def ensure_chat_session_owner(db: Session, chat_session_id: int, user_id: int) -> ChatSession:
    """校验咨询会话属于当前用户"""
    chat_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == chat_session_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="咨询会话不存在")
    return chat_session


def init_chat_with_context(db: Session, chat_session: ChatSession, user_id: int):
    """为咨询会话初始化系统提示和欢迎消息"""
    # 清除旧的系统消息
    db.query(ChatMessageModel).filter(
        ChatMessageModel.chat_session_id == chat_session.id,
        ChatMessageModel.role == "system",
    ).delete()
    db.commit()

    # 构建上下文
    assessment_context = ""
    if chat_session.assessment_session_id:
        assessment_context = get_assessment_context(chat_session.assessment_session_id, db)

    system_prompt = build_system_prompt(assessment_context)
    append_chat_message(db, chat_session.id, user_id, "system", system_prompt)

    # 如果没有任何可见消息，添加欢迎消息
    visible = get_chat_messages(db, chat_session.id, include_system=False)
    if not visible:
        if chat_session.assessment_session_id:
            welcome = "你好！我是你的AI心理顾问。我已经详细了解了你的测评结果，很高兴能和你交流。你可以问我关于测评结果的任何问题，或者聊聊你当前的心理状态。"
        else:
            welcome = "你好！我是你的AI心理顾问。目前没有关联测评结果，我可以基于心理学专业知识为你提供通用的心理咨询。你也可以在上方选择关联一份测评结果，获得更个性化的分析。"
        append_chat_message(db, chat_session.id, user_id, "assistant", welcome)


async def generate_reply(messages: list[dict]) -> str:
    """调用 LLM API 生成回复"""
    if not LLM_API_KEY:
        return "【错误】未配置 API 密钥"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": LLM_MODEL, "messages": messages, "temperature": 1, "max_tokens": 2000},
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        return f"【API错误】API 错误: {e.response.status_code}"
    except Exception as e:
        return f"【异常】调用 API 失败: {str(e)}"


# ==================== 接口 ====================


@router.get("/sessions")
async def list_chat_sessions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取用户所有咨询会话"""
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    result = []
    for s in sessions:
        # 获取最后一条可见消息作为预览
        last_msg = (
            db.query(ChatMessageModel)
            .filter(
                ChatMessageModel.chat_session_id == s.id,
                ChatMessageModel.role != "system",
            )
            .order_by(ChatMessageModel.id.desc())
            .first()
        )

        msg_count = (
            db.query(ChatMessageModel)
            .filter(
                ChatMessageModel.chat_session_id == s.id,
                ChatMessageModel.role != "system",
            )
            .count()
        )

        # 获取关联测评的简要信息
        assessment_info = None
        if s.assessment_session_id and s.assessment_session:
            assessment_info = {
                "session_id": s.assessment_session_id,
                "started_at": s.assessment_session.started_at.isoformat() if s.assessment_session.started_at else None,
                "has_report": s.assessment_session.report_content is not None,
            }

        result.append(
            {
                "id": s.id,
                "title": s.title,
                "assessment_session_id": s.assessment_session_id,
                "assessment_info": assessment_info,
                "message_count": msg_count,
                "last_message": last_msg.content[:50] if last_msg else None,
                "last_message_role": last_msg.role if last_msg else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
        )

    return {"sessions": result}


@router.post("/sessions")
async def create_chat_session(
    payload: CreateChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建新咨询会话"""
    # 如果指定了关联测评，校验归属
    if payload.assessment_session_id:
        assessment = (
            db.query(AssessmentSession)
            .filter(
                AssessmentSession.id == payload.assessment_session_id,
                AssessmentSession.user_id == current_user.id,
            )
            .first()
        )
        if not assessment:
            raise HTTPException(status_code=404, detail="测评会话不存在")

    title = payload.title or "新对话"
    if not payload.title and payload.assessment_session_id:
        title = f"测评 #{payload.assessment_session_id} 咨询"

    chat_session = ChatSession(
        user_id=current_user.id,
        assessment_session_id=payload.assessment_session_id,
        title=title,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    # 初始化系统提示和欢迎消息
    init_chat_with_context(db, chat_session, current_user.id)

    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "assessment_session_id": chat_session.assessment_session_id,
    }


@router.put("/sessions/{chat_session_id}")
async def update_chat_session(
    chat_session_id: int,
    payload: UpdateChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改咨询会话（切换关联测评、修改标题）"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)

    # 检查关联测评是否变化
    assessment_changed = False
    if payload.assessment_session_id is not None:
        if payload.assessment_session_id != chat_session.assessment_session_id:
            # 校验新测评归属
            if payload.assessment_session_id > 0:
                assessment = (
                    db.query(AssessmentSession)
                    .filter(
                        AssessmentSession.id == payload.assessment_session_id,
                        AssessmentSession.user_id == current_user.id,
                    )
                    .first()
                )
                if not assessment:
                    raise HTTPException(status_code=404, detail="测评会话不存在")
                chat_session.assessment_session_id = payload.assessment_session_id
            else:
                # 传 0 或负数表示取消关联
                chat_session.assessment_session_id = None
            assessment_changed = True

    if payload.title is not None:
        chat_session.title = payload.title

    db.commit()

    # 关联测评变化时，重新初始化系统上下文
    if assessment_changed:
        init_chat_with_context(db, chat_session, current_user.id)

    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "assessment_session_id": chat_session.assessment_session_id,
    }


@router.delete("/sessions/{chat_session_id}")
async def delete_chat_session(
    chat_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除咨询会话（含所有消息）"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)
    db.delete(chat_session)  # cascade 自动删除消息
    db.commit()
    return {"status": "success"}


@router.get("/sessions/{chat_session_id}/messages")
async def get_messages(
    chat_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取咨询会话的消息历史"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)

    # 如果没有任何消息，初始化
    all_msgs = get_chat_messages(db, chat_session_id, include_system=True)
    if not all_msgs:
        init_chat_with_context(db, chat_session, current_user.id)

    return {
        "messages": serialize_messages(get_chat_messages(db, chat_session_id, include_system=False)),
        "assessment_session_id": chat_session.assessment_session_id,
        "title": chat_session.title,
    }


@router.post("/sessions/{chat_session_id}/send")
async def send_message(
    chat_session_id: int,
    payload: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息并获取回复"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)

    # 确保已初始化
    all_msgs = get_chat_messages(db, chat_session_id, include_system=True)
    if not all_msgs:
        init_chat_with_context(db, chat_session, current_user.id)

    # RAG 检索增强
    rag_context = ""
    try:
        rag_context = await retrieve_knowledge(payload.message, max_sections=3, max_chars=2000)
    except Exception as e:
        print(f"[Chat] RAG 检索失败: {e}")

    # 保存用户消息
    append_chat_message(db, chat_session_id, current_user.id, "user", payload.message)

    # 更新会话时间和标题
    from datetime import datetime

    chat_session.updated_at = datetime.now()
    # 如果标题还是默认的，用第一条用户消息更新
    if chat_session.title in ("新对话", f"测评 #{chat_session.assessment_session_id} 咨询"):
        chat_session.title = payload.message[:20] + ("..." if len(payload.message) > 20 else "")
    db.commit()

    # 构建 LLM 消息
    persisted = serialize_messages(get_chat_messages(db, chat_session_id, include_system=True), include_system=True)
    llm_messages = list(persisted)
    if rag_context:
        llm_messages.append(
            {
                "role": "system",
                "content": f"【ATMR 知识库参考资料】以下是与用户问题相关的 ATMR 心理学专业知识，请结合这些资料回答用户问题，并在适当时引用理论依据：\n\n{rag_context}",
            }
        )

    reply = await generate_reply(llm_messages)
    append_chat_message(db, chat_session_id, current_user.id, "assistant", reply)

    return {
        "reply": reply,
        "messages": serialize_messages(get_chat_messages(db, chat_session_id, include_system=False)),
    }


@router.post("/sessions/{chat_session_id}/clear")
async def clear_chat(
    chat_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空咨询会话的消息"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)

    db.query(ChatMessageModel).filter(
        ChatMessageModel.chat_session_id == chat_session_id,
    ).delete()
    db.commit()

    # 重新初始化
    init_chat_with_context(db, chat_session, current_user.id)

    return {
        "status": "success",
        "messages": serialize_messages(get_chat_messages(db, chat_session_id, include_system=False)),
    }


# --- 获取可关联的测评列表 ---
@router.get("/available-assessments")
async def get_available_assessments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取用户所有已完成的测评会话，用于关联选择"""
    sessions = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == current_user.id,
            AssessmentSession.status == "completed",
        )
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )

    return {
        "assessments": [
            {
                "session_id": s.id,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "finished_at": s.finished_at.isoformat() if s.finished_at else None,
                "has_report": s.report_content is not None,
            }
            for s in sessions
        ]
    }
