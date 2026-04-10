# app/api/assessment.py

import numpy as np
import asyncio
import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.models.question import SessionLocal, Question, AnswerRecord, AssessmentSession, ModuleDebateResult, User
from app.services.ai_detector import check_anomaly_and_generate_question
from app.services.report_service import build_debate_context, save_report_to_file
from app.services.question_selection import select_adaptive_question, QuestionSelectionService
from app.core.security import get_current_user
from agent.debate_manager import run_debate_streaming

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 测评配置常量
TOTAL_QUESTIONS = 42  # 总题数: 前2题固定 + 4个模块各10题
FIXED_QUESTIONS = 2   # 前两题固定
QUESTIONS_PER_MODULE = 10  # 每个模块10题
MODULES = ['A', 'T', 'M', 'R']  # 模块顺序


def get_current_module_and_stage(answered_count: int):
    """
    根据已答题数确定当前阶段和模块

    Args:
        answered_count: 已答题数量

    Returns:
        tuple: (module, stage)
            module: 当前模块 ('A','T','M','R')，前两题返回None
            stage: 当前阶段描述
    """
    if answered_count < FIXED_QUESTIONS:
        return None, "fixed"

    # 计算模块内题号 (0-based)
    module_index = (answered_count - FIXED_QUESTIONS) // QUESTIONS_PER_MODULE
    if module_index < len(MODULES):
        return MODULES[module_index], "module"

    # 超出范围，返回最后一个模块
    return MODULES[-1], "module"


