# app/api/chat.py

import json
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import (
    build_deepseek_thinking_payload,
    get_deepseek_api_key,
    get_deepseek_chat_completions_url,
    get_deepseek_chat_model,
    get_deepseek_chat_thinking_mode,
)
from app.core.constants import MODULE_DIM_MAP, MODULE_DISPLAY_NAMES
from app.core.database import SessionLocal, get_db
from app.core.security import get_current_user
from app.models.assessment import AnswerRecord, AssessmentSession, Question
from app.models.chat import ChatSession, ChatMessage as ChatMessageModel
from app.models.multimodal import BigFivePersonalityReport
from app.models.user import User
from app.services.scoring import calculate_weight_bonus, clamp_score
from app.services.rag_service import retrieve_big_five_knowledge, retrieve_knowledge

router = APIRouter()

# LLM API 配置

BIG_FIVE_DIMENSIONS = [
    ("openness", "开放性"),
    ("conscientiousness", "尽责性"),
    ("extraversion", "外向性"),
    ("agreeableness", "宜人性"),
    ("neuroticism", "神经质"),
]


# --- Schema ---
class ChatMessageSchema(BaseModel):
    role: str
    content: str
    timestamp: str | None = None


class CreateChatSessionRequest(BaseModel):
    assessment_session_id: int | None = None
    big_five_report_id: int | None = None
    title: str | None = None


class UpdateChatSessionRequest(BaseModel):
    assessment_session_id: int | None = None
    big_five_report_id: int | None = None
    reset_history: bool = False
    title: str | None = None


class ChatSendRequest(BaseModel):
    message: str


# --- 辅助函数 ---
def build_assessment_title(assessment_session: AssessmentSession | None) -> str:
    if assessment_session is None:
        return "未命名测评"

    title = (assessment_session.title or "").strip()
    if title:
        return title

    if assessment_session.started_at is not None:
        try:
            return assessment_session.started_at.astimezone().strftime("%Y.%m.%d %H:%M")
        except Exception:
            return assessment_session.started_at.strftime("%Y.%m.%d %H:%M")

    if assessment_session.id is not None:
        return f"测评 #{assessment_session.id}"
    return "未命名测评"


def build_big_five_report_title(report: BigFivePersonalityReport | None) -> str:
    if report is None:
        return "未命名大五报告"

    title = (report.title or "").strip()
    if title:
        return title

    if report.original_filename:
        return f"{report.original_filename} 大五报告"

    if report.id is not None:
        return f"大五报告 #{report.id}"
    return "未命名大五报告"


def build_default_chat_title(
    assessment_session: AssessmentSession | None,
    big_five_report: BigFivePersonalityReport | None = None,
) -> str:
    if assessment_session is not None and big_five_report is not None:
        return f"{build_assessment_title(assessment_session)} + 大五报告咨询"
    if assessment_session is not None:
        return f"{build_assessment_title(assessment_session)} 咨询"
    if big_five_report is not None:
        return f"{build_big_five_report_title(big_five_report)} 咨询"
    return "新对话"


def get_assessment_dominant_dimension(db: Session, assessment_session_id: int | None) -> dict | None:
    if not assessment_session_id:
        return None

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == assessment_session_id).all()
    if not records:
        return None

    exam_nos = [record.exam_no for record in records]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all() if exam_nos else []
    question_map = {question.exam_no: question for question in questions}
    module_by_dimension = {dimension_id: module for module, dimension_id in MODULE_DIM_MAP.items()}
    module_scores = {module: 0.0 for module in MODULE_DISPLAY_NAMES}
    module_counts = {module: 0 for module in MODULE_DISPLAY_NAMES}

    for record in records:
        question = question_map.get(record.exam_no)
        module_key = module_by_dimension.get(question.dimension_id) if question else None
        if not module_key:
            continue
        module_scores[module_key] += float(record.score or 0)
        module_counts[module_key] += 1

    weight_bonus = calculate_weight_bonus(records, question_map)
    weighted_scores = {
        module: clamp_score(module_scores[module] + weight_bonus.get(module, 0))
        for module in MODULE_DISPLAY_NAMES
    }
    dominant_key = max(
        weighted_scores,
        key=lambda module: (weighted_scores[module], module_scores[module], module_counts[module], module),
    )
    if weighted_scores[dominant_key] <= 0:
        return None

    return {
        "key": dominant_key,
        "label": MODULE_DISPLAY_NAMES[dominant_key],
        "score": round(weighted_scores[dominant_key], 2),
        "question_count": module_counts[dominant_key],
    }


