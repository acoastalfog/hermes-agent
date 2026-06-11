"""Pure RSS/Atom evidence packet builder for Hermes.

This module intentionally has no kb-engine dependency. It gathers source
evidence before the KB boundary and returns a packet that kb-engine can later
validate, preview, confirm, remember, and receipt.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any


CONNECTOR_ID = "hermes.plugin.rss"
HARNESS_ID = "hermes"
SOURCE_ID = "rss"
DEFAULT_USER_AGENT = "hermes-kb-rss-connector/1"


class RssEvidenceError(ValueError):
    """Raised when RSS evidence gathering cannot produce a bounded packet."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def _item_external_id(guid: str, link: str, title: str) -> str:
    basis = guid or link or title
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"rss:item:{digest}"


def read_bounded_url(feed_url: str, *, max_bytes: int, timeout_seconds: int) -> tuple[bytes, dict[str, Any]]:
    """Read a feed URL with a hard byte limit."""

    request = urllib.request.Request(feed_url, headers={"User-Agent": DEFAULT_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - harness-owned explicit URL read
            data = response.read(max_bytes + 1)
    except urllib.error.URLError as exc:
        raise RssEvidenceError(f"unable to read RSS feed: {exc.reason}") from exc
    if len(data) > max_bytes:
        raise RssEvidenceError("feed exceeds max_bytes")
    return data, {"mode": "url", "source_ref": feed_url, "bytes_read": len(data)}


def read_source_bytes(
    *,
    feed_url: str,
    feed_xml: str | None = None,
    fixture: Path | None = None,
    max_bytes: int,
    timeout_seconds: int,
) -> tuple[bytes, dict[str, Any]]:
    """Read bounded source bytes before the KB boundary."""

    if feed_xml is not None:
        data = feed_xml.encode("utf-8")
        if len(data) > max_bytes:
            raise RssEvidenceError("feed exceeds max_bytes")
        return data, {"mode": "inline_fixture", "source_ref": feed_url, "bytes_read": len(data)}
    if fixture is not None:
        data = fixture.read_bytes()
        if len(data) > max_bytes:
            raise RssEvidenceError("feed exceeds max_bytes")
        return data, {"mode": "file_fixture", "source_ref": str(fixture), "bytes_read": len(data)}
    return read_bounded_url(feed_url, max_bytes=max_bytes, timeout_seconds=timeout_seconds)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_items(feed: ET.Element) -> list[ET.Element]:
    rss_items = feed.findall(".//item")
    if rss_items:
        return rss_items
    return [element for element in feed.iter() if _local_name(element.tag) == "entry"]


def _find_text(element: ET.Element, local_name: str) -> str:
    found = element.find(local_name)
    if found is not None and found.text:
        return found.text.strip()
    for child in element.iter():
        if _local_name(child.tag) == local_name and child.text:
            return child.text.strip()
    return ""


def _find_link(element: ET.Element) -> str:
    text_link = _find_text(element, "link")
    if text_link:
        return text_link
    for child in element.iter():
        if _local_name(child.tag) == "link" and child.attrib.get("href"):
            return child.attrib["href"].strip()
    return ""


def parse_rss_or_atom(raw_bytes: bytes, *, max_items: int) -> tuple[list[dict[str, Any]], bool]:
    """Parse bounded RSS or Atom bytes into evidence items."""

    try:
        feed = ET.fromstring(raw_bytes)
    except ET.ParseError as exc:
        raise RssEvidenceError(f"invalid RSS/Atom XML: {exc}") from exc
    raw_items = _find_items(feed)
    items: list[dict[str, Any]] = []
    for raw_item in raw_items[:max_items]:
        title = _find_text(raw_item, "title")
        link = _find_link(raw_item)
        guid = _find_text(raw_item, "guid") or _find_text(raw_item, "id") or link or title
        items.append(
            {
                "external_id": _item_external_id(guid, link, title),
                "title": title,
                "url": link,
            }
        )
    return items, len(raw_items) > max_items


def build_rss_evidence_packet(
    *,
    feed_url: str,
    feed_xml: str | None = None,
    fixture: Path | None = None,
    max_items: int = 20,
    max_bytes: int = 200_000,
    timeout_seconds: int = 10,
    collected_at: str | None = None,
) -> dict[str, Any]:
    """Gather RSS evidence before the KB boundary as a Hermes connector."""

    max_items = _coerce_int(max_items, default=20, minimum=1, maximum=1000)
    max_bytes = _coerce_int(max_bytes, default=200_000, minimum=1, maximum=1_000_000)
    timeout_seconds = _coerce_int(timeout_seconds, default=10, minimum=1, maximum=30)

    raw_bytes, source_read = read_source_bytes(
        feed_url=feed_url,
        feed_xml=feed_xml,
        fixture=fixture,
        max_bytes=max_bytes,
        timeout_seconds=timeout_seconds,
    )
    items, truncated = parse_rss_or_atom(raw_bytes, max_items=max_items)

    return {
        "schema_version": 1,
        "kind": "kb.source_evidence",
        "source_id": SOURCE_ID,
        "connector_id": CONNECTOR_ID,
        "harness_id": HARNESS_ID,
        "collected_at": collected_at or _utc_now(),
        "items": items,
        "provenance": {
            "source_refs": [feed_url],
            "external_ids": [item["external_id"] for item in items],
            "retrieval_method": "harness_connector",
        },
        "privacy": {
            "classification": "public",
            "redactions_applied": [],
        },
        "requested_journey": "kb_sync",
        "limits": {
            "max_items": max_items,
            "max_bytes": max_bytes,
            "truncated": truncated,
        },
        "connector_run": {
            "owner": "harness",
            "harness_id": HARNESS_ID,
            "connector_id": CONNECTOR_ID,
            "source_access": "before_kb_boundary",
            "source_read": source_read,
            "kb_engine_imported": False,
            "live_source_fetch_inside_kb_engine": False,
        },
    }