async def run_module_debate_async(session_id: int, user_id: int, module: str):
    """
    异步执行模块级专家辩论
    使用多个AI专家并行分析模块答题数据，并注入 RAG 知识库证据
    """
    import os
    import asyncio
    from openai import AsyncOpenAI
    from app.services.rag_service import retrieve_evidence_for_debate

    db = SessionLocal()
    try:
        print(f"[模块辩论 {module}] 开始异步辩论分析...")

        # 1. 获取该模块的所有答题记录
        module_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}
        target_dimension = module_map.get(module)

        # 查询该会话中该维度的所有答题记录
        records = db.query(AnswerRecord).filter(
            AnswerRecord.session_id == session_id,
            AnswerRecord.user_id == user_id
        ).all()

        # 批量查询题目，避免 N+1
        exam_nos = [r.exam_no for r in records]
        questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
        question_map = {q.exam_no: q for q in questions}

        module_records = []
        for r in records:
            question = question_map.get(r.exam_no)
            if question and question.dimension_id == target_dimension:
                module_records.append({
                    "exam_no": r.exam_no,
                    "question": question.content,
                    "selected_option": r.selected_option,
                    "score": float(r.score) if r.score is not None else 0,
                    "time_spent": float(r.time_spent) if r.time_spent is not None else 0,
                    "is_anomaly": r.is_anomaly,
                    "user_explanation": r.user_explanation if hasattr(r, 'user_explanation') else None,
                    "is_reverse": question.is_reverse,
                    "trait_label": question.trait_label
                })

        if not module_records:
            print(f"[模块辩论 {module}] 未找到答题记录")
            return

        # 2. 构建模块数据摘要
        total_score = sum(r["score"] for r in module_records)
        avg_score = total_score / len(module_records) if module_records else 0
        anomaly_count = sum(1 for r in module_records if r["is_anomaly"])

        module_data = {
            "module": module,
            "dimension_id": target_dimension,
            "question_count": len(module_records),
            "total_score": total_score,
            "average_score": round(avg_score, 2),
            "anomaly_count": anomaly_count,
            "records": module_records
        }

        data_json = json.dumps(module_data, ensure_ascii=False, indent=2)

        # 2.5 从 RAG 知识库检索相关证据
        user_traits = f"模块{module}, 总分{total_score}, 平均分{avg_score:.2f}"
        try:
            rag_evidence = await retrieve_evidence_for_debate(user_traits, module)
            if rag_evidence:
                print(f"[模块辩论 {module}] RAG 检索到 {len(rag_evidence)} 字符的证据")
            else:
                rag_evidence = ""
                print(f"[模块辩论 {module}] RAG 未检索到相关证据")
        except Exception as e:
            rag_evidence = ""
            print(f"[模块辩论 {module}] RAG 检索失败: {e}")

        # 构建 RAG 知识参考段落
        rag_context = ""
        if rag_evidence:
            rag_context = f"""

【ATMR 理论知识参考（来自知识库）】
{rag_evidence}

请结合以上理论知识进行分析，在分析中引用知识库中的理论依据。"""

        # 3. 定义专家提示词
        experts = {
            "psychologist": {
                "name": "心理学专家",
                "prompt": f"""你是一位资深心理学专家，专注于分析ATMR测评中的{module}模块（{'欣赏型' if module=='A' else '目标型' if module=='T' else '包容型' if module=='M' else '责任型'}）。

请分析以下用户答题数据，从心理学角度：
1. 评估用户在该维度上的心理特质水平
2. 分析答题模式（一致性、极端性、矛盾性）
3. 识别潜在的心理优势和发展空间
4. 给出专业的心理学解读
{rag_context}

数据：{data_json}

请用中文输出你的专业分析（不超过400字）。"""
            },
            "behaviorist": {
                "name": "行为分析师",
                "prompt": f"""你是一位行为分析师，专注于从行为数据中发现模式。

请分析以下用户在{module}模块的答题行为：
1. 作答时间分布是否合理
2. 是否存在异常作答模式（过快/过慢）
3. 用户对异常追问的解释说明了什么
4. 行为数据与选项选择的一致性
{rag_context}

数据：{data_json}

请用中文输出你的行为分析（不超过400字）。"""
            },
            "critic": {
                "name": "批判性评估师",
                "prompt": f"""你是一位批判性评估师，负责质疑和挑战初步结论。

请对以下{module}模块的答题数据提出批判性观点：
1. 数据是否存在矛盾或不可信之处
2. 可能存在的测量误差或干扰因素
3. 对高分/低分解释的替代假设
4. 建议需要进一步验证的方面
{rag_context}

数据：{data_json}

请用中文输出你的批判性评估（不超过400字）。"""
            }
        }

        # 4. 并行调用多个专家
        async def call_expert(expert_key, expert_config):
            """调用单个专家"""
            try:
                client = AsyncOpenAI(
                    api_key=os.environ.get("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com/v1"
                )

                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是ATMR心理测评系统的专家分析师。"},
                        {"role": "user", "content": expert_config["prompt"]}
                    ],
                    temperature=0.7,
                    max_tokens=800
                )

                return {
                    "expert": expert_config["name"],
                    "content": response.choices[0].message.content,
                    "status": "success"
                }
            except Exception as e:
                return {
                    "expert": expert_config["name"],
                    "content": f"分析失败: {str(e)}",
                    "status": "error"
                }

        # 并行执行所有专家分析
        tasks = [
            call_expert(key, config)
            for key, config in experts.items()
        ]

        expert_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 5. 整合专家意见
        synthesis_prompt = f"""作为ATMR测评系统的主分析师，请综合以下三位专家的意见，生成{module}模块的最终评估结论。

专家意见：
"""
        for result in expert_results:
            if isinstance(result, dict) and result.get("status") == "success":
                synthesis_prompt += f"\n【{result['expert']}】\n{result['content']}\n"

        synthesis_prompt += """
请输出一个简洁的模块评估总结（不超过400字），包含：
1. 该模块的核心特质水平评估
2. 关键发现或注意事项
3. 与其他模块的关联预期

格式：直接输出总结文本，不要加标题。"""

        # 生成综合结论
        try:
            client = AsyncOpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1"
            )
            synthesis_response = await client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是ATMR心理测评系统的主分析师。"},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.5,
                max_tokens=300
            )
            final_conclusion = synthesis_response.choices[0].message.content
        except Exception as e:
            final_conclusion = f"模块{module}综合评估生成失败: {str(e)}"

        # 6. 保存辩论结果
        result_content = f"""# 模块 {module} 专家辩论结果

## 数据摘要
- 题目数: {len(module_records)}
- 总得分: {total_score:.2f}
- 平均分: {avg_score:.2f}
- 异常标记: {anomaly_count} 次

## 专家分析
"""
        for result in expert_results:
            if isinstance(result, dict):
                result_content += f"\n### {result['expert']}\n{result.get('content', '无内容')}\n"

        result_content += f"\n## 综合结论\n{final_conclusion}\n"

        if rag_evidence:
            result_content += f"\n## 知识库引用\n{rag_evidence[:500]}...\n"

        debate_result = ModuleDebateResult(
            session_id=session_id,
            user_id=user_id,
            module=module,
            result_content=result_content
        )
        db.add(debate_result)
        db.commit()

        print(f"[模块辩论 {module}] 辩论完成，结果已保存")
        print(f"[模块辩论 {module}] 综合结论: {final_conclusion[:100]}...")

    except Exception as e:
        print(f"[模块辩论 {module}] 失败: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


# 保留旧函数名作为兼容层
trigger_module_debate = run_module_debate_async


# --- Schema 定义 ---
class StartSessionRequest(BaseModel):
    pass  # user_id 从 JWT token 获取


class SubmitModuleRequest(BaseModel):
    session_id: int
    module: str  # A/T/M/R


class SaveAnswerRequest(BaseModel):
    session_id: int
    exam_no: str
    selected_option: str
    time_spent: float
    score: float
    is_anomaly: int = 0
    ai_follow_up: Optional[str] = None
    user_explanation: Optional[str] = None

class AnswerSubmitRequest(BaseModel):
    session_id: int
    exam_no: str
    selected_option: str
    time_spent: float


class AnswerSubmitResponse(BaseModel):
    status: str
    message: str
    score: float
    follow_up_question: Optional[str] = None
    risk_score: Optional[int] = None
    risk_reasons: list[str] = Field(default_factory=list)


class ExplanationSubmitRequest(BaseModel):
    session_id: int
    exam_no: str
    text: str


class CheckAnswerRequest(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float


class BatchAnswerItem(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float
    user_explanation: Optional[str] = None


class BatchSubmitRequest(BaseModel):
    session_id: int
    answers: list[BatchAnswerItem]


class AdaptiveAnswerItem(BaseModel):
    exam_no: str
    selected_option: str
    time_spent: float
    score: float
    status: str
    user_explanation: Optional[str] = None


class AdaptiveQuestionRequest(BaseModel):
    """智能选题请求"""
    session_id: int
    module: Optional[str] = None  # 模块类型: A/T/M/R
    answers: list[AdaptiveAnswerItem] = Field(default_factory=list)


def calculate_question_score(db_question: Question, selected_option: str) -> float:
    """计算题目分数（支持反向计分）"""
    current_score = 0.0
    opt_index = db_question.options.index(selected_option)
    raw_score = float(db_question.scores[opt_index])
    if db_question.is_reverse:
        return 6.0 - raw_score
    return raw_score


async def analyze_answer(
        db_question: Question,
        selected_option: str,
        time_spent: float,
        recent_answers: Optional[list[dict]] = None,
) -> tuple[float, dict]:
    """计算分数并执行异常检测"""
    score = calculate_question_score(db_question, selected_option)
    detection_result = await check_anomaly_and_generate_question(
        time_spent=time_spent,
        avg_time=float(db_question.avg_time or 8.0),
        question_content=db_question.content,
        selected_option=selected_option,
        recent_answers=recent_answers or [],
        available_options=db_question.options,
    )
    return score, detection_result


def ensure_session_owner(db: Session, session_id: int, user_id: int) -> AssessmentSession:
    """校验会话属于当前用户"""
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")
    return session


def build_recent_answer_context(db: Session, session_id: int, user_id: int, limit: int = 5) -> list[dict]:
    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session_id,
        AnswerRecord.user_id == user_id,
    ).order_by(AnswerRecord.created_at.asc()).all()
    return [
        {
            "exam_no": record.exam_no,
            "selected_option": record.selected_option,
            "time_spent": float(record.time_spent or 0),
            "score": float(record.score or 0),
            "is_anomaly": int(record.is_anomaly or 0),
        }
        for record in records[-limit:]
    ]


def build_transient_answer_context(db: Session, answers: list[AdaptiveAnswerItem]) -> dict:
    """将前端本地答案快照归一化为自适应选题可用的上下文"""
    if not answers:
        return {
            "answered_question_nos": [],
            "answered_ids": [],
            "answered_count": 0,
            "question_map": {},
            "transient_records": [],
        }

    answered_question_nos = [item.exam_no for item in answers]
    if len(answered_question_nos) != len(set(answered_question_nos)):
        raise HTTPException(status_code=400, detail="自适应选题请求中存在重复题目")

    questions = db.query(Question).filter(Question.exam_no.in_(answered_question_nos)).all()
    question_map = {q.exam_no: q for q in questions}
    if len(question_map) != len(answered_question_nos):
        raise HTTPException(status_code=400, detail="自适应选题请求中存在无效题目编号")

    transient_records = []
    answered_ids = []
    for item in answers:
        question = question_map[item.exam_no]
        answered_ids.append(question.id)
        transient_records.append({
            "exam_no": item.exam_no,
            "selected_option": item.selected_option,
            "score": item.score,
            "time_spent": item.time_spent,
            "is_anomaly": item.status == "anomaly",
            "user_explanation": item.user_explanation,
        })

    return {
        "answered_question_nos": answered_question_nos,
        "answered_ids": answered_ids,
        "answered_count": len(answered_question_nos),
        "question_map": question_map,
        "transient_records": transient_records,
    }


def trigger_completed_module_debates(db: Session, session_id: int, user_id: int, background_tasks: BackgroundTasks):
    """检测已完成模块并触发辩论"""
    all_records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session_id,
        AnswerRecord.user_id == user_id
    ).all()
    if not all_records:
        return

    all_exam_nos = [rec.exam_no for rec in all_records]
    all_questions = db.query(Question).filter(Question.exam_no.in_(all_exam_nos)).all() if all_exam_nos else []
    all_q_map = {q.exam_no: q for q in all_questions}

    existing_modules = {
        r.module for r in db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).all()
    }
    module_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}

    for module, target_dimension in module_map.items():
        if module in existing_modules:
            continue
        module_questions_count = 0
        for record in all_records:
            question = all_q_map.get(record.exam_no)
            if question and question.dimension_id == target_dimension:
                module_questions_count += 1
        if module_questions_count >= QUESTIONS_PER_MODULE:
            background_tasks.add_task(trigger_module_debate, session_id, user_id, module)


