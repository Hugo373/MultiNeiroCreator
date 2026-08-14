"""chat_orchestrator 的单元测试（C2+C3）：todo §6.4 要求的五种场景。

用假 client 按剧本回放流式分片，验证编排器的行为契约：
无工具 / 一个工具 / 同轮多工具 / 工具失败不崩流 / 无限请求工具触顶收尾。
"""

import asyncio
import json

import pytest

from services.chat import chat_orchestrator
from services.chat.context_builder import ChatContext

# ---------- 假流式分片 ----------


class _Func:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _ToolCallDelta:
    def __init__(self, index=0, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _Func(name, arguments)


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, delta):
        self.delta = delta


class _Chunk:
    def __init__(self, content=None, tool_calls=None):
        self.choices = [_Choice(_Delta(content, tool_calls))]


def content_stream(*texts):
    return [_Chunk(content=t) for t in texts]


def tool_call_stream(*calls):
    """calls: (index, id, name, arguments)；arguments 拆两段模拟流式分片。"""
    chunks = []
    for index, call_id, name, arguments in calls:
        half = len(arguments) // 2
        chunks.append(_Chunk(tool_calls=[_ToolCallDelta(index, call_id, name, arguments[:half])]))
        chunks.append(_Chunk(tool_calls=[_ToolCallDelta(index, None, None, arguments[half:])]))
    return chunks


class FakeClient:
    """按剧本逐次回放流；记录每次请求的 kwargs 供断言。"""

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.script.pop(0))


# ---------- 公共脚手架 ----------


@pytest.fixture
def persisted(monkeypatch):
    saved = []
    monkeypatch.setattr(
        chat_orchestrator, "append_message",
        lambda user_id, role, content, project_id=None, attachments=None: saved.append((role, content)),
    )

    async def fake_context(user_id, message, project_id=None, attachments=None):
        return ChatContext(
            messages=[{"role": "system", "content": "SYS"}, {"role": "user", "content": message}],
            clean_history=[{"role": "user", "content": message}],
            persist_text=message,
            attachments=[],
        )

    monkeypatch.setattr(chat_orchestrator, "build_chat_context", fake_context)
    return saved


def run_chat(monkeypatch, script):
    fake = FakeClient(script)
    monkeypatch.setattr(chat_orchestrator, "client", fake)

    async def collect():
        events = []
        async for raw in chat_orchestrator.stream_chat({"id": 1}, "hi"):
            events.append(json.loads(raw.removeprefix("data: ").strip()))
        return events

    return fake, asyncio.run(collect())


def events_of(events, type_):
    return [e for e in events if e["type"] == type_]


# ---------- 五种场景 ----------


def test_no_tool(monkeypatch, persisted):
    fake, events = run_chat(monkeypatch, [content_stream("你", "好")])

    assert "".join(e["content"] for e in events_of(events, "content")) == "你好"
    assert events_of(events, "tool") == []
    done = events_of(events, "done")[0]
    assert done["tool_used"] is None
    assert done["history"][-1] == {"role": "assistant", "content": "你好"}
    assert len(fake.calls) == 1
    assert "tools" in fake.calls[0]  # 首轮必须把工具亮给模型
    assert persisted == [("user", "hi"), ("assistant", "你好")]


def test_single_tool(monkeypatch, persisted):
    script = [
        tool_call_stream((0, "call_1", "calculate", '{"expression": "1+1"}')),
        content_stream("等于2"),
    ]
    fake, events = run_chat(monkeypatch, script)

    assert [e["tool_name"] for e in events_of(events, "tool")] == ["calculate"]
    assert events_of(events, "done")[0]["tool_used"] == "calculate"
    # 第二次请求必须带回：assistant 的 tool_calls 声明 + 对应 tool 结果
    second_messages = fake.calls[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert second_messages[-1] == {"role": "tool", "content": "2", "tool_call_id": "call_1"}


def test_multiple_tools_in_one_round(monkeypatch, persisted):
    script = [
        tool_call_stream(
            (0, "call_a", "calculate", '{"expression": "1+1"}'),
            (1, "call_b", "calculate", '{"expression": "2+2"}'),
        ),
        content_stream("2和4"),
    ]
    fake, events = run_chat(monkeypatch, script)

    assert [e["tool_name"] for e in events_of(events, "tool")] == ["calculate", "calculate"]
    tool_messages = [m for m in fake.calls[1]["messages"] if m["role"] == "tool"]
    # 按 index 聚合：两个调用的参数各归各，不会拼接串味
    assert {(m["tool_call_id"], m["content"]) for m in tool_messages} == {
        ("call_a", "2"),
        ("call_b", "4"),
    }


def test_tool_failure_does_not_break_stream(monkeypatch, persisted):
    script = [
        tool_call_stream((0, "call_1", "not_a_tool", "{}")),
        content_stream("工具不可用，直接回答"),
    ]
    fake, events = run_chat(monkeypatch, script)

    # 未知工具被拒绝，但流不断：结果单照样回填给模型继续对话
    assert events_of(events, "error") == []
    tool_message = next(m for m in fake.calls[1]["messages"] if m["role"] == "tool")
    assert "不支持的工具" in tool_message["content"]
    assert events_of(events, "done")[0]["history"][-1]["content"] == "工具不可用，直接回答"


def test_infinite_tool_requests_hit_round_limit(monkeypatch, persisted):
    rounds = chat_orchestrator.MAX_TOOL_ROUNDS
    script = [
        tool_call_stream((0, f"call_{i}", "calculate", '{"expression": "1+1"}'))
        for i in range(rounds)
    ] + [content_stream("最终回答")]
    fake, events = run_chat(monkeypatch, script)

    assert len(fake.calls) == rounds + 1
    final_call = fake.calls[-1]
    assert "tools" not in final_call  # 收尾轮不给工具：模型只能说话
    assert final_call["messages"][-1] == {
        "role": "system",
        "content": chat_orchestrator.TOOL_LIMIT_NOTICE,
    }
    assert events_of(events, "done")[0]["history"][-1]["content"] == "最终回答"


def test_per_round_tool_call_cap(monkeypatch, persisted):
    cap = chat_orchestrator.MAX_TOOL_CALLS_PER_ROUND
    calls = [
        (i, f"call_{i}", "calculate", '{"expression": "1+1"}') for i in range(cap + 2)
    ]
    script = [tool_call_stream(*calls), content_stream("ok")]
    fake, events = run_chat(monkeypatch, script)

    assert len(events_of(events, "tool")) == cap  # 超额的没执行
    tool_messages = [m for m in fake.calls[1]["messages"] if m["role"] == "tool"]
    assert len(tool_messages) == cap + 2  # 但每个 tool_call_id 都有应答（协议要求）
    skipped = [m for m in tool_messages if m["content"] == chat_orchestrator.TOOL_SKIPPED_RESULT]
    assert len(skipped) == 2