def serialize_assessment_info(assessment_session: AssessmentSession | None, db: Session | None = None) -> dict | None:
    if assessment_session is None:
        return None

    info = {
        "session_id": assessment_session.id,
        "title": build_assessment_title(assessment_session),
        "started_at": assessment_session.started_at.isoformat() if assessment_session.started_at else None,
        "finished_at": assessment_session.finished_at.isoformat() if assessment_session.finished_at else None,
        "has_report": assessment_session.report_content is not None,
    }
    if db is not None:
        info["dominant_dimension"] = get_assessment_dominant_dimension(db, assessment_session.id)
    return info


def serialize_big_five_report_info(report: BigFivePersonalityReport | None) -> dict | None:
    if report is None:
        return None

    return {
        "report_id": report.id,
        "title": build_big_five_report_title(report),
        "status": report.status,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
        "model_version": report.model_version,
        "scores": report.scores,
        "is_real_result": bool(report.is_real_result),
        "interpretation_status": report.interpretation_status,
        "has_interpretation": bool(report.interpretation_content),
    }


def is_big_five_report_usable(report: BigFivePersonalityReport | None) -> bool:
    return bool(report and report.status == "completed" and report.is_real_result and report.scores)


def is_auto_generated_chat_title(chat_session: ChatSession) -> bool:
    normalized_title = (chat_session.title or "").strip()
    if not normalized_title:
        return True

    candidate_titles = {"新对话"}
    if chat_session.assessment_session_id:
        candidate_titles.add(f"测评 #{chat_session.assessment_session_id} 咨询")
    if chat_session.assessment_session is not None:
        candidate_titles.add(build_default_chat_title(chat_session.assessment_session, chat_session.big_five_report))
        candidate_titles.add(build_assessment_title(chat_session.assessment_session))
    if chat_session.big_five_report is not None:
        candidate_titles.add(build_default_chat_title(chat_session.assessment_session, chat_session.big_five_report))
        candidate_titles.add(build_big_five_report_title(chat_session.big_five_report))
    return normalized_title in candidate_titles


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


def chat_session_has_visible_history(db: Session, chat_session_id: int) -> bool:
    return (
        db.query(ChatMessageModel)
        .filter(
            ChatMessageModel.chat_session_id == chat_session_id,
            ChatMessageModel.role != "system",
        )
        .first()
        is not None
    )


def clear_chat_messages(db: Session, chat_session_id: int, system_only: bool = False) -> None:
    query = db.query(ChatMessageModel).filter(ChatMessageModel.chat_session_id == chat_session_id)
    if system_only:
        query = query.filter(ChatMessageModel.role == "system")
    query.delete(synchronize_session=False)
    db.commit()


