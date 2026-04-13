# app/services/rag_service.py
"""
RAG 服务模块 - 基于 PageIndex 的 ATMR 心理学知识库检索
提供知识库初始化、查询、证据检索等功能，供聊天和辩论系统使用。
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx

# 将 PageIndex 目录加入模块搜索路径
PAGEINDEX_DIR = Path(__file__).resolve().parent.parent.parent / "PageIndex"
if str(PAGEINDEX_DIR) not in sys.path:
    sys.path.insert(0, str(PAGEINDEX_DIR))

from pageindex import PageIndexClient  # noqa: E402

# ── 单例知识库客户端 ──────────────────────────────────────────────────────────

_client: PageIndexClient | None = None
_doc_id: str | None = None

WORKSPACE = PAGEINDEX_DIR / "results"
ATMR_DOC_NAME = "MinerU_markdown_ATMR_Longtext"

# LLM 语义评分检索配置
RELEVANCE_THRESHOLD = 0.3  # 相关性阈值，低于此分数视为不相关
MAX_SECTIONS_TO_SCORE = 30  # 最多评分的章节数（先粗筛后精排）


def get_rag_client() -> tuple[PageIndexClient, str]:
    """
    获取或初始化 RAG 客户端单例。
    返回 (client, doc_id)。
    """
    global _client, _doc_id

    if _client is not None and _doc_id is not None:
        return _client, _doc_id

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 DEEPSEEK_API_KEY 环境变量，无法初始化 RAG 服务")

    # 初始化 PageIndexClient，加载已有 workspace（已构建的索引）
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    _client = PageIndexClient(
        api_key=api_key,
        model="deepseek/deepseek-chat",
        retrieve_model="deepseek/deepseek-chat",
        workspace=str(WORKSPACE),
    )

    # 从已有索引中找到 ATMR 文档
    for did, doc in _client.documents.items():
        if doc.get("doc_name") == ATMR_DOC_NAME:
            _doc_id = did
            break

    if _doc_id is None:
        raise RuntimeError(
            f"未找到已索引的文档 '{ATMR_DOC_NAME}'，请先运行 PageIndex 索引构建（workspace: {WORKSPACE}）"
        )

    print(f"[RAG] 知识库已加载: doc_id={_doc_id}, 文档={ATMR_DOC_NAME}")
    return _client, _doc_id


# ── 核心检索功能 ──────────────────────────────────────────────────────────────


def get_document_structure() -> dict:
    """获取文档目录结构（不含正文）。"""
    client, doc_id = get_rag_client()
    return json.loads(client.get_document_structure(doc_id))


def get_page_content(pages: str) -> list[dict]:
    """获取指定行号范围的内容。pages 格式: '5-7', '3,8', '12'。"""
    client, doc_id = get_rag_client()
    return json.loads(client.get_page_content(doc_id, pages))


def _collect_all_sections(structure: list[dict]) -> list[dict]:
    """将树形结构展平为一维列表，便于检索。"""
    sections = []

    def _traverse(nodes, depth=0):
        for node in nodes:
            sections.append(
                {
                    "node_id": node.get("node_id"),
                    "title": node.get("title", ""),
                    "line_num": node.get("line_num"),
                    "summary": node.get("summary", ""),
                    "text": node.get("text", ""),
                    "depth": depth,
                }
            )
            if node.get("nodes"):
                _traverse(node["nodes"], depth + 1)

    _traverse(structure)
    return sections


def _keyword_coarse_filter(sections: list[dict], query: str) -> list[dict]:
    """关键词粗筛：快速过滤掉明显不相关的章节，缩小 LLM 评分范围。"""
    query_lower = query.lower()
    query_words = set(query_lower.replace("，", " ").replace(",", " ").split())

    # 保留原有的关键词映射作为粗筛辅助
    keyword_map = {
        "欣赏": ["欣赏", "appreciation"],
        "目标": ["目标", "target"],
        "包容": ["包容", "magnanimity"],
        "责任": ["责任", "responsibility"],
        "atmr": ["atmr", "特质", "性格", "测评"],
        "左右脑": ["左脑", "右脑", "左右脑", "理性", "感性"],
        "对冲": ["对冲", "冲突", "ar", "mt", "tm", "ra"],
        "均衡": ["均衡", "at", "ta", "mr", "rm"],
        "天赋": ["天赋", "优势", "潜力"],
        "弱势": ["弱势", "弱点", "风险"],
        "教育": ["教育", "培养", "父母", "家长", "亲子"],
        "职业": ["职业", "探索", "发展"],
    }
    all_keywords = query_words.copy()
    for word in query_words:
        for key, synonyms in keyword_map.items():
            if word in synonyms or word in key:
                all_keywords.update(synonyms)

    filtered = []
    for section in sections:
        match_text = (section["title"] + " " + section["summary"]).lower()
        if any(kw in match_text for kw in all_keywords):
            filtered.append(section)

    return filtered if filtered else sections[:20]  # 如果粗筛无结果，返回前 20 个章节兜底


async def _llm_score_relevance(query: str, sections: list[dict]) -> list[dict]:
    """使用 LLM 对章节进行语义相关性评分。

    将所有章节标题和摘要打包成一次请求，让 LLM 批量评分，减少 API 调用次数。
    返回格式: [{"section": section_dict, "score": float, "reason": str}, ...]
    """
    # 构建批量评分 prompt
    sections_text = "\n".join(
        f"[{i}] {s['title']} - {s['summary'][:100]}" for i, s in enumerate(sections)
    )

    prompt = f"""你是一个专业的心理学文档检索助手。请基于用户的查询问题，对以下文档章节标题和摘要进行语义相关性评分。

