"""Tests for the generic opaque KB callback registry."""

import asyncio
import time

import pytest

from tools import kb_callback_registry as kb_callbacks


@pytest.fixture(autouse=True)
def _clean_pending():
    kb_callbacks._pending.clear()
    yield
    kb_callbacks._pending.clear()


@pytest.mark.asyncio
async def test_register_returns_short_opaque_id_and_context():
    seen = []

    async def handler(ctx):
        seen.append(ctx)
        return f"ran {ctx.action_id}"

    callback_id = kb_callbacks.register(
        "archive",
        handler,
        chat_id="12345",
        thread_id="999",
        metadata={"entity": "accounts/acme"},
    )

    assert isinstance(callback_id, str)
    assert 6 <= len(callback_id) <= 16
    assert ":" not in callback_id

    result = await kb_callbacks.resolve(
        callback_id,
        actor_id="777",
        actor_name="Ada",
        chat_id="12345",
        thread_id="999",
    )

    assert result == "ran archive"
    assert len(seen) == 1
    ctx = seen[0]
    assert ctx.callback_id == callback_id
    assert ctx.action_id == "archive"
    assert ctx.chat_id == "12345"
    assert ctx.thread_id == "999"
    assert ctx.actor_id == "777"
    assert ctx.actor_name == "Ada"
    assert ctx.metadata == {"entity": "accounts/acme"}


@pytest.mark.asyncio
async def test_resolve_is_one_shot_under_concurrent_clicks():
    calls = 0

    async def handler(ctx):
        nonlocal calls
        calls += 1
        return "done"

    callback_id = kb_callbacks.register("apply", handler)

    first, second = await asyncio.gather(
        kb_callbacks.resolve(callback_id, actor_id="1"),
        kb_callbacks.resolve(callback_id, actor_id="1"),
    )

    assert calls == 1
    assert (first == "done") ^ (second == "done")


@pytest.mark.asyncio
async def test_resolve_stale_entry_does_not_run_handler():
    called = False

    async def handler(ctx):
        nonlocal called
        called = True
        return "should not run"

    callback_id = kb_callbacks.register("old", handler, ttl=0.01)
    kb_callbacks._pending[callback_id]["created_at"] = time.time() - 60

    assert await kb_callbacks.resolve(callback_id) is None
    assert called is False
    assert kb_callbacks.get_pending(callback_id) is None


@pytest.mark.asyncio
async def test_handler_exception_is_safe_error_text():
    async def handler(ctx):
        raise RuntimeError("kaboom")

    callback_id = kb_callbacks.register("explode", handler)

    result = await kb_callbacks.resolve(callback_id, actor_id="1")

    assert result is not None
    assert result == "KB action failed. Check gateway logs for details."
    assert "kaboom" not in result
    assert kb_callbacks.get_pending(callback_id) is None


def test_get_pending_returns_copy_and_clear_removes_entry():
    async def handler(ctx):
        return "ok"

    callback_id = kb_callbacks.register("inspect", handler, metadata={"a": 1})
    pending = kb_callbacks.get_pending(callback_id)
    pending["action_id"] = "mutated"

    assert kb_callbacks.get_pending(callback_id)["action_id"] == "inspect"

    kb_callbacks.clear(callback_id)
    assert kb_callbacks.get_pending(callback_id) is None


@pytest.mark.asyncio
async def test_handler_can_return_followup_card_payload():
    async def handler(ctx):
        return {"text": "Preview ready", "actions": [{"label": "Confirm"}]}

    callback_id = kb_callbacks.register("preview", handler)

    result = await kb_callbacks.resolve(callback_id, actor_id="1")

    assert result == {"text": "Preview ready", "actions": [{"label": "Confirm"}]}


@pytest.mark.asyncio
async def test_callback_is_scoped_to_chat_and_topic():
    async def handler(ctx):
        return "done"

    callback_id = kb_callbacks.register(
        "approve",
        handler,
        chat_id="chat-a",
        thread_id="topic-a",
    )

    wrong_chat = await kb_callbacks.resolve(callback_id, chat_id="chat-b", thread_id="topic-a")
    assert wrong_chat == "This KB action belongs to a different chat."
    assert kb_callbacks.get_pending(callback_id) is not None

    wrong_topic = await kb_callbacks.resolve(callback_id, chat_id="chat-a", thread_id="topic-b")
    assert wrong_topic == "This KB action belongs to a different topic."
    assert kb_callbacks.get_pending(callback_id) is not None

    missing_chat = await kb_callbacks.resolve(callback_id, thread_id="topic-a")
    assert missing_chat == "This KB action belongs to a different chat."
    assert kb_callbacks.get_pending(callback_id) is not None

    missing_topic = await kb_callbacks.resolve(callback_id, chat_id="chat-a")
    assert missing_topic == "This KB action belongs to a different topic."
    assert kb_callbacks.get_pending(callback_id) is not None

    result = await kb_callbacks.resolve(callback_id, chat_id="chat-a", thread_id="topic-a")
    assert result == "done"
    assert kb_callbacks.get_pending(callback_id) is None
