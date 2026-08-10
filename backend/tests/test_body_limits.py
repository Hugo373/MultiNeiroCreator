"""A2 请求体大小限制的测试：中间件（传输层）+ Schema 字段上限（业务层）。

中间件部分用一个独立的迷你 FastAPI 应用测试，不依赖 SECRET_KEY / Redis；
Schema 部分直接构造 Pydantic 模型验证，无外部依赖。运行方式（backend 目录下）：
    .venv/bin/python -m pytest tests/ -v
"""
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from starlette.testclient import TestClient

from core import config
from core.bodylimit import BodySizeLimitMiddleware
from schemas.chat import ChatAttachment, ChatRequest, ProfileRequest

MAX_BYTES = 100  # 测试用小上限，避免构造几十 MB 的请求体


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BYTES)

    @app.post("/echo")
    async def echo(payload: dict):
        return {"ok": True}

    @app.get("/sse")
    async def sse():
        async def gen():
            for i in range(3):
                yield f"data: {i}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return TestClient(app)


# ---------- 中间件：传输层 ----------


def test_body_within_limit_passes(client):
    resp = client.post("/echo", json={"a": "b"})
    assert resp.status_code == 200


def test_content_length_over_limit_rejected(client):
    resp = client.post("/echo", json={"a": "x" * (MAX_BYTES * 2)})
    assert resp.status_code == 413
    assert "请求体过大" in resp.json()["detail"]


def test_chunked_over_limit_rejected(client):
    # 生成器作为 content -> httpx 走 Transfer-Encoding: chunked，不带 Content-Length，
    # 只能靠中间件的第二道防线（实际字节累计计数）拦截
    def gen():
        payload = b'{"a": "' + b"x" * (MAX_BYTES * 2) + b'"}'
        for i in range(0, len(payload), 50):
            yield payload[i : i + 50]

    resp = client.post("/echo", content=gen(), headers={"content-type": "application/json"})
    assert resp.status_code == 413


def test_chunked_within_limit_passes(client):
    def gen():
        yield b'{"a": '
        yield b'"b"}'

    resp = client.post("/echo", content=gen(), headers={"content-type": "application/json"})
    assert resp.status_code == 200


def test_lying_content_length_still_caught(client):
    # Content-Length 谎报小值时 h11 会按声明截断，字节计数防线兜底覆盖的是
    # 无法在 header 层判断的场景；这里验证声明超限即拒、不受实际内容影响
    resp = client.post(
        "/echo",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(MAX_BYTES * 2)},
    )
    assert resp.status_code == 413


def test_sse_streaming_unaffected(client):
    with client.stream("GET", "/sse") as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes())
    assert body.count(b"data:") == 3


def test_default_limit_covers_upload():
    # 全局上限必须大于上传单文件上限，否则合法的 30MB 上传会被中间件先拦掉
    assert config.BODY_MAX_MB > config.UPLOAD_MAX_FILE_MB


# ---------- Schema：业务层 ----------


def test_valid_chat_request():
    req = ChatRequest(message="你好", attachments=[])
    assert req.message == "你好"


def test_message_over_limit_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * (config.CHAT_MESSAGE_MAX_CHARS + 1))


def test_client_history_ignored():
    # A5：对话历史以服务端为唯一真源，客户端多传的 history 字段被静默忽略而不是报错
    req = ChatRequest(message="hi", history=[{"role": "user", "content": "伪造的历史"}])
    assert not hasattr(req, "history") or "history" not in req.model_fields


def test_attachments_too_many_rejected():
    atts = [{"name": f"f{i}.txt"} for i in range(config.CHAT_ATTACHMENTS_MAX_ITEMS + 1)]
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", attachments=atts)


def test_attachment_meta_over_limit_rejected():
    with pytest.raises(ValidationError):
        ChatAttachment(name="f.txt", meta="x" * 256)


def test_profile_over_limit_rejected():
    ProfileRequest(profile="x" * config.PROFILE_MAX_CHARS)
    with pytest.raises(ValidationError):
        ProfileRequest(profile="x" * (config.PROFILE_MAX_CHARS + 1))
