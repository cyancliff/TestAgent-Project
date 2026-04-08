# app/services/rag_service.py
"""
RAG 服务模块 - 基于 PageIndex 的 ATMR 心理学知识库检索
提供知识库初始化、查询、证据检索等功能，供聊天和辩论系统使用。
"""

import os
import sys
import json
import httpx
from typing import Optional
from pathlib import Path

# 将 PageIndex 目录加入模块搜索路径
PAGEINDEX_DIR = Path(__file__).resolve().parent.parent.parent / "PageIndex"
if str(PAGEINDEX_DIR) not in sys.path:
    sys.path.insert(0, str(PAGEINDEX_DIR))

from pageindex import PageIndexClient


# ── 单例知识库客户端 ──────────────────────────────────────────────────────────

_client: Optional[PageIndexClient] = None
_doc_id: Optional[str] = None

WORKSPACE = PAGEINDEX_DIR / "results"
ATMR_DOC_NAME = "MinerU_markdown_ATMR_Longtext"


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
            f"未找到已索引的文档 '{ATMR_DOC_NAME}'，"
            f"请先运行 PageIndex 索引构建（workspace: {WORKSPACE}）"
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


def _find_relevant_sections(structure: list[dict], query: str) -> list[dict]:
    """
    根据查询关键词，从文档目录结构中找出相关章节。
    使用简单的关键词匹配（标题 + summary 匹配），返回相关节点列表。
    直接携带节点的 text 内容，避免二次查找。
    """
    query_lower = query.lower()
    # ATMR 相关关键词映射
    keyword_map = {
        "a特质": ["欣赏", "appreciation", "欣赏型"],
        "t特质": ["目标", "target", "目标型"],
        "m特质": ["包容", "magnanimity", "包容型"],
        "r特质": ["责任", "responsibility", "责任型"],
        "atmr": ["atmr", "特质", "性格", "测评"],
        "左右脑": ["左脑", "右脑", "左右脑", "理性", "感性"],
        "对冲": ["对冲", "冲突", "ar", "mt", "tm", "ra"],
        "均衡": ["均衡", "at", "ta", "mr", "rm"],
        "天赋": ["天赋", "优势", "潜力"],
        "弱势": ["弱势", "弱点", "风险"],
        "教育": ["教育", "培养", "父母", "家长", "亲子"],
        "职业": ["职业", "探索", "发展"],
    }

    # 展开查询关键词
    search_terms = set()
    search_terms.add(query_lower)
    # 拆分查询为词
    for word in query_lower.replace("，", " ").replace(",", " ").split():
        search_terms.add(word)
        for key, synonyms in keyword_map.items():
            if word in synonyms or word in key:
                search_terms.update(synonyms)

    relevant = []

    def _traverse(nodes, depth=0):
        for node in nodes:
            title = node.get("title", "").lower()
            summary = node.get("summary", "").lower()
            match_text = title + " " + summary
            score = sum(1 for term in search_terms if term in match_text)
            if score > 0:
                relevant.append({
                    "node_id": node.get("node_id"),
                    "title": node.get("title"),
                    "line_num": node.get("line_num"),
                    "summary": node.get("summary", ""),
                    "text": node.get("text", ""),  # 直接携带正文
                    "score": score,
                    "depth": depth,
                })
            if node.get("nodes"):
                _traverse(node["nodes"], depth + 1)

    _traverse(structure)
    # 按匹配得分降序排列
    relevant.sort(key=lambda x: (-x["score"], x["depth"]))
    return relevant


def _get_full_structure() -> list[dict]:
    """获取包含 text 字段的完整文档结构（从已加载的索引中）。"""
    client, doc_id = get_rag_client()
    # 确保完整数据已加载（包含 text 字段）
    if hasattr(client, '_ensure_doc_loaded'):
        client._ensure_doc_loaded(doc_id)
    doc = client.documents.get(doc_id, {})
    return doc.get('structure', [])


async def retrieve_knowledge(query: str, max_sections: int = 3, max_chars: int = 3000) -> str:
    """
    核心 RAG 检索函数：根据查询从 ATMR 知识库中检索相关知识。

    两阶段检索：
    1. 结构匹配 - 从文档目录树中找到相关章节
    2. 内容提取 - 直接从匹配节点中获取正文内容

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

    # 阶段1: 找出相关章节
    relevant_sections = _find_relevant_sections(structure, query)
    if not relevant_sections:
        print(f"[RAG] 未找到与 '{query}' 相关的章节")
        return ""

    # 阶段2: 从匹配节点直接提取 text 内容
    top_sections = relevant_sections[:max_sections]
    contents = []
    total_chars = 0

    for section in top_sections:
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
            contents.append(f"【{section['title']}】\n{content}")
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
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            response = await http_client.post(
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
    except Exception as e:
        print(f"[RAG] LLM 生成回答失败: {e}")
        answer = f"以下是从知识库中检索到的相关内容：\n\n{knowledge}"

    return {
        "answer": answer,
        "sources": [{"title": "ATMR 心理学知识库", "doc": ATMR_DOC_NAME}],
        "query": question,
    }