【查询问题】
{query}

【待评分章节】（格式: [序号] 标题 - 摘要）
{sections_text}

【评分要求】
1. 对每个章节给出 0.0 到 1.0 的相关性评分
2. 评分标准:
   - 0.8-1.0: 高度相关，直接回应查询核心
   - 0.5-0.8: 中度相关，包含部分相关信息
   - 0.3-0.5: 低度相关，仅有间接关联
   - 0.0-0.3: 几乎不相关
3. 用一行简短中文说明评分理由

【输出格式】
请严格按以下 JSON 格式输出，不要包含其他内容:
{{"scores": [{{"index": 序号, "score": 分数, "reason": "理由"}}, ...]}}
"""

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        # 无 API key 时回退到关键词评分
        return _keyword_score_fallback(query, sections)

    try:
        client = httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # 解析 JSON 响应
            scores_data = json.loads(content)
            scores_list = scores_data.get("scores", [])

            scored_sections = []
            for item in scores_list:
                idx = item.get("index", -1)
                if 0 <= idx < len(sections):
                    scored_sections.append(
                        {
                            "section": sections[idx],
                            "score": float(item.get("score", 0)),
                            "reason": item.get("reason", ""),
                        }
                    )

            return scored_sections
        finally:
            try:
                await client.aclose()
            except RuntimeError:
                pass  # Windows ProactorEventLoop: 事件循环已关闭时 aclose 会报错，连接已断开，可安全忽略

    except Exception as e:
        print(f"[RAG] LLM 语义评分失败: {e}，回退到关键词评分")
        return _keyword_score_fallback(query, sections)


def _keyword_score_fallback(query: str, sections: list[dict]) -> list[dict]:
    """关键词评分兜底方案：当 LLM 不可用时使用。"""
    query_lower = query.lower()
    query_words = set(query_lower.replace("，", " ").replace(",", " ").split())

    scored = []
    for section in sections:
        match_text = (section["title"] + " " + section["summary"]).lower()
        match_count = sum(1 for w in query_words if w in match_text)
        score = match_count / max(len(query_words), 1)
        scored.append({"section": section, "score": score, "reason": "关键词匹配"})

    return scored


def _get_full_structure() -> list[dict]:
    """获取包含 text 字段的完整文档结构（从已加载的索引中）。"""
    client, doc_id = get_rag_client()
    # 确保完整数据已加载（包含 text 字段）
    if hasattr(client, "_ensure_doc_loaded"):
        client._ensure_doc_loaded(doc_id)
    doc = client.documents.get(doc_id, {})
    return doc.get("structure", [])


async def retrieve_knowledge(query: str, max_sections: int = 3, max_chars: int = 3000) -> str:
    """
    核心 RAG 检索函数：根据查询从 ATMR 知识库中检索相关知识。

    三阶段检索：
    1. 关键词粗筛 - 快速过滤明显不相关的章节
    2. LLM 语义评分 - 对候选章节进行语义相关性评分
    3. 内容提取 - 从高评分节点中提取正文内容

    Args:
        query: 查询问题
        max_sections: 最多返回的章节数
        max_chars: 返回内容的最大字符数

    Returns:
        检索到的知识文本，可直接注入到 prompt 中
    """
    try:
        # 获取带 text 字段的完整结构
        structure = _get_full_structure()
        if not structure:
            # 回退到不含 text 的结构
            structure = get_document_structure()
    except Exception as e:
        print(f"[RAG] 获取文档结构失败: {e}")
        return ""

    # 阶段1: 关键词粗筛，缩小候选范围
    all_sections = _collect_all_sections(structure)
    candidate_sections = _keyword_coarse_filter(all_sections, query)

    # 阶段2: LLM 语义评分精排
    scored_sections = await _llm_score_relevance(query, candidate_sections[:MAX_SECTIONS_TO_SCORE])

    # 按 LLM 评分降序排列，过滤低于阈值的章节
    scored_sections.sort(key=lambda x: -x["score"])
    relevant_sections = [
        s for s in scored_sections if s["score"] >= RELEVANCE_THRESHOLD
    ]

    if not relevant_sections:
        print(f"[RAG] 未找到与 '{query}' 相关的章节（所有章节相关性均低于阈值 {RELEVANCE_THRESHOLD}）")
        return ""

    # 阶段3: 从高评分章节中提取内容
    top_sections = relevant_sections[:max_sections]
    contents = []
    total_chars = 0

    for item in top_sections:
        section = item["section"]
        score = item["score"]

        # 优先使用节点自带的 text 字段
        content = section.get("text", "").strip()

        if not content:
            # 回退到 get_page_content
            line_num = section.get("line_num")
            if not line_num:
                continue
            try:
                end_line = line_num + 50
                pages_content = get_page_content(f"{line_num}-{end_line}")
                for page in pages_content:
                    content += page.get("content", "").strip() + "\n"
                content = content.strip()
            except Exception as e:
                print(f"[RAG] 获取章节 '{section['title']}' 内容失败: {e}")
                continue

        if not content:
            continue

        # 如果单个章节内容超过剩余容量，截断到合理边界
        remaining_budget = max_chars - total_chars
        if len(content) > remaining_budget:
            content = content[:remaining_budget].rsplit("\n", 1)[0]

        if content:
            contents.append(f"【{section['title']}】（相关性: {score:.2f}）\n{content}")
            total_chars += len(content)

    if not contents:
        return ""

    result = "\n\n---\n\n".join(contents)
    print(f"[RAG] 检索完成: 查询='{query}', 返回 {len(contents)} 个章节, {len(result)} 字符")
    return result


async def retrieve_evidence_for_debate(user_traits: str, module: str = "") -> str:
    """
    为辩论系统检索知识库证据。

    Args:
        user_traits: 用户特质描述（如 "A特质得分32, T特质得分28"）
        module: 当前辩论的模块（A/T/M/R）

    Returns:
        相关的 ATMR 理论知识，作为辩论证据
    """
    # 构建面向辩论的查询
    queries = []
    if module:
        module_names = {
            "A": "欣赏型 Appreciation",
            "T": "目标型 Target",
            "M": "包容型 Magnanimity",
            "R": "责任型 Responsibility",
        }
        module_name = module_names.get(module.upper(), module)
        queries.append(f"{module_name} 特质 天赋优势 弱势")
    queries.append(f"ATMR 特质组合 {user_traits}")

    all_evidence = []
    for q in queries:
        evidence = await retrieve_knowledge(q, max_sections=2, max_chars=1500)
        if evidence:
            all_evidence.append(evidence)

    return "\n\n===\n\n".join(all_evidence) if all_evidence else ""


async def query_knowledge_base(question: str) -> dict:
    """
    RAG 问答接口：回答关于 ATMR 心理学的问题。
    用于独立的 RAG API 端点。

    Returns:
        {"answer": str, "sources": list[dict], "query": str}
    """
    knowledge = await retrieve_knowledge(question, max_sections=5, max_chars=5000)

    if not knowledge:
        return {
            "answer": "抱歉，在知识库中未找到与您问题相关的内容。",
            "sources": [],
            "query": question,
        }

    # 使用 LLM 基于检索到的知识生成回答
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {
            "answer": knowledge,
            "sources": [],
            "query": question,
        }

    prompt = f"""你是一位 ATMR 心理学专家。请基于以下知识库内容，回答用户的问题。
回答要求：
1. 仅基于提供的知识库内容回答，不要编造
2. 如果知识库内容不足以完整回答，请说明
3. 用专业但易懂的语言回答

【知识库内容】
{knowledge}

【用户问题】
{question}"""

    try:
        client = httpx.AsyncClient(timeout=60.0)
        try:
            response = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            response.raise_for_status()
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
        finally:
            try:
                await client.aclose()
            except RuntimeError:
                pass  # Windows ProactorEventLoop 已知问题，可安全忽略
    except Exception as e:
        print(f"[RAG] LLM 生成回答失败: {e}")
        answer = f"以下是从知识库中检索到的相关内容：\n\n{knowledge}"

    return {
        "answer": answer,
        "sources": [{"title": "ATMR 心理学知识库", "doc": ATMR_DOC_NAME}],
        "query": question,
    }
