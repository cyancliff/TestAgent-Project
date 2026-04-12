# app/services/report_service.py

import asyncio
import json
import os
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.question import AnswerRecord, ModuleDebateResult, Question, SessionLocal


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def build_debate_context(user_id: str, db: Session, session_id: int = None) -> str:
    """从数据库查询用户作答记录，组装辩论 prompt，并注入 RAG 知识库证据"""
    query = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id)
    if session_id:
        query = query.filter(AnswerRecord.session_id == session_id)
    records = query.all()
    if not records:
        raise ValueError(f"用户 {user_id} 没有作答记录，无法生成报告。")

    # 批量查询所有相关题目，避免 N+1
    record_exam_nos = [r.exam_no for r in records]
    questions = db.query(Question).filter(Question.exam_no.in_(record_exam_nos)).all()
    question_map = {q.exam_no: q for q in questions}

    debate_context = []
    for r in records:
        question = question_map.get(r.exam_no)
        q_content = question.content if question else "未知题目"

        record_data = {
            "exam_no": r.exam_no,
            "question_content": q_content,
            "selected_option": r.selected_option,
            "score": r.score,
            "time_spent": r.time_spent,
            "is_anomaly": r.is_anomaly,
            "is_reverse": question.is_reverse if question else False,
            "trait_label": question.trait_label if question else None,
            "dimension_id": question.dimension_id if question else None,
        }
        if hasattr(r, "user_explanation") and r.user_explanation:
            record_data["user_explanation"] = r.user_explanation

        debate_context.append(record_data)

    context_str = json.dumps(debate_context, ensure_ascii=False, indent=2, cls=_DecimalEncoder)

    # 查询模块辩论结果
    module_query = db.query(ModuleDebateResult).filter(ModuleDebateResult.user_id == user_id)
    if session_id:
        module_query = module_query.filter(ModuleDebateResult.session_id == session_id)
    module_results = module_query.all()

    module_summary = ""
    if module_results:
        module_summary = "\n\n【模块辩论结果汇总】：\n"
        for mr in module_results:
            module_summary += f"模块 {mr.module}: {mr.result_content}\n"

    # RAG 检索：获取 ATMR 理论知识作为辩论证据
    rag_section = ""
    try:
        from app.services.rag_service import retrieve_evidence_for_debate

        # 计算各维度得分以构建更精准的查询
        dimension_scores = {}
        for record in debate_context:
            dim = record.get("dimension_id", "")
            if dim:
                dimension_scores[dim] = dimension_scores.get(dim, 0) + record.get("score", 0)

        user_traits = ", ".join(f"维度{k}={v:.1f}" for k, v in dimension_scores.items())

        # 同步执行异步 RAG 检索
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                evidence = pool.submit(asyncio.run, retrieve_evidence_for_debate(user_traits)).result(timeout=30)
        else:
            evidence = asyncio.run(retrieve_evidence_for_debate(user_traits))

        if evidence:
            rag_section = f"\n\n【ATMR 理论知识库参考】：\n{evidence}"
            print(f"[report_service] RAG 证据已注入辩论上下文，{len(evidence)} 字符")
    except Exception as e:
        print(f"[report_service] RAG 检索失败（不影响辩论）: {e}")

    return (
        f"以下是用户（ID: {user_id}）在 ATMR 心理测评中的作答记录（包含异常检测与用户的自我解释）。\n"
        f"请你们（正方、反方、裁决者）根据这些数据展开辩论，并生成最终的心理画像报告。\n"
        f"在分析中请引用 ATMR 理论知识库中的专业依据来支撑你的论点。\n"
        f"【作答数据】：\n{context_str}"
        f"{module_summary}"
        f"{rag_section}"
    )


def save_report_to_file(user_id: str, report_content: str) -> str:
    """将报告保存为 Markdown 文件，返回文件路径"""
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"reports/user_{user_id}_{timestamp}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# ATMR 心理测评深度画像报告 (用户: {user_id})\n\n")
        f.write(report_content)
    print(f"报告已保存至: {file_path}")
    return file_path