def append_chat_message(
    db: Session,
    chat_session_id: int,
    user_id: int,
    role: str,
    content: str,
    legacy_session_id: int | None = None,
) -> ChatMessageModel:
    message = ChatMessageModel(
        chat_session_id=chat_session_id,
        session_id=legacy_session_id,
        user_id=user_id,
        role=role,
        content=content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def extract_text_only_report_content(report_content: str | None) -> str:
    """仅保留报告中的文字内容，剔除图片、图表和代码块标记。"""
    if not report_content:
        return "暂无报告"

    text = report_content
    # 移除 fenced code block（例如 mermaid、图表配置等）
    text = re.sub(r"```[\s\S]*?```", "\n", text)
    # 移除 markdown 图片
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", "", text)
    # 保留 markdown 链接文本，移除 URL
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    # 移除常见图片/图表 HTML 标签
    text = re.sub(r"<(img|svg|canvas|figure|figcaption)[^>]*>[\s\S]*?</\1>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<(img|svg|canvas)[^>]*/?>", "", text, flags=re.IGNORECASE)
    # 去掉剩余 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 去掉 markdown 格式符号，仅保留文本
    text = re.sub(r"^[>#*\-\s`]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"[_~`]+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    cleaned = text.strip()
    return cleaned or "暂无报告"


def get_assessment_context(assessment_session_id: int, db: Session) -> str:
    """获取测评报告和答题记录作为上下文"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == assessment_session_id).first()
    if not session:
        return ""

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == assessment_session_id).all()
    report_text = extract_text_only_report_content(session.report_content)

    context = f"""【用户心理测评报告】
{report_text}

【答题记录】
"""
    for r in records:
        context += f"- {r.exam_no}: 选择'{r.selected_option}', 得分{r.score}, 耗时{r.time_spent}s"
        if r.is_anomaly:
            context += f" [异常: {r.ai_follow_up}]"
        context += "\n"

    return context


def _format_big_five_score(value) -> str:
    try:
        return f"{float(value) * 100:.0f}/100"
    except (TypeError, ValueError):
        return "暂无"


def get_big_five_context(big_five_report_id: int, db: Session) -> str:
    """获取大五人格报告作为视频多模态上下文。"""
    report = db.query(BigFivePersonalityReport).filter(BigFivePersonalityReport.id == big_five_report_id).first()
    if not is_big_five_report_usable(report):
        return ""

    scores = report.scores or {}
    lines = [
        "【视频大五人格报告】",
        f"报告名称：{build_big_five_report_title(report)}",
        f"模型版本：{report.model_version}",
        "五维得分（0-100）：",
    ]
    for key, label in BIG_FIVE_DIMENSIONS:
        lines.append(f"- {label}: {_format_big_five_score(scores.get(key))}")
    if report.interpretation_status == "completed" and report.interpretation_content:
        interpretation = extract_text_only_report_content(report.interpretation_content)
        lines.extend(
            [
                "",
                "【AI 详细解读】",
                interpretation[:6000],
            ]
        )
    lines.append("说明：该报告来自用户上传视频的多模态分析，可作为人格线索，不应被当作医学诊断或唯一判断依据。")
    return "\n".join(lines)


def build_system_prompt(assessment_context: str = "", big_five_context: str = "") -> str:
    """构建系统提示词"""
    context_blocks = [block for block in [assessment_context, big_five_context] if block]
    if context_blocks:
        return f"""你是一位专业的心理咨询师和心理分析专家。用户授权关联了以下报告资料，现在需要基于这些资料与用户进行深入的对话交流。

{chr(10).join(context_blocks)}

你的职责：
1. 根据已关联报告，解答用户关于自己心理状态和人格特征的疑问
2. 提供个性化的心理改善建议
3. 以专业、温暖、支持性的态度与用户交流
4. 区分 ATMR 问卷报告与视频大五人格报告的来源和边界，不把两者强行合并成单一结论
5. 如果用户的问题超出报告范围，可以基于心理学常识回答，但要说明这是通用建议

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


def ensure_assessment_owner(db: Session, assessment_session_id: int, user_id: int) -> AssessmentSession:
    assessment = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.id == assessment_session_id,
            AssessmentSession.user_id == user_id,
        )
        .first()
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="测评会话不存在")
    return assessment


def ensure_big_five_report_owner(db: Session, report_id: int, user_id: int) -> BigFivePersonalityReport:
    report = (
        db.query(BigFivePersonalityReport)
        .filter(
            BigFivePersonalityReport.id == report_id,
            BigFivePersonalityReport.user_id == user_id,
        )
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="大五人格报告不存在")
    if not is_big_five_report_usable(report):
        raise HTTPException(status_code=400, detail="这份大五人格报告暂时不能用于对话")
    return report


def init_chat_with_context(
    db: Session,
    chat_session: ChatSession,
    user_id: int,
    reset_history: bool = False,
):
    """为咨询会话初始化系统提示。"""
    # Rebinding to another assessment should not preserve prior turns.
    clear_chat_messages(db, chat_session.id, system_only=not reset_history)

    # 构建上下文
    assessment_context = ""
    if chat_session.assessment_session_id:
        assessment_context = get_assessment_context(chat_session.assessment_session_id, db)
    big_five_context = ""
    if chat_session.big_five_report_id:
        big_five_context = get_big_five_context(chat_session.big_five_report_id, db)

    system_prompt = build_system_prompt(assessment_context, big_five_context)
    append_chat_message(
        db,
        chat_session.id,
        user_id,
        "system",
        system_prompt,
        legacy_session_id=chat_session.assessment_session_id,
    )


async def generate_reply(messages: list[dict]) -> str:
    """调用 LLM API 生成回复"""
    api_key = get_deepseek_api_key()
    if not api_key:
        return "【错误】未配置 API 密钥"

    try:
        client = httpx.AsyncClient(timeout=60.0)
        try:
            response = await client.post(
                get_deepseek_chat_completions_url(),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": get_deepseek_chat_model(),
                    "messages": messages,
                    "temperature": 1,
                    "max_tokens": 2000,
                    **build_deepseek_thinking_payload(get_deepseek_chat_thinking_mode()),
                },
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]
        finally:
            try:
                await client.aclose()
            except RuntimeError:
                pass  # Windows ProactorEventLoop 已知问题，可安全忽略
    except httpx.HTTPStatusError as e:
        return f"【API错误】API 错误: {e.response.status_code}"
    except Exception as e:
        return f"【异常】调用 API 失败: {str(e)}"


async def stream_reply_chunks(messages: list[dict]):
    """调用 LLM API 并按增量片段流式返回回复内容。"""
    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("未配置 API 密钥")

    timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            get_deepseek_chat_completions_url(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": get_deepseek_chat_model(),
                "messages": messages,
                "temperature": 1,
                "max_tokens": 2000,
                "stream": True,
                **build_deepseek_thinking_payload(get_deepseek_chat_thinking_mode()),
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue

                data = line[5:].strip()
                if data == "[DONE]":
                    break

                payload = json.loads(data)
                choices = payload.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content


async def prepare_chat_messages(
    db: Session,
    chat_session: ChatSession,
    user_id: int,
    message_text: str,
) -> list[dict]:
    """准备一次聊天调用所需上下文，并持久化用户消息。"""
    all_msgs = get_chat_messages(db, chat_session.id, include_system=True)
    if not all_msgs:
        init_chat_with_context(db, chat_session, user_id)

    rag_contexts: list[dict] = []
    if chat_session.assessment_session_id:
        try:
            atmr_rag_context = await retrieve_knowledge(message_text, max_sections=3, max_chars=2000)
            if atmr_rag_context:
                rag_contexts.append(
                    {
                        "title": "ATMR 知识库参考资料",
                        "content": (
                            "以下是与用户问题相关的 ATMR 心理学专业知识，"
                            f"请结合这些资料回答用户问题，并在适当时引用理论依据：\n\n{atmr_rag_context}"
                        ),
                    }
                )
        except Exception as e:
            print(f"[Chat] ATMR RAG 检索失败: {e}")

    if chat_session.big_five_report_id:
        try:
            big_five_rag_context = await retrieve_big_five_knowledge(message_text, max_sections=3, max_chars=2000)
            if big_five_rag_context:
                rag_contexts.append(
                    {
                        "title": "大五人格知识库参考资料",
                        "content": (
                            "以下是与用户问题相关的大五人格知识库资料。"
                            "请把它作为视频大五报告的解释辅助，不要替代用户真实经历：\n\n"
                            f"{big_five_rag_context}"
                        ),
                    }
                )
        except Exception as e:
            print(f"[Chat] 大五 RAG 检索失败: {e}")

    append_chat_message(
        db,
        chat_session.id,
        user_id,
        "user",
        message_text,
        legacy_session_id=chat_session.assessment_session_id,
    )

    from datetime import datetime

    chat_session.updated_at = datetime.now()
    if is_auto_generated_chat_title(chat_session):
        chat_session.title = message_text[:20] + ("..." if len(message_text) > 20 else "")
    db.commit()

    persisted = serialize_messages(get_chat_messages(db, chat_session.id, include_system=True), include_system=True)
    llm_messages = list(persisted)
    for context in rag_contexts:
        llm_messages.append(
            {
                "role": "system",
                "content": f"【{context['title']}】{context['content']}",
            }
        )
    return llm_messages


def sse_event(event: str, data: dict) -> str:
    """构造单条 SSE 消息。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ==================== API ====================

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
        assessment_info = serialize_assessment_info(s.assessment_session, db) if s.assessment_session_id else None
        big_five_report_info = serialize_big_five_report_info(s.big_five_report) if s.big_five_report_id else None

        result.append(
            {
                "id": s.id,
                "title": s.title,
                "assessment_session_id": s.assessment_session_id,
                "big_five_report_id": s.big_five_report_id,
                "assessment_info": assessment_info,
                "big_five_report_info": big_five_report_info,
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
    assessment = None
    big_five_report = None
    # 如果指定了关联测评，校验归属
    if payload.assessment_session_id:
        assessment = ensure_assessment_owner(db, payload.assessment_session_id, current_user.id)

    if payload.big_five_report_id:
        big_five_report = ensure_big_five_report_owner(db, payload.big_five_report_id, current_user.id)

    title = payload.title or "新对话"
    if not payload.title and (assessment is not None or big_five_report is not None):
        title = build_default_chat_title(assessment, big_five_report)

    chat_session = ChatSession(
        user_id=current_user.id,
        assessment_session_id=payload.assessment_session_id if payload.assessment_session_id and payload.assessment_session_id > 0 else None,
        big_five_report_id=payload.big_five_report_id if payload.big_five_report_id and payload.big_five_report_id > 0 else None,
        title=title,
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)

    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "assessment_session_id": chat_session.assessment_session_id,
        "big_five_report_id": chat_session.big_five_report_id,
        "assessment_info": serialize_assessment_info(assessment, db),
        "big_five_report_info": serialize_big_five_report_info(big_five_report),
    }


@router.put("/sessions/{chat_session_id}")
async def update_chat_session(
    chat_session_id: int,
    payload: UpdateChatSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改咨询会话（切换关联报告、修改标题）"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)
    should_refresh_default_title = False

    assessment_changed = False
    big_five_changed = False
    next_assessment = chat_session.assessment_session
    next_big_five_report = chat_session.big_five_report

    if payload.assessment_session_id is not None:
        next_assessment_id = payload.assessment_session_id if payload.assessment_session_id > 0 else None
        if next_assessment_id != chat_session.assessment_session_id:
            assessment_changed = True
            should_refresh_default_title = is_auto_generated_chat_title(chat_session)
            next_assessment = (
                ensure_assessment_owner(db, next_assessment_id, current_user.id)
                if next_assessment_id is not None
                else None
            )

    if payload.big_five_report_id is not None:
        next_report_id = payload.big_five_report_id if payload.big_five_report_id > 0 else None
        if next_report_id != chat_session.big_five_report_id:
            big_five_changed = True
            should_refresh_default_title = should_refresh_default_title or is_auto_generated_chat_title(chat_session)
            next_big_five_report = (
                ensure_big_five_report_owner(db, next_report_id, current_user.id)
                if next_report_id is not None
                else None
            )

    association_changed = assessment_changed or big_five_changed
    if association_changed and chat_session_has_visible_history(db, chat_session.id) and not payload.reset_history:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "chat_session_has_history",
                "message": "当前会话已经有历史消息，切换关联报告需要重置当前对话。",
                "reset_required": True,
            },
        )

    if assessment_changed:
        chat_session.assessment_session_id = next_assessment.id if next_assessment is not None else None
        chat_session.assessment_session = next_assessment

    if big_five_changed:
        chat_session.big_five_report_id = next_big_five_report.id if next_big_five_report is not None else None
        chat_session.big_five_report = next_big_five_report

    if payload.title is not None:
        chat_session.title = payload.title
    elif association_changed and should_refresh_default_title:
        chat_session.title = build_default_chat_title(chat_session.assessment_session, chat_session.big_five_report)

    db.commit()

    if association_changed:
        init_chat_with_context(db, chat_session, current_user.id, reset_history=payload.reset_history)
        db.refresh(chat_session)

    return {
        "id": chat_session.id,
        "title": chat_session.title,
        "assessment_session_id": chat_session.assessment_session_id,
        "big_five_report_id": chat_session.big_five_report_id,
        "assessment_info": serialize_assessment_info(chat_session.assessment_session, db),
        "big_five_report_info": serialize_big_five_report_info(chat_session.big_five_report),
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

    return {
        "messages": serialize_messages(get_chat_messages(db, chat_session_id, include_system=False)),
        "assessment_session_id": chat_session.assessment_session_id,
        "big_five_report_id": chat_session.big_five_report_id,
        "assessment_info": serialize_assessment_info(chat_session.assessment_session, db),
        "big_five_report_info": serialize_big_five_report_info(chat_session.big_five_report),
        "title": chat_session.title,
    }


@router.post("/sessions/{chat_session_id}/stream")
async def stream_message(
    chat_session_id: int,
    payload: ChatSendRequest,
    current_user: User = Depends(get_current_user),
):
    """流式发送消息并返回增量回复。"""
    user_id = current_user.id

    async def event_generator():
        db = SessionLocal()
        reply_parts: list[str] = []
        try:
            chat_session = ensure_chat_session_owner(db, chat_session_id, user_id)
            llm_messages = await prepare_chat_messages(db, chat_session, user_id, payload.message)

            yield sse_event("start", {"chat_session_id": chat_session_id})
            async for chunk in stream_reply_chunks(llm_messages):
                reply_parts.append(chunk)
                yield sse_event("delta", {"content": chunk})

            reply = "".join(reply_parts).strip()
            if not reply:
                reply = "抱歉，这次我没有生成有效回复。请再试一次。"

            append_chat_message(
                db,
                chat_session_id,
                user_id,
                "assistant",
                reply,
                legacy_session_id=chat_session.assessment_session_id,
            )
            yield sse_event(
                "done",
                {
                    "reply": reply,
                    "messages": serialize_messages(get_chat_messages(db, chat_session_id, include_system=False)),
                },
            )
            yield ": stream-end\n\n"
        except HTTPException as e:
            yield sse_event("error", {"message": e.detail})
        except httpx.HTTPStatusError as e:
            print(f"[Chat] LLM API 错误: {e.response.status_code}")
            yield sse_event("error", {"message": f"LLM API 错误: {e.response.status_code}"})
        except Exception as e:
            print(f"[Chat] 流式回复失败: {e}")
            yield sse_event("error", {"message": f"流式回复失败: {str(e)}"})
        finally:
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{chat_session_id}/send")
async def send_message(
    chat_session_id: int,
    payload: ChatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """发送消息并获取回复。"""
    chat_session = ensure_chat_session_owner(db, chat_session_id, current_user.id)
    llm_messages = await prepare_chat_messages(db, chat_session, current_user.id, payload.message)

    reply = await generate_reply(llm_messages)
    append_chat_message(
        db,
        chat_session_id,
        current_user.id,
        "assistant",
        reply,
        legacy_session_id=chat_session.assessment_session_id,
    )

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

    clear_chat_messages(db, chat_session_id)

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
            serialize_assessment_info(s, db)
            for s in sessions
        ]
    }


@router.get("/available-reports")
async def get_available_reports(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取对话可关联的 ATMR 报告和大五人格报告。"""
    sessions = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == current_user.id,
            AssessmentSession.status == "completed",
        )
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )
    big_five_reports = (
        db.query(BigFivePersonalityReport)
        .filter(
            BigFivePersonalityReport.user_id == current_user.id,
            BigFivePersonalityReport.status == "completed",
            BigFivePersonalityReport.is_real_result.is_(True),
        )
        .order_by(BigFivePersonalityReport.created_at.desc())
        .all()
    )

    return {
        "atmr_reports": [serialize_assessment_info(session, db) for session in sessions],
        "big_five_reports": [
            serialize_big_five_report_info(report)
            for report in big_five_reports
            if report.scores
        ],
    }
