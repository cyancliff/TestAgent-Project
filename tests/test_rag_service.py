import httpx
import pytest

from app.services import rag_service


def test_describe_exception_uses_type_when_detail_is_empty():
    assert rag_service._describe_exception(httpx.ReadTimeout("")) == "ReadTimeout"


def test_parse_llm_scores_accepts_json_fence():
    sections = [{"title": "责任型", "summary": "责任稳定", "text": "", "line_num": 1}]
    content = '```json\n{"scores":[{"index":0,"score":0.82,"reason":"高度相关"}]}\n```'

    scored_sections = rag_service._parse_llm_scores(content, sections)

    assert len(scored_sections) == 1
    assert scored_sections[0]["section"] == sections[0]
    assert scored_sections[0]["score"] == pytest.approx(0.82)
    assert scored_sections[0]["reason"] == "高度相关"


@pytest.mark.asyncio
async def test_llm_score_relevance_retries_once_then_succeeds(monkeypatch):
    sections = [{"title": "责任型", "summary": "责任稳定", "text": "", "line_num": 1}]
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(rag_service.asyncio, "sleep", fake_sleep)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"scores":[{"index":0,"score":0.91,"reason":"语义匹配"}]}'
                        }
                    }
                ]
            }

    class FakeClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, *args, **kwargs):
            type(self).calls += 1
            if type(self).calls == 1:
                raise httpx.ReadTimeout("")
            return FakeResponse()

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(rag_service.httpx, "AsyncClient", FakeClient)

    scored_sections = await rag_service._llm_score_relevance("责任型有什么特点", sections)

    assert FakeClient.calls == 2
    assert len(scored_sections) == 1
    assert scored_sections[0]["section"] == sections[0]
    assert scored_sections[0]["score"] == pytest.approx(0.91)
    assert scored_sections[0]["reason"] == "语义匹配"
