"""
测评报告与 SSE 流式路由：多智能体辩论流、报告生成、历史记录、详细报告
"""

import os
import json
import queue
import threading
import asyncio
import time
from datetime import datetime
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.core.security import get_current_user
from app.core.constants import MODULE_DIM_MAP, MODULE_DISPLAY_NAMES, STAGE_NAMES
from app.core.constants import SCORE_LEVELS, WEIGHT_BONUS_SCORE, DIMENSION_MAX_SCORE
from app.models.assessment import AssessmentSession, AnswerRecord, ModuleDebateResult, Question
from app.models.chat import ChatSession
from app.models.user import User
from app.services.report_service import build_debate_context, save_report_to_file
from app.services.scoring import get_dimension_level, clamp_score, calculate_weight_bonus
from app.services.debate_manager import run_debate_streaming

# 评分标准说明（注入到模块辩论 prompt 中）
SCORING_STANDARD_TEXT = """
【评分标准说明】
本测评采用 1-5 分李克特量表（完全不符合=1分，比较不符合=2分，一般=3分，比较符合=4分，完全符合=5分）。
每个维度（A/T/M/R）各 10 道题，单项基础满分为 50 分（10题 × 5分），最低 10 分。
等级划分（三分法）：
  - 偏低（潜伏特质）：10-23 分 — 该维度特征表现不明显，很少调用该特质
  - 中等（情境特质）：24-37 分 — 具备基础特征，但非本能首选，特定环境下才展现
  - 偏高（显性主导特质）：38-50 分 — 该特质是典型行为模式和舒适区，表现强烈且稳定
前两题存在加权调节机制（+2分），请注意用户的实际得分可能包含加权成分。
"""


router = APIRouter()


def build_assessment_session_title(started_at: datetime | None, session_id: int | None = None) -> str:
    if started_at is not None:
        try:
            return started_at.astimezone().strftime("%Y.%m.%d %H:%M")
        except Exception:
            return started_at.strftime("%Y.%m.%d %H:%M")
    if session_id is not None:
        return f"测评 #{session_id}"
    return "未命名测评"


def _compute_history_dimension_scores(records, questions):
    """为历史记录计算维度分数（含等级和加权）"""
    q_map = {q.exam_no: q for q in questions}
    weight_bonus = calculate_weight_bonus(records, q_map)

    dim_scores = {}
    for m in ['A', 'T', 'M', 'R']:
        target_dim = MODULE_DIM_MAP[m]
        dim_records = [r for r in records if q_map.get(r.exam_no) and q_map[r.exam_no].dimension_id == target_dim]
        raw_total = sum(float(r.score or 0) for r in dim_records)
        weighted_total = raw_total + weight_bonus[m]
        clamped_total = clamp_score(weighted_total)
        level_info = get_dimension_level(clamped_total)

        dim_scores[m] = {
            "score": round(clamped_total, 1),
            "raw_score": round(raw_total, 1),
            "weighted_bonus": weight_bonus[m],
            "level": level_info["level"],
            "level_label": level_info["label"],
            "level_color": level_info["color"],
        }

    return dim_scores


