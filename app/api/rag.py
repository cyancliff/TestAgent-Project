# app/api/rag.py
"""
RAG 知识库查询 API 端点
提供 ATMR 心理学知识库的独立查询接口。
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import get_current_user
from app.services.rag_service import (
    BIG_FIVE_DOC_NAME,
    get_big_five_document_structure,
    get_big_five_rag_client,
    get_document_structure,
    query_big_five_knowledge_base,
    query_knowledge_base,
    retrieve_big_five_knowledge,
    retrieve_knowledge,
)

router = APIRouter(dependencies=[Depends(get_current_user)])


class RAGQueryRequest(BaseModel):
    question: str


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    query: str


class RAGRetrieveRequest(BaseModel):
    query: str
    max_sections: int = 3
    max_chars: int = 3000


def _count_structure_sections(sections: list[dict]) -> int:
    total = 0
    for section in sections:
        total += 1
        children = section.get("nodes") or []
        if children:
            total += _count_structure_sections(children)
    return total


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(payload: RAGQueryRequest):
    """
    RAG 问答接口：基于 ATMR 知识库回答心理学相关问题。
    系统会先检索知识库，再结合 LLM 生成专业回答。
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        result = await query_knowledge_base(payload.question)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/retrieve")
async def rag_retrieve(payload: RAGRetrieveRequest):
    """
    RAG 检索接口：从 ATMR 知识库中检索相关内容片段（不经过 LLM 生成）。
    适用于需要原始知识库内容的场景。
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")

    try:
        content = await retrieve_knowledge(
            payload.query,
            max_sections=payload.max_sections,
            max_chars=payload.max_chars,
        )
        return {
            "query": payload.query,
            "content": content,
            "has_results": bool(content),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/structure")
async def rag_structure():
    """
    获取知识库文档的目录结构。
    用于前端展示知识库概览或调试。
    """
    try:
        structure = get_document_structure()
        return {"structure": structure}
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/status")
async def rag_status():
    """
    检查 RAG 服务状态。
    """
    try:
        from app.services.rag_service import get_rag_client

        client, doc_id = get_rag_client()
        doc_meta = client.get_document(doc_id)
        import json

        return {
            "status": "ok",
            "doc_id": doc_id,
            "document": json.loads(doc_meta),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@router.post("/big-five/query", response_model=RAGQueryResponse)
async def big_five_rag_query(payload: RAGQueryRequest):
    """Query the Big Five personality knowledge base."""
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")

    try:
        result = await query_big_five_knowledge_base(payload.question)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/big-five/retrieve")
async def big_five_rag_retrieve(payload: RAGRetrieveRequest):
    """Retrieve raw Big Five personality knowledge snippets."""
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="查询不能为空")

    try:
        content = await retrieve_big_five_knowledge(
            payload.query,
            max_sections=payload.max_sections,
            max_chars=payload.max_chars,
        )
        return {
            "query": payload.query,
            "content": content,
            "has_results": bool(content),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/big-five/status")
async def big_five_rag_status():
    """Check whether the Big Five knowledge base is available."""
    try:
        client, doc_id = get_big_five_rag_client()
        doc_meta = client.get_document(doc_id)
        import json

        structure = get_big_five_document_structure()
        sections = structure.get("structure", structure) if isinstance(structure, dict) else structure
        return {
            "status": "ok" if sections else "empty",
            "doc": BIG_FIVE_DOC_NAME,
            "doc_id": doc_id,
            "document": json.loads(doc_meta),
            "fallback": False,
            "section_count": _count_structure_sections(sections),
        }
    except Exception as e:
        structure = get_big_five_document_structure()
        sections = structure.get("structure", []) if isinstance(structure, dict) else []
        return {
            "status": "ok" if sections else "error",
            "doc": BIG_FIVE_DOC_NAME,
            "doc_id": None,
            "fallback": True,
            "section_count": _count_structure_sections(sections),
            "message": str(e),
        }