# --- 接口 0：启动新会话 ---
@router.post("/start-session")
async def start_session(payload: StartSessionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 清理该用户所有旧的 active 会话及其草稿记录
    old_sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
    ).all()
    for old in old_sessions:
        db.query(AnswerRecord).filter(AnswerRecord.session_id == old.id).delete()
        db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == old.id).delete()
        db.delete(old)
    db.commit()

    new_session = AssessmentSession(user_id=current_user.id, status='active')
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"session_id": new_session.id, "status": "success"}


# --- 接口 0.1：实时保存单题答案（草稿） ---
@router.post("/save-answer")
async def save_answer(payload: SaveAnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = ensure_session_owner(db, payload.session_id, current_user.id)
    if session.status == 'completed':
        raise HTTPException(status_code=400, detail="该测评已完成")

    existing = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
        AnswerRecord.exam_no == payload.exam_no,
    ).first()

    if existing:
        existing.selected_option = payload.selected_option
        existing.time_spent = payload.time_spent
        existing.score = payload.score
        existing.is_anomaly = payload.is_anomaly
        existing.ai_follow_up = payload.ai_follow_up
        existing.user_explanation = payload.user_explanation
    else:
        db.add(AnswerRecord(
            session_id=payload.session_id,
            user_id=current_user.id,
            exam_no=payload.exam_no,
            selected_option=payload.selected_option,
            score=payload.score,
            time_spent=payload.time_spent,
            is_anomaly=payload.is_anomaly,
            ai_follow_up=payload.ai_follow_up,
            user_explanation=payload.user_explanation,
        ))
    db.commit()
    return {"status": "success"}