def _run_debate_logic(session_id: int, user_id: int, module: str, result_holder: dict):
    """内部辩论逻辑（可被超时线程调用）"""
    from openai import AsyncOpenAI
    from app.services.rag_service import retrieve_evidence_for_debate

    db = SessionLocal()
    try:
        print(f"[模块辩论 {module}] 开始辩论分析...")

        target_dimension = MODULE_DIM_MAP.get(module)
        if not target_dimension:
            result_holder["error"] = "无效的模块"
            return

        records = db.query(AnswerRecord).filter(
            AnswerRecord.session_id == session_id,
            AnswerRecord.user_id == user_id,
        ).all()

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
                    "trait_label": question.trait_label,
                })

        if not module_records:
            result_holder["error"] = "未找到答题记录"
            return

        total_score = sum(r["score"] for r in module_records)
        avg_score = total_score / len(module_records) if module_records else 0
        anomaly_count = sum(1 for r in module_records if r["is_anomaly"])

        weight_bonus = calculate_weight_bonus(records, question_map)
        weighted_bonus = weight_bonus.get(module, 0)
        weighted_total_score = total_score + weighted_bonus
        clamped_score = clamp_score(weighted_total_score)
        level_info = get_dimension_level(clamped_score)

        module_data = {
            "module": module,
            "dimension_id": target_dimension,
            "question_count": len(module_records),
            "raw_total_score": total_score,
            "weighted_bonus": weighted_bonus,
            "weighted_total_score": weighted_total_score,
            "clamped_score": clamped_score,
            "average_score": round(avg_score, 2),
            "anomaly_count": anomaly_count,
            "level": level_info["level"],
            "level_label": level_info["label"],
            "records": module_records,
        }

        data_json = json.dumps(module_data, ensure_ascii=False, indent=2)

        # RAG 检索
        user_traits = f"模块{module}, 总分{total_score}, 平均分{avg_score:.2f}"
        try:
            rag_evidence = asyncio.run(retrieve_evidence_for_debate(user_traits, module))
            if not rag_evidence:
                rag_evidence = ""
        except Exception as e:
            rag_evidence = ""
            print(f"[模块辩论 {module}] RAG 检索失败: {e}")

        rag_context = ""
        if rag_evidence:
            rag_context = f"""

【ATMR 理论知识参考（来自知识库）】
{rag_evidence}

请结合以上理论知识进行分析，在分析中引用知识库中的理论依据。"""

        experts = {
            "proponent": {
                "name": "正方分析师",
                "prompt": f"""你是 ATMR 模块辩论中的正方分析师，负责基于完整材料给出建设性判断。

{SCORING_STANDARD_TEXT}
请完整阅读分数、异常标记、作答耗时、用户解释和知识库证据，并完成：
1. 明确该模块当前等级（偏低/中等/偏高）及主要依据，注意加权后的封顶分
2. 提炼用户在该模块的核心特质、稳定优势和可迁移潜力
3. 解释行为数据与作答内容之间的一致性，不要忽略异常后的自我解释
4. 对潜在风险保持审慎，但整体立场以“发掘优势与成长空间”为主
{rag_context}

数据：{data_json}

请用中文输出一段结构清晰、专业但简洁的分析（不超过450字）。"""
            },
            "opponent": {
                "name": "反方分析师",
                "prompt": f"""你是 ATMR 模块辩论中的反方分析师，负责基于完整材料给出审慎而批判的判断。

{SCORING_STANDARD_TEXT}
请完整阅读分数、异常标记、作答耗时、用户解释和知识库证据，并完成：
1. 明确该模块等级判断中最需要谨慎对待的依据与边界
2. 挖掘可能的情境依赖、测量误差、行为矛盾和替代解释
3. 说明高分或低分不应被直接浪漫化或绝对化的原因
4. 给出最值得继续观察或在综合层继续追问的风险点
{rag_context}

数据：{data_json}

请用中文输出一段结构清晰、专业但简洁的分析（不超过450字）。"""
            },
        }

        async def call_expert(expert_config):
            try:
                client = AsyncOpenAI(
                    api_key=os.environ.get("DEEPSEEK_API_KEY"),
                    base_url="https://api.deepseek.com/v1",
                )
                response = await client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": "你是ATMR心理测评系统的专家分析师。"},
                        {"role": "user", "content": expert_config["prompt"]},
                    ],
                    temperature=0.7,
                    max_tokens=800,
                )
                return {
                    "expert": expert_config["name"],
                    "content": response.choices[0].message.content,
                    "status": "success",
                }
            except Exception as e:
                return {
                    "expert": expert_config["name"],
                    "content": f"分析失败: {str(e)}",
                    "status": "error",
                }

        async def run_all():
            tasks = [call_expert(config) for config in experts.values()]
            return await asyncio.gather(*tasks, return_exceptions=True)

        expert_results = asyncio.run(run_all())

        # 裁判总结
        synthesis_prompt = f"""你是 ATMR 模块辩论中的裁判，请综合以下正反两方观点，生成 {module} 模块可供上层综合报告直接复用的裁判总结。

{SCORING_STANDARD_TEXT}
请输出一段简洁、专业、可复用的模块总结（不超过450字），必须包含：
1. 该模块的最终等级判断（偏低/中等/偏高）与关键依据，注意加权后得分口径
2. 核心特质判断：这个模块最稳定的表现是什么
3. 优势与风险：各给出最关键的一点到两点
4. 跨模块提示：一句话说明这个模块后续在综合层最应与哪些维度联动理解

输出要求：
- 直接输出总结正文，不要写标题
- 不要提及“正方”“反方”“两位分析师”等元信息

专家意见：
"""
        for result in expert_results:
            if isinstance(result, dict) and result.get("status") == "success":
                synthesis_prompt += f"\n【{result['expert']}】\n{result['content']}\n"

        try:
            client = AsyncOpenAI(
                api_key=os.environ.get("DEEPSEEK_API_KEY"),
                base_url="https://api.deepseek.com/v1",
            )
            synthesis_response = asyncio.run(client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是ATMR测评系统的主分析师。"},
                    {"role": "user", "content": synthesis_prompt},
                ],
                temperature=0.5,
                max_tokens=300,
            ))
            final_conclusion = synthesis_response.choices[0].message.content
        except Exception as e:
            final_conclusion = f"模块{module}综合评估生成失败: {str(e)}"

        clamped_score = clamp_score(weighted_total_score)
        level_info = get_dimension_level(clamped_score)

        result_content = f"""# 模块 {module} 专家辩论结果

## 数据摘要
- 题目数: {len(module_records)}
- 原始总得分: {total_score:.2f} / {DIMENSION_MAX_SCORE}
- 前两题加权: +{weighted_bonus}
- 加权后总得分: {weighted_total_score:.2f}（封顶后 {clamped_score:.2f}）
- 等级评定: {level_info['label']}（{level_info['level']}）
- 平均分: {avg_score:.2f}
- 异常标记: {anomaly_count} 次

## 专家分析
"""
        for result in expert_results:
            if isinstance(result, dict):
                result_content += f"\n### {result['expert']}\n{result.get('content', '无内容')}\n"

        result_content += f"\n## 裁判总结\n{final_conclusion}\n"

        # 先删除旧的辩论结果（覆盖）
        db.query(ModuleDebateResult).filter(
            ModuleDebateResult.session_id == session_id,
            ModuleDebateResult.module == module,
        ).delete()

        debate_result = ModuleDebateResult(
            session_id=session_id,
            user_id=user_id,
            module=module,
            result_content=result_content,
        )
        db.add(debate_result)
        db.commit()

        result_holder["success"] = True
        print(f"[模块辩论 {module}] 辩论完成，结果已保存")
        print(f"[模块辩论 {module}] 综合结论: {final_conclusion[:100]}...")

    except Exception as e:
        print(f"[模块辩论 {module}] 失败: {e}")
        import traceback
        traceback.print_exc()
        result_holder["error"] = str(e)
        db.rollback()
    finally:
        db.close()


