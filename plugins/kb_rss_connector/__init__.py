"""Hermes RSS evidence connector plugin."""

from __future__ import annotations

from typing import Any

from tools.registry import tool_error, tool_result

from .rss_evidence import RssEvidenceError, build_rss_evidence_packet


RSS_GATHER_EVIDENCE_SCHEMA = {
    "name": "kb_rss_gather_evidence",
    "description": (
        "Gather bounded RSS/Atom evidence as a Hermes harness connector. "
        "Returns a kb.source_evidence packet for kb_sync preview; does not write to the KB."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feed_url": {
                "type": "string",
                "description": "RSS/Atom feed URL to gather from.",
            },
            "feed_xml": {
                "type": "string",
                "description": "Optional fixture XML. Use only for local tests or explicit supplied content.",
            },
            "max_items": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 20,
            },
            "max_bytes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000000,
                "default": 200000,
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 1,
                "maximum": 30,
                "default": 10,
            },
        },
        "required": ["feed_url"],
        "additionalProperties": False,
    },
}


def handle_kb_rss_gather_evidence(args: dict[str, Any], **_: Any) -> str:
    """Tool handler returning a kb.source_evidence packet."""

    feed_url = str(args.get("feed_url") or "").strip()
    if not feed_url:
        return tool_error("feed_url is required")
    try:
        packet = build_rss_evidence_packet(
            feed_url=feed_url,
            feed_xml=args.get("feed_xml"),
            max_items=args.get("max_items", 20),
            max_bytes=args.get("max_bytes", 200_000),
            timeout_seconds=args.get("timeout_seconds", 10),
        )
    except RssEvidenceError as exc:
        return tool_error(str(exc))
    return tool_result(packet)


def register(ctx) -> None:
    """Register the Hermes RSS evidence tool."""

    ctx.register_tool(
        name="kb_rss_gather_evidence",
        toolset="kb-source-access",
        schema=RSS_GATHER_EVIDENCE_SCHEMA,
        handler=handle_kb_rss_gather_evidence,
    )
