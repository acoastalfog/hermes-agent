"""Generic opaque KB callback primitive for gateway action cards."""

from __future__ import annotations

import inspect
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 300


@dataclass(frozen=True)
class KbCallbackContext:
    """Context passed to a resolved KB action handler."""

    callback_id: str
    action_id: str
    chat_id: Optional[str] = None
    thread_id: Optional[str] = None
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


KbCallbackResult = Optional[str] | Mapping[str, Any]
KbCallbackHandler = Callable[[KbCallbackContext], Awaitable[KbCallbackResult] | KbCallbackResult]


@dataclass(frozen=True)
class KbAction:
    """Action-card button definition.

    Platform adapters render only ``label`` and route clicks through the opaque
    registry id.  ``action_id`` and ``metadata`` are for the handler context.
    """

    label: str
    action_id: str
    handler: KbCallbackHandler
    metadata: Mapping[str, Any] = field(default_factory=dict)
    ttl: float = DEFAULT_TTL_SECONDS


_pending: Dict[str, Dict[str, Any]] = {}
_lock = threading.RLock()


def _new_callback_id() -> str:
    return secrets.token_urlsafe(8).rstrip("=")


def register(
    action_id: str,
    handler: KbCallbackHandler,
    *,
    chat_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
    ttl: float = DEFAULT_TTL_SECONDS,
) -> str:
    """Register a one-shot KB action and return a short opaque callback id."""
    if not callable(handler):
        raise TypeError("handler must be callable")

    with _lock:
        callback_id = _new_callback_id()
        while callback_id in _pending:
            callback_id = _new_callback_id()
        _pending[callback_id] = {
            "action_id": str(action_id),
            "handler": handler,
            "chat_id": str(chat_id) if chat_id is not None else None,
            "thread_id": str(thread_id) if thread_id is not None else None,
            "metadata": dict(metadata or {}),
            "ttl": float(ttl),
            "created_at": time.time(),
        }
        return callback_id


def get_pending(callback_id: str) -> Optional[Dict[str, Any]]:
    """Return a copy of a pending callback entry, or None."""
    with _lock:
        entry = _pending.get(str(callback_id))
        if not entry:
            return None
        copied = dict(entry)
        copied["metadata"] = dict(entry.get("metadata") or {})
        return copied


def clear(callback_id: str) -> None:
    """Drop a pending callback without running it."""
    with _lock:
        _pending.pop(str(callback_id), None)


async def resolve(
    callback_id: str,
    *,
    actor_id: Optional[str] = None,
    actor_name: Optional[str] = None,
    chat_id: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> KbCallbackResult:
    """Resolve a pending callback once and run its handler safely."""
    callback_id = str(callback_id)
    with _lock:
        entry = _pending.get(callback_id)
        if not entry:
            return None
        age = time.time() - float(entry.get("created_at", 0) or 0)
        if age > float(entry.get("ttl", DEFAULT_TTL_SECONDS)):
            _pending.pop(callback_id, None)
            return None
        expected_chat_id = entry.get("chat_id")
        expected_thread_id = entry.get("thread_id")
        actual_chat_id = str(chat_id) if chat_id is not None else None
        actual_thread_id = str(thread_id) if thread_id is not None else None
        if expected_chat_id is not None and actual_chat_id != expected_chat_id:
            return "This KB action belongs to a different chat."
        if expected_thread_id is not None and actual_thread_id != expected_thread_id:
            return "This KB action belongs to a different topic."
        _pending.pop(callback_id, None)
        handler = entry.get("handler")
        ctx = KbCallbackContext(
            callback_id=callback_id,
            action_id=str(entry.get("action_id") or ""),
            chat_id=entry.get("chat_id") or (str(chat_id) if chat_id is not None else None),
            thread_id=entry.get("thread_id") or (str(thread_id) if thread_id is not None else None),
            actor_id=str(actor_id) if actor_id is not None else None,
            actor_name=str(actor_name) if actor_name else None,
            metadata=dict(entry.get("metadata") or {}),
        )

    if not handler:
        return None
    try:
        result = handler(ctx)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:
        logger.error(
            "KB callback handler for %s raised: %s",
            ctx.action_id,
            exc,
            exc_info=True,
        )
        return "KB action failed. Check gateway logs for details."
    if isinstance(result, str) or isinstance(result, Mapping) or result is None:
        return result
    return None
