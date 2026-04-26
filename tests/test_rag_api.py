from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/v1/rag/query", {"question": "ATMR是什么"}),
        ("post", "/api/v1/rag/retrieve", {"query": "ATMR"}),
        ("post", "/api/v1/rag/big-five/query", {"question": "开放性是什么"}),
        ("post", "/api/v1/rag/big-five/retrieve", {"query": "开放性"}),
        ("get", "/api/v1/rag/structure", None),
        ("get", "/api/v1/rag/status", None),
        ("get", "/api/v1/rag/big-five/status", None),
    ],
)
def test_rag_endpoints_require_authentication(method, path, payload):
    client = TestClient(app)

    if method == "post":
        response = client.post(path, json=payload)
    else:
        response = client.get(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_rag_query_succeeds_with_authenticated_user(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")

    async def fake_query_knowledge_base(question: str) -> dict:
        return {
            "answer": f"mocked answer for {question}",
            "sources": [{"title": "Mock Source"}],
            "query": question,
        }

    monkeypatch.setattr("app.api.rag.query_knowledge_base", fake_query_knowledge_base)

    try:
        response = client.post("/api/v1/rag/query", json={"question": "ATMR是什么"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "mocked answer for ATMR是什么",
        "sources": [{"title": "Mock Source"}],
        "query": "ATMR是什么",
    }


def test_big_five_rag_query_succeeds_with_authenticated_user(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")

    async def fake_query_big_five_knowledge_base(question: str) -> dict:
        return {
            "answer": f"big five answer for {question}",
            "sources": [{"title": "Big Five"}],
            "query": question,
        }

    monkeypatch.setattr("app.api.rag.query_big_five_knowledge_base", fake_query_big_five_knowledge_base)

    try:
        response = client.post("/api/v1/rag/big-five/query", json={"question": "开放性是什么"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "answer": "big five answer for 开放性是什么",
        "sources": [{"title": "Big Five"}],
        "query": "开放性是什么",
    }


def test_big_five_rag_status_reports_indexed_document(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, username="tester")

    class FakeClient:
        def get_document(self, doc_id: str) -> str:
            return '{"doc_name":"BigFive_Personality_Knowledge"}'

    monkeypatch.setattr("app.api.rag.get_big_five_rag_client", lambda: (FakeClient(), "doc-big-five"))
    monkeypatch.setattr(
        "app.api.rag.get_big_five_document_structure",
        lambda: [{"title": "BigFive_Personality_Knowledge"}],
    )

    try:
        response = client.get("/api/v1/rag/big-five/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "doc": "BigFive_Personality_Knowledge",
        "doc_id": "doc-big-five",
        "document": {"doc_name": "BigFive_Personality_Knowledge"},
        "fallback": False,
        "section_count": 1,
    }