# --- 接口 0.2：恢复未完成会话 ---
@router.get("/resume-session")
async def resume_session(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
    ).order_by(AssessmentSession.started_at.desc()).first()

    if not session:
        return {"has_active_session": False}

    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == session.id,
        AnswerRecord.user_id == current_user.id,
    ).all()

    if not records:
        return {"has_active_session": False}

    exam_nos = [r.exam_no for r in records]
    questions = db.query(Question).filter(
        Question.exam_no.in_(exam_nos)
    ).all()
    q_map = {q.exam_no: q for q in questions}

    answers_data = []
    questions_data = []
    for r in records:
        q = q_map.get(r.exam_no)
        answers_data.append({
            "exam_no": r.exam_no,
            "selected_option": r.selected_option,
            "time_spent": float(r.time_spent) if r.time_spent else 0,
            "score": float(r.score) if r.score else 0,
            "is_anomaly": r.is_anomaly,
            "ai_follow_up": r.ai_follow_up,
            "user_explanation": r.user_explanation,
        })
        if q:
            questions_data.append({
                "examNo": q.exam_no,
                "exam": q.content,
                "options": q.options,
            })

    return {
        "has_active_session": True,
        "session_id": session.id,
        "answered_count": len(records),
        "answers": answers_data,
        "questions": questions_data,
    }


# --- 接口 0.3：重新打开已完成会话（用于修改答案） ---
@router.post("/reopen-session/{session_id}")
async def reopen_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = ensure_session_owner(db, session_id, current_user.id)
    if session.status != 'completed':
        raise HTTPException(status_code=400, detail="该会话不是已完成状态")

    # 先关闭该用户其他 active 会话
    old_active = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == current_user.id,
        AssessmentSession.status == 'active',
        AssessmentSession.id != session_id,
    ).all()
    for old in old_active:
        db.query(AnswerRecord).filter(AnswerRecord.session_id == old.id).delete()
        db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == old.id).delete()
        db.delete(old)

    # 重新打开会话
    session.status = 'active'
    session.finished_at = None
    session.report_content = None
    session.report_file_path = None
    # 清除模块辩论结果（重新提交后会重新生成）
    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).delete()
    db.commit()

    return {"status": "success", "session_id": session_id}


# --- 接口 0.4：手动提交模块触发辩论 ---
MODULE_COOLDOWN_SECONDS = 30

@router.post("/submit-module")
async def submit_module(payload: SubmitModuleRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    module = payload.module.upper()
    if module not in MODULES:
        raise HTTPException(status_code=400, detail=f"无效模块: {module}")

    session = ensure_session_owner(db, payload.session_id, current_user.id)

    # 检查该模块答题数是否足够
    module_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}
    target_dimension = module_map[module]

    records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
    ).all()
    exam_nos = [r.exam_no for r in records]
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all() if exam_nos else []
    q_map = {q.exam_no: q for q in questions}

    module_count = sum(1 for r in records if q_map.get(r.exam_no) and q_map[r.exam_no].dimension_id == target_dimension)
    if module_count < QUESTIONS_PER_MODULE:
        raise HTTPException(status_code=400, detail=f"模块 {module} 答题不足 {QUESTIONS_PER_MODULE} 题（当前 {module_count} 题）")

    # 检查冷却时间
    from datetime import datetime, timedelta
    existing = db.query(ModuleDebateResult).filter(
        ModuleDebateResult.session_id == payload.session_id,
        ModuleDebateResult.module == module,
    ).first()

    if existing:
        elapsed = (datetime.now(existing.created_at.tzinfo) if existing.created_at.tzinfo else datetime.now()) - existing.created_at
        if elapsed.total_seconds() < MODULE_COOLDOWN_SECONDS:
            remaining = int(MODULE_COOLDOWN_SECONDS - elapsed.total_seconds())
            raise HTTPException(status_code=429, detail=f"请等待 {remaining} 秒后再重新提交")
        # 冷却已过，删除旧结果
        db.delete(existing)
        db.commit()

    # 触发模块辩论
    background_tasks.add_task(trigger_module_debate, payload.session_id, current_user.id, module)

    return {"status": "success", "message": f"模块 {module} 辩论已启动"}


# --- 接口 1：获取题目 (42题完整测评版) ---


@router.get("/question/{index}")
async def get_question(index: int, db: Session = Depends(get_db)):
    # 核心拦截：如果前端请求的题号达到了 10，直接告诉它测试结束了！
    if index >= TOTAL_QUESTIONS:
        raise HTTPException(status_code=404, detail="测评已完成")

    db_question = db.query(Question).offset(index).limit(1).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题库已做完")

    return {
        "examNo": db_question.exam_no,
        "exam": db_question.content,
        "options": db_question.options,
        "total": TOTAL_QUESTIONS  # 动态告诉前端，总进度条只有 10
    }


