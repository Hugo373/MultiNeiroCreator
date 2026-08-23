import httpx
import pytest

import services.rag.embedding as embedding


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.siliconflow.cn/v1/embeddings")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("request failed", request=request, response=response)

    def json(self):
        return self._payload


def test_get_embedding_uses_siliconflow_openai_compatible_api(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse({"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    monkeypatch.setattr(embedding, "SILICONFLOW_API_KEY", "test-key")
    monkeypatch.setattr(embedding.httpx, "post", fake_post)

    assert embedding.get_embedding("问题") == [0.1, 0.2]
    assert calls[0][0] == embedding.EMBEDDING_API_URL
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0][1]["json"] == {"model": embedding.EMBEDDING_MODEL, "input": "问题"}


def test_get_embeddings_batch_sends_all_chunks_in_one_request(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        # 返回乱序 index，验证客户端按 index 恢复输入顺序。
        return FakeResponse({
            "data": [
                {"index": 1, "embedding": [0.0, 1.0]},
                {"index": 0, "embedding": [1.0, 0.0]},
            ]
        })

    monkeypatch.setattr(embedding, "SILICONFLOW_API_KEY", "test-key")
    monkeypatch.setattr(embedding.httpx, "post", fake_post)

    assert embedding.get_embeddings_batch(["第一段", "第二段"]) == [[1.0, 0.0], [0.0, 1.0]]
    assert len(calls) == 1
    assert calls[0][1]["json"] == {
        "model": embedding.EMBEDDING_MODEL,
        "input": ["第一段", "第二段"],
    }


def test_get_embeddings_batch_rejects_incomplete_api_response(monkeypatch):
    monkeypatch.setattr(embedding, "SILICONFLOW_API_KEY", "test-key")
    monkeypatch.setattr(
        embedding.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse({"data": [{"index": 0, "embedding": [1.0, 0.0]}]}),
    )

    with pytest.raises(RuntimeError, match="预期 2 个"):
        embedding.get_embeddings_batch(["第一段", "第二段"])


def test_embedding_requires_siliconflow_api_key(monkeypatch):
    monkeypatch.setattr(embedding, "SILICONFLOW_API_KEY", "")

    with pytest.raises(RuntimeError, match="未配置 SILICONFLOW_API_KEY"):
        embedding.get_embedding("问题")


def test_embedding_converts_provider_error_without_exposing_key(monkeypatch):
    monkeypatch.setattr(embedding, "SILICONFLOW_API_KEY", "secret-key")
    monkeypatch.setattr(
        embedding.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(
            {"error": "quota exceeded"},
            status_code=429,
            text='{"error":"quota exceeded"}',
        ),
    )

    with pytest.raises(RuntimeError, match="SiliconFlow HTTP 429") as exc_info:
        embedding.get_embedding("问题")
    assert "secret-key" not in str(exc_info.value)
