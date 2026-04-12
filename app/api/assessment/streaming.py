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
from app.core.constants import MODULE_DIM_MAP, MODULE_DISPLAY_NAMES
from app.models.question import (
    AssessmentSession, AnswerRecord, ModuleDebateResult, Question, User, ChatSession,
)
from app.services.report_service import build_debate_context, save_report_to_file
from agent.debate_manager import run_debate_streaming

router = APIRouter()


def trigger_module_debate(session_id: int, user_id: int, module: str):
    """同步执行模块级专家辩论（用于 background_tasks 调用）"""
    import asyncio
    from openai import AsyncOpenAI
    from app.services.rag_service import retrieve_evidence_for_debate

    db = SessionLocal()
    try:
        print(f"[模块辩论 {module}] 开始异步辩论分析...")

        target_dimension = MODULE_DIM_MAP.get(module)

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
            print(f"[模块辩论 {module}] 未找到答题记录")
            return

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
            "records": module_records,
        }

        data_json = json.dumps(module_data, ensure_ascii=False, indent=2)

        # RAG 检索
        user_traits = f"模块{module}, 总分{total_score}, 平均分{avg_score:.2f}"
        try:
            rag_evidence = asyncio.run(retrieve_evidence_for_debate(user_traits, module))
            if rag_evidence:
                print(f"[模块辩论 {module}] RAG 检索到 {len(rag_evidence)} 字符的证据")
            else:
                rag_evidence = ""
                print(f"[模块辩论 {module}] RAG 未检索到相关证据")
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

        # 综合结论
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
            result_content=result_content,
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


# 保持旧函数名兼容
trigger_module_debate_async = trigger_module_debate


def save_report_to_session(db: Session, session_id: int, report_content: str, file_path: str):
    """将报告内容存入会话记录"""
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if session:
        session.report_content = report_content
        session.report_file_path = file_path
        session.status = 'completed'
        db.commit()


def generate_report_in_background(session_id: int, user_id: int):
    """后台生成最终辩论报告，无需前端 SSE 连接"""
    db = SessionLocal()
    try:
        print(f"[后台报告] 开始为 session {session_id} 生成报告...")

        time.sleep(3)  # 等待模块辩论启动

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
        timeout_seconds = 300
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
            save_report_to_session(db, session_id, final_report, file_path)
            print(f"[后台报告] session {session_id} 报告生成完成，长度: {len(final_report)}")
        else:
            print(f"[后台报告] session {session_id} 报告生成失败或超时")

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
                            data = json.dumps({"message": "辩论服务异常终止，请检查后端日志"}, ensure_ascii=False)
                            yield f"event: error\ndata: {data}\n\n"
                        break

                if msg["type"] == "message":
                    data = json.dumps({"agent": msg["agent"], "content": msg["content"]}, ensure_ascii=False)
                    yield f"event: agent_message\ndata: {data}\n\n"
                elif msg["type"] == "done":
                    file_path = save_report_to_file(user_id, msg["content"])
                    save_report_to_session(db, session_id, msg["content"], file_path)
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
        AssessmentSession.status == 'completed',
    ).order_by(AssessmentSession.started_at.desc()).all()

    session_ids = [s.id for s in sessions]
    all_history_records = db.query(AnswerRecord).filter(
        AnswerRecord.session_id.in_(session_ids)
    ).all() if session_ids else []

    all_exam_nos = list(set(r.exam_no for r in all_history_records))
    question_dim_map = {}
    if all_exam_nos:
        questions = db.query(Question.exam_no, Question.dimension_id).filter(
            Question.exam_no.in_(all_exam_nos)
        ).all()
        question_dim_map = {q.exam_no: q.dimension_id for q in questions}

    records_by_session = defaultdict(list)
    for r in all_history_records:
        records_by_session[r.session_id].append(r)

    result = []
    for s in sessions:
        records = records_by_session.get(s.id, [])
        total_score = sum(float(r.score or 0) for r in records)
        anomaly_count = sum(1 for r in records if r.is_anomaly == 1)

        dim_scores = {}
        for m in ['A', 'T', 'M', 'R']:
            dim_records = [r for r in records if question_dim_map.get(r.exam_no) == MODULE_DIM_MAP[m]]
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
            "report_generating": s.report_content is None and s.status == 'completed',
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
            "name": MODULE_DISPLAY_NAMES[m],
            "total_score": round(total, 2),
            "avg_score": round(avg, 2),
            "max_possible": max_possible,
            "percentage": round(percentage, 1),
            "question_count": len(scores),
            "anomaly_count": sum(1 for rec in dimension_data[m]["records"] if rec["is_anomaly"]),
            "evidence_records": dimension_data[m]["records"],
        }

    module_debates = db.query(ModuleDebateResult).filter(
        ModuleDebateResult.session_id == session_id,
    ).all()
    debate_results = {md.module: md.result_content for md in module_debates}

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