# --- 接口 1.1：智能选题（新增）---
@router.post("/adaptive-question")
async def get_adaptive_question(payload: AdaptiveQuestionRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    智能选题接口
    基于用户能力向量和题目特征向量，选择最合适的下一题
    """
    use_local_answers = bool(payload.answers)
    fallback_index = len(payload.answers)
    try:
        if use_local_answers:
            transient_context = build_transient_answer_context(db, payload.answers)
            answered_question_nos = transient_context["answered_question_nos"]
            answered_count = transient_context["answered_count"]
            answered_q_map = transient_context["question_map"]
            answered_ids = transient_context["answered_ids"]
            transient_records = transient_context["transient_records"]
        else:
            answered_records = db.query(AnswerRecord).filter(
                AnswerRecord.session_id == payload.session_id,
                AnswerRecord.user_id == current_user.id
            ).all()
            answered_question_nos = [record.exam_no for record in answered_records]
            answered_count = len(answered_question_nos)
            answered_questions = db.query(Question).filter(
                Question.exam_no.in_(answered_question_nos)
            ).all() if answered_question_nos else []
            answered_q_map = {q.exam_no: q for q in answered_questions}
            answered_ids = [q.id for q in answered_questions]
            transient_records = None
            fallback_index = answered_count

        if answered_count >= TOTAL_QUESTIONS:
            raise HTTPException(status_code=404, detail="测评已完成")

        current_module, stage = get_current_module_and_stage(answered_count)
        service = QuestionSelectionService(db)

        if current_module and stage == "module":
            module_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}
            target_dimension = module_map.get(current_module)
            module_answered_count = 0
            module_questions = []
            if target_dimension:
                for exam_no in answered_question_nos:
                    q = answered_q_map.get(exam_no)
                    if q and q.dimension_id == target_dimension:
                        module_answered_count += 1
                        module_questions.append(q.exam_no)
            print(f"[DEBUG] 总已答题数: {answered_count}, 当前模块: {current_module}, target_dimension: {target_dimension}")
            print(f"[DEBUG] 当前模块已答题: {module_questions}")
            print(f"[DEBUG] 当前模块已答: {module_answered_count}/{QUESTIONS_PER_MODULE}题")

            if module_answered_count >= QUESTIONS_PER_MODULE:
                current_module_index = MODULES.index(current_module) if current_module in MODULES else -1
                if current_module_index < len(MODULES) - 1:
                    current_module = MODULES[current_module_index + 1]
                    print(f"模块已答满10题，切换到下一个模块: {current_module}")
                else:
                    raise HTTPException(status_code=404, detail="所有模块已完成")

        next_question = None
        if stage == "fixed":
            fixed_query = db.query(Question).filter(Question.dimension_id == '1')
            if answered_ids:
                fixed_query = fixed_query.filter(Question.id.notin_(answered_ids))
            fixed_candidates = fixed_query.all()
            if fixed_candidates:
                next_question = fixed_candidates[0]
        else:
            next_question = service.select_next_question(
                current_user.id,
                payload.session_id,
                answered_ids,
                module=current_module,
                transient_records=transient_records,
            )

        is_adaptive = True
        similarity = None
        ability_vector_exists = False

        if next_question is not None:
            profile_vector, ability_level, _ = service.get_user_ability_vector(
                current_user.id,
                payload.session_id,
                current_module,
                transient_records=transient_records,
            )
            if profile_vector is not None and next_question.feature_vector:
                question_vector = np.array(next_question.feature_vector)
                similarity = service._cosine_similarity(profile_vector, question_vector)
                ability_vector_exists = True
        else:
            print(f"[DEBUG] 智能选题返回None，进入回退逻辑")
            print(f"[DEBUG] stage={stage}, current_module={current_module}")
            query = db.query(Question)
            if stage == "fixed":
                query = query.filter(Question.dimension_id == '1')
                print(f"[DEBUG] 回退逻辑：查询维度1的题目")
            elif current_module:
                module_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}
                if current_module in module_map:
                    query = query.filter(Question.dimension_id == module_map[current_module])
                    print(f"[DEBUG] 回退逻辑：查询模块 {current_module} (dimension_id={module_map[current_module]}) 的题目")

            if answered_ids:
                query = query.filter(Question.id.notin_(answered_ids))
                print(f"[DEBUG] 回退逻辑：排除已答题目 {len(answered_ids)} 道")

            from sqlalchemy import func
            next_question = query.order_by(
                func.cast(func.substr(Question.exam_no, 2), db.Integer)
            ).first()

            print(f"[DEBUG] 回退逻辑查询结果: {next_question.exam_no if next_question else 'None'}")

            if not next_question:
                raise HTTPException(status_code=404, detail="当前模块题目已用完")

            is_adaptive = False

        remaining = TOTAL_QUESTIONS - answered_count - 1
        if remaining < 0:
            remaining = 0

        selected_dimension = next_question.dimension_id
        selected_trait = next_question.trait_label

        return {
            "examNo": next_question.exam_no,
            "exam": next_question.content,
            "options": next_question.options,
            "total": TOTAL_QUESTIONS,
            "remaining": remaining,
            "is_adaptive": is_adaptive,
            "current_module": current_module,
            "selected_dimension": selected_dimension,
            "selected_trait": selected_trait,
            "question_stats": {
                "difficulty": float(next_question.difficulty or 0.5),
                "discrimination": float(next_question.discrimination or 0.7),
                "has_feature_vector": next_question.feature_vector is not None,
                "similarity": similarity,
                "ability_vector_exists": ability_vector_exists
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"智能选题错误: {e}")
        index = fallback_index
        if index >= TOTAL_QUESTIONS:
            raise HTTPException(status_code=404, detail="测评已完成")

        db_question = db.query(Question).offset(index).limit(1).first()
        if not db_question:
            raise HTTPException(status_code=404, detail="题库已做完")

        return {
            "examNo": db_question.exam_no,
            "exam": db_question.content,
            "options": db_question.options,
            "total": TOTAL_QUESTIONS,
            "remaining": TOTAL_QUESTIONS - index - 1,
            "is_adaptive": False,
            "error": "智能选题失败，使用顺序模式",
            "question_stats": {
                "difficulty": float(db_question.difficulty or 0.5),
                "discrimination": float(db_question.discrimination or 0.7),
                "has_feature_vector": db_question.feature_vector is not None,
                "similarity": None,
                "ability_vector_exists": False
            }
        }


# --- 接口 2：只检测答案，不落库 ---
@router.post("/check-answer", response_model=AnswerSubmitResponse)
async def check_answer(payload: CheckAnswerRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    try:
        current_score, detection_result = await analyze_answer(
            db_question,
            payload.selected_option,
            payload.time_spent,
            recent_answers=[],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"答案检测失败: {e}")

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="检测完成，尚未正式提交",
        score=current_score,
        follow_up_question=detection_result.get("follow_up"),
        risk_score=detection_result.get("risk_score"),
        risk_reasons=detection_result.get("reasons", []),
    )


# --- 接口 2.1：最终批量提交答案 ---
@router.post("/submit-batch")
async def submit_batch(payload: BatchSubmitRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = ensure_session_owner(db, payload.session_id, current_user.id)

    if session.status == 'completed':
        raise HTTPException(status_code=400, detail="该测评已提交，不能重复提交")

    if len(payload.answers) < TOTAL_QUESTIONS:
        raise HTTPException(status_code=400, detail=f"题目未全部完成，当前仅 {len(payload.answers)}/{TOTAL_QUESTIONS} 题")

    answer_map = {item.exam_no: item for item in payload.answers}
    if len(answer_map) != len(payload.answers):
        raise HTTPException(status_code=400, detail="存在重复题目答案")

    exam_nos = list(answer_map.keys())
    questions = db.query(Question).filter(Question.exam_no.in_(exam_nos)).all()
    question_map = {q.exam_no: q for q in questions}

    if len(question_map) != len(answer_map):
        raise HTTPException(status_code=400, detail="存在无效题目编号")

    # 清理旧正式记录，保证同一个 session 最终只有一份正式结果
    db.query(AnswerRecord).filter(AnswerRecord.session_id == payload.session_id).delete()
    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == payload.session_id).delete()
    db.commit()

    recent_answers = []
    for item in payload.answers:
        db_question = question_map[item.exam_no]
        score, detection_result = await analyze_answer(
            db_question,
            item.selected_option,
            item.time_spent,
            recent_answers=recent_answers,
        )
        is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
        new_record = AnswerRecord(
            session_id=payload.session_id,
            user_id=current_user.id,
            exam_no=item.exam_no,
            selected_option=item.selected_option,
            score=score,
            time_spent=item.time_spent,
            is_anomaly=is_anomaly_flag,
            ai_follow_up=detection_result.get("follow_up"),
            user_explanation=item.user_explanation if is_anomaly_flag else None,
        )
        db.add(new_record)
        recent_answers.append({
            "exam_no": item.exam_no,
            "selected_option": item.selected_option,
            "time_spent": item.time_spent,
            "score": score,
            "is_anomaly": is_anomaly_flag,
        })
        recent_answers = recent_answers[-5:]

    session.status = 'completed'
    from datetime import datetime
    session.finished_at = datetime.now()
    db.commit()

    try:
        trigger_completed_module_debates(db, payload.session_id, current_user.id, background_tasks)
    except Exception as e:
        print(f"批量提交后模块辩论检测失败: {e}")

    return {
        "status": "success",
        "message": "答题记录已正式提交",
        "saved_count": len(payload.answers),
        "session_id": payload.session_id,
    }


# --- 兼容旧接口：提交答案（现仅保留旧前端兼容） ---
@router.post("/submit", response_model=AnswerSubmitResponse)
async def submit_answer(payload: AnswerSubmitRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_question = db.query(Question).filter(Question.exam_no == payload.exam_no).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="题目不存在")

    current_score, detection_result = await analyze_answer(
        db_question,
        payload.selected_option,
        payload.time_spent,
        recent_answers=build_recent_answer_context(db, payload.session_id, current_user.id),
    )
    is_anomaly_flag = 1 if detection_result["status"] == "anomaly" else 0
    new_record = AnswerRecord(
        session_id=payload.session_id,
        user_id=current_user.id,
        exam_no=payload.exam_no,
        selected_option=payload.selected_option,
        score=current_score,
        time_spent=payload.time_spent,
        is_anomaly=is_anomaly_flag,
        ai_follow_up=detection_result.get("follow_up")
    )
    db.add(new_record)
    db.commit()

    try:
        trigger_completed_module_debates(db, payload.session_id, current_user.id, background_tasks)
    except Exception as e:
        print(f"模块完成检测出错: {e}")

    return AnswerSubmitResponse(
        status=detection_result["status"],
        message="记录已成功存入数据库",
        score=current_score,
        follow_up_question=detection_result.get("follow_up"),
        risk_score=detection_result.get("risk_score"),
        risk_reasons=detection_result.get("reasons", []),
    )


# --- 接口 3：提交补充解释 (保留兼容) ---
@router.post("/submit_explanation")
async def submit_explanation(payload: ExplanationSubmitRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # 找到刚才那条被拦截的异常记录
    record = db.query(AnswerRecord).filter(
        AnswerRecord.session_id == payload.session_id,
        AnswerRecord.user_id == current_user.id,
        AnswerRecord.exam_no == payload.exam_no,
        AnswerRecord.is_anomaly == 1
    ).order_by(AnswerRecord.created_at.desc()).first()

    if record:
        record.user_explanation = payload.text
        db.commit()
        return {"status": "success", "message": "解释已入库"}

    raise HTTPException(status_code=404, detail="找不到对应的异常记录")


@router.post("/finish")
async def finish_assessment(
        session_id: int,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
):
    """
    保留兼容：批量提交后可调用此接口标记完成。
    """
    session = ensure_session_owner(db, session_id, current_user.id)
    session.status = 'completed'
    from datetime import datetime
    session.finished_at = datetime.now()
    db.commit()

    return {
        "status": "success",
        "message": "测评已完成！请连接 /finish-stream 端点观看专家评审团的实时辩论并获取最终报告。"
    }


@router.get("/finish-stream")
async def finish_assessment_stream(session_id: int, token: str):
    """
    SSE 端点：实时推送多智能体辩论过程到前端。
    前端用 EventSource 连接此接口，通过 query param 传递 token。
    """
    from jose import JWTError, jwt as jose_jwt
    from app.core.config import settings as app_settings
    try:
        payload_data = jose_jwt.decode(token, app_settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload_data.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="无效的认证凭据")
    except JWTError:
        raise HTTPException(status_code=401, detail="无效的认证凭据")

    print(f"[finish-stream] 收到请求 - user_id: {user_id}, session_id: {session_id}")
    db = SessionLocal()

    try:
        prompt = build_debate_context(user_id, db, session_id)
        print(f"[finish-stream] 辩论上下文构建成功，长度: {len(prompt)}")
    except ValueError as e:
        print(f"[finish-stream] 构建辩论上下文失败: {e}")
        db.close()
        raise HTTPException(status_code=404, detail=str(e))

    message_queue = queue.Queue()

    # 在后台线程启动辩论
    print(f"[finish-stream] 启动辩论线程...")
    debate_thread = threading.Thread(
        target=run_debate_streaming,
        args=(prompt, message_queue),
        daemon=True
    )
    debate_thread.start()
    print(f"[finish-stream] 辩论线程已启动，ID: {debate_thread.ident}")

    async def event_generator():
        print(f"[finish-stream] 事件生成器开始，辩论线程存活状态: {debate_thread.is_alive()}")
        try:
            while True:
                try:
                    # 在线程池中执行阻塞的 queue.get，不阻塞事件循环
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: message_queue.get(block=True, timeout=2.0)
                    )
                    print(f"[finish-stream] 从队列收到消息: {msg.get('type', 'unknown')}")
                except queue.Empty:
                    # 超时但辩论还在进行，发送心跳保持连接
                    if debate_thread.is_alive():
                        print(f"[finish-stream] 队列为空，但辩论线程仍存活，发送心跳")
                        yield ": heartbeat\n\n"
                        continue
                    else:
                        # 辩论线程已结束，再尝试清空队列中剩余消息
                        print(f"[finish-stream] 辩论线程已结束，检查队列中剩余消息")
                        remaining_handled = False
                        while not message_queue.empty():
                            try:
                                msg = message_queue.get_nowait()
                                print(f"[finish-stream] 从队列取出剩余消息: {msg.get('type', 'unknown')}")
                                if msg["type"] == "message":
                                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                                    yield f"event: agent_message\ndata: {data}\n\n"
                                elif msg["type"] == "done":
                                    file_path = save_report_to_file(user_id, msg["content"])
                                    save_report_to_session(db, session_id, msg["content"], file_path)
                                    data = json.dumps({"report": msg["content"]}, ensure_ascii=False)
                                    yield f"event: debate_complete\ndata: {data}\n\n"
                                    remaining_handled = True
                                elif msg["type"] == "error":
                                    data = json.dumps({"message": msg["content"]}, ensure_ascii=False)
                                    yield f"event: error\ndata: {data}\n\n"
                                    remaining_handled = True
                            except queue.Empty:
                                break
                        if not remaining_handled:
                            # 队列真的为空且线程已死，发送兜底错误
                            print(f"[finish-stream] 队列为空且线程已死，发送兜底错误")
                            data = json.dumps({"message": "辩论服务异常终止，请检查后端日志"}, ensure_ascii=False)
                            yield f"event: error\ndata: {data}\n\n"
                        break

                if msg["type"] == "message":
                    print(f"[finish-stream] 发送agent_message事件: {msg.get('agent', 'unknown')}")
                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                    yield f"event: agent_message\ndata: {data}\n\n"

                elif msg["type"] == "done":
                    print(f"[finish-stream] 发送debate_complete事件，报告长度: {len(msg['content'])}")
                    # 保存报告到文件和数据库
                    file_path = save_report_to_file(user_id, msg["content"])
                    save_report_to_session(db, session_id, msg["content"], file_path)
                    data = json.dumps({"report": msg["content"]}, ensure_ascii=False)
                    yield f"event: debate_complete\ndata: {data}\n\n"
                    # 短暂延迟确保前端收到事件后再关闭流
                    await asyncio.sleep(0.5)
                    yield ": stream-end\n\n"
                    break

                elif msg["type"] == "error":
                    print(f"[finish-stream] 发送error事件: {msg['content']}")
                    data = json.dumps({"message": msg["content"]}, ensure_ascii=False)
                    yield f"event: error\ndata: {data}\n\n"
                    break
        finally:
            print(f"[finish-stream] 事件生成器结束，关闭数据库连接")
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


def save_report_to_session(db, session_id: int, report_content: str, file_path: str):
    """将报告内容存入会话记录"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if session:
        session.report_content = report_content
        session.report_file_path = file_path
        session.status = 'completed'
        db.commit()


# --- 接口：获取用户历史测评记录 ---
@router.get("/history")
async def get_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user_id = current_user.id
    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id,
        AssessmentSession.status == 'completed'
    ).order_by(AssessmentSession.started_at.desc()).all()

    # 批量查询所有会话的答题记录，避免 N+1
    session_ids = [s.id for s in sessions]
    all_history_records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id.in_(session_ids)
    ).all() if session_ids else []

    # 批量查询题目的维度信息
    all_exam_nos = list(set(r.exam_no for r in all_history_records))
    question_dim_map = {}
    if all_exam_nos:
        questions = db.query(Question.exam_no, Question.dimension_id).filter(
            Question.exam_no.in_(all_exam_nos)
        ).all()
        question_dim_map = {q.exam_no: q.dimension_id for q in questions}

    # 按 session_id 分组
    from collections import defaultdict
    records_by_session = defaultdict(list)
    for r in all_history_records:
        records_by_session[r.session_id].append(r)

    result = []
    for s in sessions:
        records = records_by_session.get(s.id, [])
        total_score = sum(float(r.score or 0) for r in records)
        anomaly_count = sum(1 for r in records if r.is_anomaly == 1)

        # 计算 ATMR 各维度百分比 (dimension_id: A=6, T=4, M=5, R=7)
        atmr_dim_map = {'A': '6', 'T': '4', 'M': '5', 'R': '7'}
        dim_scores = {}
        for m in ['A', 'T', 'M', 'R']:
            dim_records = [r for r in records if question_dim_map.get(r.exam_no) == atmr_dim_map[m]]
            if dim_records:
                dim_total = sum(float(r.score or 0) for r in dim_records)
                dim_scores[m] = round(dim_total, 1)
            else:
                dim_scores[m] = 0

        result.append({
            "session_id": s.id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "status": s.status,
            "question_count": len(records),
            "total_score": total_score,
            "anomaly_count": anomaly_count,
            "has_report": s.report_content is not None,
            "dim_scores": dim_scores,
        })

    return {"user_id": user_id, "sessions": result}


