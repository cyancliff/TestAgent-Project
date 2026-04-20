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
        ("get", "/api/v1/rag/structure", None),
        ("get", "/api/v1/rag/status", None),
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
