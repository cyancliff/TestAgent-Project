# app/api/rag.py
"""
RAG 知识库查询 API 端点
提供 ATMR 心理学知识库的独立查询接口。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.rag_service import (
    query_knowledge_base,
    retrieve_knowledge,
    get_document_structure,
)

router = APIRouter()


class RAGQueryRequest(BaseModel):
    question: str


class RAGQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    query: str


class RAGRetrieveRequest(BaseModel):
    query: str
    max_sections: int = 3
    max_chars: int = 3000


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