# --- 接口：获取某次测评的详细报告 ---
@router.get("/report/{session_id}")
async def get_report(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()

    # 维度映射
    module_map = {'6': 'A', '4': 'T', '5': 'M', '7': 'R'}
    module_names = {
        'A': '欣赏型 (Appreciation)',
        'T': '目标型 (Target)',
        'M': '包容型 (Magnanimity)',
        'R': '责任型 (Responsibility)',
    }

    # 批量查询题目，避免 N+1
    record_exam_nos = [r.exam_no for r in records]
    report_questions = db.query(Question).filter(
        Question.exam_no.in_(record_exam_nos)
    ).all() if record_exam_nos else []
    report_q_map = {q.exam_no: q for q in report_questions}

    # 按维度汇总分数，并收集证据链
    dimension_data = {m: {"scores": [], "records": []} for m in ['A', 'T', 'M', 'R']}

    answers = []
    for r in records:
        question = report_q_map.get(r.exam_no)
        dim_id = question.dimension_id if question else None
        module_key = module_map.get(dim_id) if dim_id else None

        answer_item = {
            "exam_no": r.exam_no,
            "question": question.content if question else "未知",
            "selected_option": r.selected_option,
            "score": float(r.score) if r.score is not None else 0,
            "time_spent": float(r.time_spent) if r.time_spent is not None else 0,
            "is_anomaly": r.is_anomaly,
            "ai_follow_up": r.ai_follow_up,
            "user_explanation": r.user_explanation,
            "dimension_id": dim_id,
            "module": module_key,
            "trait_label": question.trait_label if question else None,
            "is_reverse": question.is_reverse if question else False,
        }
        answers.append(answer_item)

        if module_key and module_key in dimension_data:
            dimension_data[module_key]["scores"].append(r.score)
            dimension_data[module_key]["records"].append(answer_item)

    # 计算各维度汇总
    dimension_summary = {}
    for m in ['A', 'T', 'M', 'R']:
        scores = dimension_data[m]["scores"]
        if scores:
            total = float(sum(float(s) for s in scores))
            avg = total / len(scores)
            max_possible = len(scores) * 5.0
            percentage = (total / max_possible * 100) if max_possible > 0 else 0
        else:
            total = avg = percentage = 0
            max_possible = 0

        dimension_summary[m] = {
            "name": module_names[m],
            "total_score": round(total, 2),
            "avg_score": round(avg, 2),
            "max_possible": max_possible,
            "percentage": round(percentage, 1),
            "question_count": len(scores),
            "anomaly_count": sum(1 for rec in dimension_data[m]["records"] if rec["is_anomaly"]),
            "evidence_records": dimension_data[m]["records"],
        }

    # 查询模块辩论结果
    module_debates = db.query(ModuleDebateResult).filter(
        ModuleDebateResult.session_id == session_id
    ).all()
    debate_results = {}
    for md in module_debates:
        debate_results[md.module] = md.result_content

    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "report": session.report_content,
        "answers": answers,
        "dimension_summary": dimension_summary,
        "module_debates": debate_results,
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    import os
    from app.models.question import ChatMessage

    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    report_file_path = session.report_file_path

    db.query(ModuleDebateResult).filter(ModuleDebateResult.session_id == session_id).delete()
    db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).delete()
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()

    if report_file_path and os.path.exists(report_file_path):
        try:
            os.remove(report_file_path)
        except Exception as e:
            print(f"删除报告文件失败: {e}")

    return {"status": "success", "message": "测评记录已删除"}