def trigger_module_debate(session_id: int, user_id: int, module: str, timeout: int = 120):
    """后台执行模块级专家辩论（带超时保护）"""
    result_holder = {}
    debate_thread = threading.Thread(
        target=_run_debate_logic,
        args=(session_id, user_id, module, result_holder),
        daemon=True,
    )
    debate_thread.start()
    debate_thread.join(timeout=timeout)

    if debate_thread.is_alive():
        print(f"[模块辩论 {module}] 超时（{timeout}秒），辩论线程仍在运行")
        result_holder["error"] = "辩论超时"
    elif "error" in result_holder:
        print(f"[模块辩论 {module}] 异常: {result_holder['error']}")


def generate_report_in_background(session_id: int, user_id: int):
    """
    后台生成最终辩论报告
    此时所有模块辩论已在后台独立运行
    """
    db = SessionLocal()
    try:
        print(f"[后台报告] 开始为 session {session_id} 生成报告...")

        prompt = build_debate_context(str(user_id), db, session_id)
        print(f"[后台报告] 辩论上下文构建成功，长度: {len(prompt)}")

        message_queue = queue.Queue()
        debate_thread = threading.Thread(
            target=run_debate_streaming,
            args=(prompt, message_queue),
            daemon=True,
        )
        debate_thread.start()

        final_report = None
        timeout_seconds = 600
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                msg = message_queue.get(block=True, timeout=5.0)
                if msg["type"] == "done":
                    final_report = msg["content"]
                    break
                elif msg["type"] == "error":
                    print(f"[后台报告] 辩论出错: {msg['content']}")
                    break
            except queue.Empty:
                if not debate_thread.is_alive():
                    while not message_queue.empty():
                        try:
                            msg = message_queue.get_nowait()
                            if msg["type"] == "done":
                                final_report = msg["content"]
                                break
                        except queue.Empty:
                            break
                    break

        if final_report:
            file_path = save_report_to_file(str(user_id), final_report)
            session = db.query(AssessmentSession).filter(
                AssessmentSession.id == session_id
            ).first()
            if session:
                session.report_content = final_report
                session.report_file_path = file_path
                db.commit()
            print(f"[后台报告] session {session_id} 报告生成完成，长度: {len(final_report)}")
        else:
            elapsed = time.time() - start_time
            print(f"[后台报告] session {session_id} 报告生成失败或超时（耗时 {elapsed:.0f}s）")
            # 写入失败标记，防止前端永远显示"生成中"
            session = db.query(AssessmentSession).filter(
                AssessmentSession.id == session_id
            ).first()
            if session:
                session.report_content = "报告生成失败，请稍后重试。如果持续失败，请检查后端日志或 API 密钥配置。"
                session.report_file_path = None
                db.commit()

    except Exception as e:
        print(f"[后台报告] session {session_id} 生成失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.get("/finish-stream")
async def finish_assessment_stream(session_id: int, token: str):
    """SSE 端点：实时推送多智能体辩论过程到前端"""
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

    debate_thread = threading.Thread(
        target=run_debate_streaming,
        args=(prompt, message_queue),
        daemon=True,
    )
    debate_thread.start()

    async def event_generator():
        print(f"[finish-stream] 事件生成器开始，辩论线程存活状态: {debate_thread.is_alive()}")
        try:
            while True:
                try:
                    msg = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: message_queue.get(block=True, timeout=2.0),
                    )
                    print(f"[finish-stream] 从队列收到消息: {msg.get('type', 'unknown')}")
                except queue.Empty:
                    if debate_thread.is_alive():
                        yield ": heartbeat\n\n"
                        continue
                    else:
                        print(f"[finish-stream] 辩论线程已结束，检查队列中剩余消息")
                        remaining_handled = False
                        while not message_queue.empty():
                            try:
                                msg = message_queue.get_nowait()
                                if msg["type"] == "message":
                                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                                    yield f"event: agent_message\ndata: {data}\n\n"
                                elif msg["type"] == "done":
                                    file_path = save_report_to_file(user_id, msg["content"])
                                    session = db.query(AssessmentSession).filter(
                                        AssessmentSession.id == session_id
                                    ).first()
                                    if session:
                                        session.report_content = msg["content"]
                                        session.report_file_path = file_path
                                        db.commit()
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
                            data = json.dumps({"message": "辩论服务异常终止，请检查后端日志"}, ensure_ascii=False)
                            yield f"event: error\ndata: {data}\n\n"
                        break

                if msg["type"] == "message":
                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                    yield f"event: agent_message\ndata: {data}\n\n"
                elif msg["type"] == "done":
                    file_path = save_report_to_file(user_id, msg["content"])
                    session = db.query(AssessmentSession).filter(
                        AssessmentSession.id == session_id
                    ).first()
                    if session:
                        session.report_content = msg["content"]
                        session.report_file_path = file_path
                        db.commit()
                    data = json.dumps({"report": msg["content"]}, ensure_ascii=False)
                    yield f"event: debate_complete\ndata: {data}\n\n"
                    await asyncio.sleep(0.5)
                    yield ": stream-end\n\n"
                    break
                elif msg["type"] == "error":
                    data = json.dumps({"message": msg["content"]}, ensure_ascii=False)
                    yield f"event: error\ndata: {data}\n\n"
                    break
        finally:
            print(f"[finish-stream] 事件生成器结束，关闭数据库连接")
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history")
async def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户历史测评记录"""
    user_id = current_user.id
    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id,
        AssessmentSession.status.in_(['active', 'completed']),
    ).order_by(AssessmentSession.started_at.desc()).all()

    session_ids = [s.id for s in sessions]
    all_history_records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id.in_(session_ids)
    ).all() if session_ids else []

    all_exam_nos = list(set(r.exam_no for r in all_history_records))
    all_questions = db.query(Question).filter(
        Question.exam_no.in_(all_exam_nos)
    ).all() if all_exam_nos else []
    question_map = {q.exam_no: q for q in all_questions}

    records_by_session = defaultdict(list)
    for r in all_history_records:
        records_by_session[r.session_id].append(r)

    result = []
    for s in sessions:
        records = records_by_session.get(s.id, [])
        session_questions = [question_map[r.exam_no] for r in records if r.exam_no in question_map]
        total_score = sum(float(r.score or 0) for r in records)
        anomaly_count = sum(1 for r in records if r.is_anomaly == 1)

        dim_scores = _compute_history_dimension_scores(records, session_questions)

        result.append({
            "session_id": s.id,
            "title": s.title or build_assessment_session_title(s.started_at, s.id),
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "status": s.status,
            "current_stage": s.current_stage,
            "stage_display_name": STAGE_NAMES.get(s.current_stage, s.current_stage) if s.current_stage else None,
            "question_count": len(records),
            "total_score": total_score,
            "anomaly_count": anomaly_count,
            "has_report": s.status == 'completed' and s.report_content is not None,
            "report_generating": s.status == 'completed' and s.report_content is None,
            "dim_scores": dim_scores,
        })

    return {"user_id": user_id, "sessions": result}


@router.get("/report/{session_id}")
async def get_report(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取某次测评的详细报告"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    records = db.query(AnswerRecord).filter(AnswerRecord.session_id == session_id).all()

    module_map = {v: k for k, v in MODULE_DIM_MAP.items()}

    record_exam_nos = [r.exam_no for r in records]
    report_questions = db.query(Question).filter(
        Question.exam_no.in_(record_exam_nos)
    ).all() if record_exam_nos else []
    report_q_map = {q.exam_no: q for q in report_questions}

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

    # 计算各维度前两题加权分
    all_exam_nos_for_bonus = [r.exam_no for r in records]
    all_questions_for_bonus = db.query(Question).filter(Question.exam_no.in_(all_exam_nos_for_bonus)).all() if all_exam_nos_for_bonus else []
    q_map_for_bonus = {q.exam_no: q for q in all_questions_for_bonus}
    weight_bonus = calculate_weight_bonus(records, q_map_for_bonus)

    dimension_summary = {}
    for m in ['A', 'T', 'M', 'R']:
        scores = dimension_data[m]["scores"]
        if scores:
            raw_total = float(sum(float(s) for s in scores))
            weighted_total = raw_total + weight_bonus[m]
            clamped_total = clamp_score(weighted_total)
            avg = raw_total / len(scores)
            max_possible = len(scores) * 5.0
            percentage = (clamped_total / max_possible * 100) if max_possible > 0 else 0
        else:
            raw_total = avg = percentage = 0
            weighted_total = 0
            clamped_total = 0
            max_possible = 0

        level_info = get_dimension_level(clamped_total)

        dimension_summary[m] = {
            "name": MODULE_DISPLAY_NAMES[m],
            "raw_score": round(raw_total, 2),
            "total_score": round(clamped_total, 2),
            "weighted_score": round(weighted_total, 2),
            "weighted_bonus": weight_bonus[m],
            "avg_score": round(avg, 2),
            "max_possible": max_possible,
            "percentage": round(percentage, 1),
            "question_count": len(scores),
            "anomaly_count": sum(1 for rec in dimension_data[m]["records"] if rec["is_anomaly"]),
            "level": level_info["level"],
            "level_label": level_info["label"],
            "level_color": level_info["color"],
            "evidence_records": dimension_data[m]["records"],
        }

    module_debates = db.query(ModuleDebateResult).filter(
        ModuleDebateResult.session_id == session_id,
    ).all()
    debate_results = {md.module: md.result_content for md in module_debates}

    return {
        "session_id": session.id,
        "title": session.title or build_assessment_session_title(session.started_at, session.id),
        "user_id": session.user_id,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "report": session.report_content,
        "answers": answers,
        "dimension_summary": dimension_summary,
        "module_debates": debate_results,
    }
