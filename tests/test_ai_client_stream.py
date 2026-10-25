"""AIClient.chat_stream 流式通道单测（全部 mock，不发真实请求）。"""

import asyncio
from types import SimpleNamespace

from src.platform.ai.ai_client import AIClient


def _chunk(content=None, tool_calls=None, usage=None):
    """构造一个 OpenAI 流式 chunk 的最小替身。"""
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta)
    return SimpleNamespace(choices=[choice], usage=usage)


def _tc_delta(index, id="", name="", arguments=""):
    """构造一个 tool_call 增量分片。"""
    fn = SimpleNamespace(name=name or None, arguments=arguments or None)
    return SimpleNamespace(index=index, id=id or None, function=fn)


class _FakeStream:
    """模拟 AsyncOpenAI 的流式响应（异步迭代器）。"""

    def __init__(self, chunks):
        self._chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)


def _make_client(chunks):
    """构造一个 completions.create 返回固定 chunk 序列的 AIClient。"""
    client = AIClient(base_url="http://mock", api_key="mock", model="mock-model")

    async def fake_create(**kwargs):
        assert kwargs.get("stream") is True
        return _FakeStream(chunks)

    client.client.chat.completions.create = fake_create
    return client


def _collect(client, **kwargs):
    """收集 chat_stream 产出的全部事件。"""

    async def run():
        events = []
        async for ev in client.chat_stream([{"role": "user", "content": "hi"}], **kwargs):
            events.append(ev)
        return events

    return asyncio.run(run())


def test_stream_tokens():
    """纯文本流：逐 token 产出，最后产出完整 message"""
    client = _make_client([
        _chunk(content="你"),
        _chunk(content="好"),
        _chunk(content="！"),
    ])
    events = _collect(client)
    tokens = [t for kind, t in events if kind == "token"]
    assert tokens == ["你", "好", "！"]
    kind, msg = events[-1]
    assert kind == "message"
    assert msg["content"] == "你好！"
    assert msg["tool_calls"] == []


def test_stream_tool_calls_assembled():
    """工具调用流：分片的 arguments 按 index 聚合成完整 tool_calls"""
    client = _make_client([
        _chunk(tool_calls=[_tc_delta(0, id="call_1", name="get_stock_quote")]),
        _chunk(tool_calls=[_tc_delta(0, arguments='{"symbol"')]),
        _chunk(tool_calls=[_tc_delta(0, arguments=': "600519"}')]),
        _chunk(tool_calls=[_tc_delta(1, id="call_2", name="get_portfolio", arguments="{}")]),
    ])
    events = _collect(client, tools=[{"type": "function", "function": {"name": "x"}}])
    kind, msg = events[-1]
    assert kind == "message"
    assert msg["content"] == ""
    assert msg["tool_calls"] == [
        {"id": "call_1", "name": "get_stock_quote", "arguments": '{"symbol": "600519"}'},
        {"id": "call_2", "name": "get_portfolio", "arguments": "{}"},
    ]


def test_stream_forwards_required_tool_choice_to_provider():
    captured: dict = {}
    client = AIClient(base_url="http://mock", api_key="mock", model="mock-model")

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeStream([_chunk(tool_calls=[_tc_delta(0, id="call_1", name="update_price_alert")])])

    client.client.chat.completions.create = fake_create

    _collect(
        client,
        tools=[{"type": "function", "function": {"name": "update_price_alert"}}],
        tool_choice="required",
    )

    assert captured["tool_choice"] == "required"


def test_stream_usage_and_empty_choices():
    """末尾只含 usage 的空 choices chunk 不报错，且累计 token 用量"""
    usage = SimpleNamespace(
        prompt_tokens=30,
        completion_tokens=12,
        total_tokens=42,
        prompt_tokens_details=SimpleNamespace(cached_tokens=10),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=4),
    )
    client = _make_client([
        _chunk(content="ok"),
        SimpleNamespace(choices=[], usage=usage),
    ])
    events = _collect(client)
    assert events[-1][1]["content"] == "ok"
    assert events[-1][1]["usage"] == {
        "input_tokens": 30,
        "output_tokens": 12,
        "total_tokens": 42,
        "cached_input_tokens": 10,
        "reasoning_output_tokens": 4,
        "model": "mock-model",
        "source": "provider",
    }
    assert client.total_tokens_used == 42


def test_empty_api_key_is_tolerated():
    """本地推理服务（Strata / Ollama / llama.cpp）在配置里 api_key 留空。

    openai SDK 对空字符串 api_key 会在构造阶段就抛 "Missing credentials"，
    请求根本发不出去。AIClient 应把它替换成占位值，保证调用方能走到 HTTP 层。
    """
    client = AIClient(base_url="http://mock", api_key="", model="mock-model")
    assert client.api_key == ""
    assert client.client.api_key == "EMPTY"


def test_empty_api_key_still_reaches_transport():
    """空 api_key 不应在本地就失败，错误只可能来自真实网络层。"""
    client = AIClient(base_url="http://127.0.0.1:1", api_key="", model="mock-model")
    called = {}

    async def fake_create(**kwargs):
        called.update(kwargs)
        raise RuntimeError("transport-layer")

    client.client.chat.completions.create = fake_create

    async def run():
        try:
            await client.chat(system_prompt="s", user_content="u", temperature=None)
        except RuntimeError as exc:
            return str(exc)
        return None

    err = asyncio.run(run())
    assert err == "transport-layer"
    assert called["model"] == "mock-model"
