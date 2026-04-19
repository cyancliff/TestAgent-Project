# app/services/report_service.py

import os
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.assessment import AnswerRecord, ModuleDebateResult
from app.core.constants import MODULES, MODULE_DISPLAY_NAMES


FINAL_SUMMARY_GUIDE = """
【综合层输入说明】
以下内容来自 A/T/M/R 四个模块各自的分层辩论裁判总结。
- 模块层已经整合了原始作答、异常追问、用户解释、评分等级与知识库证据。
- 综合层不要再假设自己能访问原始答题记录，也不要额外补充新的 RAG 证据。
- 请直接基于模块层裁判总结做跨模块综合判断，识别共振关系、结构性优势、潜在风险与发展建议。
"""


def _extract_markdown_section(content: str, heading: str) -> str:
    marker = f"## {heading}"
    start = content.find(marker)
    if start == -1:
        return ""

    start += len(marker)
    remaining = content[start:].lstrip()
    next_heading = remaining.find("\n## ")
    if next_heading != -1:
        remaining = remaining[:next_heading]
    return remaining.strip()


def _extract_module_summary(result_content: str) -> str:
    for heading in ("裁判总结", "综合结论"):
        section = _extract_markdown_section(result_content, heading)
        if section:
            return section
    return result_content.strip()


def _wait_for_module_results(user_id: str, db: Session, session_id: int | None, timeout_seconds: int = 120) -> list[ModuleDebateResult]:
    deadline = time.time() + timeout_seconds

    while True:
        db.expire_all()
        query = db.query(ModuleDebateResult).filter(ModuleDebateResult.user_id == user_id)
        if session_id:
            query = query.filter(ModuleDebateResult.session_id == session_id)

        module_results = query.all()
        module_map = {mr.module: mr for mr in module_results}
        if all(module in module_map for module in MODULES):
            return [module_map[module] for module in MODULES]

        if time.time() >= deadline:
            return [module_map[module] for module in MODULES if module in module_map]

        time.sleep(2.0)


def build_debate_context(user_id: str, db: Session, session_id: int = None) -> str:
    """从数据库查询模块层裁判总结，组装最终综合辩论 prompt。"""
    record_query = db.query(AnswerRecord).filter(AnswerRecord.user_id == user_id)
    if session_id:
        record_query = record_query.filter(AnswerRecord.session_id == session_id)
    if not record_query.first():
        raise ValueError(f"用户 {user_id} 没有作答记录，无法生成报告。")

    module_results = _wait_for_module_results(user_id, db, session_id)
    if not module_results:
        raise ValueError(f"用户 {user_id} 暂无可用的模块辩论结果，无法生成报告。")

    module_map = {mr.module: mr for mr in module_results}
    missing_modules = [module for module in MODULES if module not in module_map]
    if missing_modules:
        print(f"[report_service] 构建综合辩论上下文时缺少模块结果: {', '.join(missing_modules)}")

    module_summary = "\n\n【模块层裁判总结】\n"
    for module in MODULES:
        result = module_map.get(module)
        if not result:
            continue
        summary = _extract_module_summary(result.result_content)
        module_summary += f"\n### 模块 {module}（{MODULE_DISPLAY_NAMES[module]}）\n{summary}\n"

    if missing_modules:
        module_summary += f"\n【缺失模块】{', '.join(missing_modules)}\n"

    return (
        f"以下是用户（ID: {user_id}）在 ATMR 心理测评四个模块中的分层辩论裁判总结。\n"
        f"请你们（正方、反方、裁判）仅基于这些模块层总结展开综合辩论，并生成最终的心理画像报告。\n"
        f"{FINAL_SUMMARY_GUIDE}"
        f"{module_summary}"
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
