"""AI interpretation generation for Big Five personality reports."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from textwrap import dedent

import httpx

from app.core.config import (
    build_deepseek_thinking_payload,
    get_deepseek_analysis_model,
    get_deepseek_analysis_thinking_mode,
    get_deepseek_api_key,
    get_deepseek_chat_completions_url,
)
from app.models.multimodal import BigFivePersonalityReport
from app.services.rag_service import retrieve_big_five_evidence, retrieve_big_five_knowledge

BIG_FIVE_DIMENSIONS = [
    ("openness", "开放性", "O"),
    ("conscientiousness", "尽责性", "C"),
    ("extraversion", "外向性", "E"),
    ("agreeableness", "宜人性", "A"),
    ("neuroticism", "神经质", "N"),
]


def _score_percent(value) -> str:
    try:
        return f"{float(value) * 100:.0f}/100"
    except (TypeError, ValueError):
        return "暂无"


def _score_band(value) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "未记录"
    if score >= 0.65:
        return "偏高"
    if score <= 0.35:
        return "偏低"
    return "中等"


def _build_scores_block(scores: dict | None) -> str:
    scores = scores or {}
    lines = []
    for key, label, short_name in BIG_FIVE_DIMENSIONS:
        lines.append(f"- {label}（{short_name}）: {_score_percent(scores.get(key))}（{_score_band(scores.get(key))}）")
    return "\n".join(lines)


def _rank_dimensions(scores: dict | None) -> dict[str, list[tuple[str, str, str, float]]]:
    scored_dimensions = []
    for key, label, short_name in BIG_FIVE_DIMENSIONS:
        try:
            value = float((scores or {}).get(key))
        except (TypeError, ValueError):
            continue
        scored_dimensions.append((key, label, short_name, value))

    return {
        "highest": sorted(scored_dimensions, key=lambda item: -item[3])[:2],
        "lowest": sorted(scored_dimensions, key=lambda item: item[3])[:2],
    }


def _dimension_query_terms(scores: dict | None) -> list[str]:
    scores = scores or {}
    terms = []
    for key, label, _ in BIG_FIVE_DIMENSIONS:
        terms.append(f"{_score_band(scores.get(key))}{label} {label} facet 行动建议")
    return terms


def _combination_query(scores: dict | None) -> str:
    ranked = _rank_dimensions(scores)
    terms = [f"{label}{_score_band(value)}" for _, label, _, value in ranked["highest"] + ranked["lowest"]]
    return "大五人格 维度组合 详细解读 " + " ".join(terms)


async def build_big_five_rag_evidence(scores: dict | None) -> str:
    """Collect richer evidence for ATMR-style Big Five report generation."""
    evidence_blocks = []
    base_evidence = await retrieve_big_five_evidence(scores, max_chars=4500)
    if base_evidence:
        evidence_blocks.append(f"【综合证据】\n{base_evidence}")

    combination_evidence = await retrieve_big_five_knowledge(
        _combination_query(scores),
        max_sections=4,
        max_chars=3000,
    )
    if combination_evidence:
        evidence_blocks.append(f"【维度组合证据】\n{combination_evidence}")

    for query in _dimension_query_terms(scores):
        dimension_evidence = await retrieve_big_five_knowledge(query, max_sections=2, max_chars=1400)
        if dimension_evidence:
            evidence_blocks.append(f"【{query}】\n{dimension_evidence}")

    boundary_evidence = await retrieve_big_five_knowledge(
        "视频多模态 大五人格报告 使用边界 风险措辞 非诊断",
        max_sections=3,
        max_chars=2200,
    )
    if boundary_evidence:
        evidence_blocks.append(f"【视频与非诊断边界】\n{boundary_evidence}")

    return "\n\n====\n\n".join(evidence_blocks)


def _build_ranked_summary(scores: dict | None) -> str:
    ranked = _rank_dimensions(scores)
    highest = "、".join(f"{label}（{_score_percent(value)}）" for _, label, _, value in ranked["highest"]) or "暂无"
    lowest = "、".join(f"{label}（{_score_percent(value)}）" for _, label, _, value in ranked["lowest"]) or "暂无"
    return f"相对更突出的维度：{highest}\n相对更需要谨慎解释的维度：{lowest}"


def _load_micro_expression_payload(report: BigFivePersonalityReport) -> dict | None:
    artifacts = report.artifacts or {}
    path_value = artifacts.get("micro_expression_feature_path")
    if not path_value:
        return None
    try:
        path = Path(path_value)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _build_micro_expression_block(report: BigFivePersonalityReport) -> str:
    payload = _load_micro_expression_payload(report)
    if not payload:
        return "【微表情线索】\n暂无可用微表情结果。"

    summary = payload.get("summary") or {}
    probabilities = payload.get("probabilities") or {}
    if not payload.get("success", False):
        errors = "；".join(str(error) for error in payload.get("errors", [])[:2]) or "微表情模块未返回可用结果"
        return f"【微表情线索】\n微表情模块未返回可用结果：{errors}。"

    label = summary.get("dominant_label_zh") or summary.get("dominant_expression") or "暂无"
    confidence = _score_percent(summary.get("confidence"))
    surprise = _score_percent(probabilities.get("surprise"))
    positive = _score_percent(probabilities.get("positive"))
    negative = _score_percent(probabilities.get("negative"))
    valence_hint = summary.get("valence_hint") or "unknown"
    return dedent(
        f"""\
        【微表情线索】
        - 主导微表情：{label}，置信度 {confidence}。
        - 三分类概率：惊讶 {surprise}，积极 {positive}，消极 {negative}。
        - 情绪倾向提示：{valence_hint}。
        - 解释边界：微表情只作为短时面部线索，不能直接代表稳定人格标签。"""
    )


def _build_interpretation_prompt(report: BigFivePersonalityReport, rag_evidence: str) -> str:
    source_filename = report.original_filename or "未记录"
    completed_at = report.completed_at.isoformat() if report.completed_at else "未记录"
    scores_block = _build_scores_block(report.scores)
    ranked_summary = _build_ranked_summary(report.scores)
    micro_expression_block = _build_micro_expression_block(report)

    return dedent(
        f"""\
        请基于用户的大五人格视频多模态结果，生成一份简洁、清晰、适合直接展示在报告页里的大五人格 AI 解读。

        【报告元信息】
        - 报告标题：{report.title or f"大五人格报告 #{report.id}"}
        - 视频文件：{source_filename}
        - 模型版本：{report.model_version}
        - 生成时间：{completed_at}
        - 结果性质：视频多模态人格线索，非医学诊断

        【五维得分】
        {scores_block}

        【维度排序辅助】
        {ranked_summary}

        {micro_expression_block}

        【大五人格 RAG 知识库证据】
        {rag_evidence or "暂无可用知识库片段，请基于五维得分进行谨慎、通用的解释。"}

        【强制输出格式】
        直接输出 Markdown。必须使用以下标题，顺序不能变：
        # 大五人格详细解读
        ## 01 报告摘要
        ## 02 综合人格画像
        ## 03 优势与潜在卡点
        ## 04 行动建议
        ## 05 使用边界

        【内容要求】
        1. 报告摘要写 3-5 条短要点，先讲整体轮廓，再讲最值得利用的优势和最需要留意的卡点。
        2. 综合人格画像用 2-4 段话串联解释：决策方式、互动风格、执行节奏、压力反应和成长空间。可以引用最突出的高低维度，但不要只罗列分数。
        3. 优势与潜在卡点分成“可能的优势”和“需要留意的地方”，每部分 2-4 条，避免把用户描述成固定标签。
        4. 行动建议给 4-6 条具体建议，可覆盖沟通、学习/工作节奏、压力管理、关系维护。建议必须可执行，不要空泛。
        5. 使用边界保持简短，说明视频结果受场景、情绪、拍摄状态影响；不替代临床评估；不应作为单一判断依据。
        6. 不要生成“五维得分速览”表格，不要生成“分维度报告”、Facet 长段落或“可用于对话的追问”。这些内容由前端固定模块和聊天页承接。
        7. 全文控制在 1200-1800 个中文字符左右，优先清晰和可读，不要写成论文。

        【写作边界】
        - 不要输出 JSON。
        - 不要出现“作为 AI”等措辞。
        - 不要把用户固定成标签。
        - 不要使用“你一定”“你完全”“你永远”等绝对化语言。
        - 不要做医学或临床诊断。
        - 语言要温暖、具体、专业，像一份可以直接给用户看的报告。
        """
    )


async def generate_big_five_interpretation(report: BigFivePersonalityReport) -> tuple[str, str]:
    """Generate a markdown interpretation and return (content, model)."""
    if not report.is_real_result or report.status != "completed" or not report.scores:
        raise ValueError("只有真实完成的大五人格报告才能生成 AI 详细解读")

    api_key = get_deepseek_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法生成 AI 详细解读")

    rag_evidence = await build_big_five_rag_evidence(report.scores)
    model = get_deepseek_analysis_model()
    prompt = _build_interpretation_prompt(report, rag_evidence)

    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0))
    try:
        response = await client.post(
            get_deepseek_chat_completions_url(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是专业、谨慎、温暖的大五人格报告撰写助手。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 2600,
                **build_deepseek_thinking_payload(get_deepseek_analysis_thinking_mode()),
            },
        )
        response.raise_for_status()
        result = response.json()
        content = (result["choices"][0]["message"].get("content") or "").strip()
    finally:
        try:
            await client.aclose()
        except RuntimeError:
            pass

    if not content:
        raise RuntimeError("AI 未返回有效的大五人格解读内容")
    return content.replace("TERMINATE", "").strip(), model


def generate_big_five_interpretation_sync(report: BigFivePersonalityReport) -> tuple[str, str]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        raise RuntimeError("不能在已运行的事件循环中同步生成大五人格解读")
    return asyncio.run(generate_big_five_interpretation(report))


def save_big_five_interpretation_to_file(report_id: int, content: str) -> str:
    os.makedirs("reports", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = Path("reports") / f"big_five_report_{report_id}_{timestamp}.md"
    file_path.write_text(content, encoding="utf-8")
    return str(file_path)
