# app/services/report_service.py

import asyncio
import json
import os
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.question import AnswerRecord, ModuleDebateResult, Question, SessionLocal


# 评分标准说明（注入到最终辩论 prompt 中）
SCORING_STANDARD_PROMPT = """
【ATMR 评分标准】
本测评采用 1-5 分李克特量表（完全不符合=1分，比较不符合=2分，一般=3分，比较符合=4分，完全符合=5分）。
4 大维度（A 欣赏型、T 目标型、M 包容型、R 责任型），每个维度 10 道题。
单项基础满分为 50 分（10题 × 5分），最低 10 分（10题 × 1分）。

等级划分（三分法）：
  - 偏低（潜伏特质）：10-23 分 — 该维度特征在测试者身上表现不明显，在日常工作或生活中很少调用该特质
  - 中等（情境特质）：24-37 分 — 测试者具备该维度的基础特征，但非本能首选，通常在特定环境或任务要求下才会展现
  - 偏高（显性主导特质）：38-50 分 — 该特质是测试者的典型行为模式和舒适区，表现极为强烈且稳定

前两题存在加权调节机制（破局与定调），根据第1题和第2题的组合对相应维度加 2 分：
  - AC 组合（做事快+选项C）→ A特质 +2分
  - BC 组合（靠分析+选项C）→ T特质 +2分
  - AD 组合（做事快+选项D）→ M特质 +2分
  - BD 组合（靠分析+选项D）→ R特质 +2分

注意：对外展示时维度得分以 50 分为封顶，内部计算可能因加权超过 50 分。
在撰写心理画像报告时，请明确标注各维度的等级（偏低/中等/偏高），并结合等级特征进行深入分析。
"""


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
        f"{SCORING_STANDARD_PROMPT}"
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
