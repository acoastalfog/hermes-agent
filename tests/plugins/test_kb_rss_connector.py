import importlib
import json
from pathlib import Path

import pytest


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Hermes can gather RSS evidence</title>
      <link>https://example.invalid/hermes/rss/1</link>
      <guid>hermes-rss-1</guid>
    </item>
    <item>
      <title>Second item proves truncation</title>
      <link>https://example.invalid/hermes/rss/2</link>
      <guid>hermes-rss-2</guid>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Hermes can parse Atom too</title>
    <link href="https://example.invalid/hermes/atom/1" />
    <id>hermes-atom-1</id>
  </entry>
</feed>
"""


def test_hermes_rss_connector_gathers_bounded_evidence_without_kb_engine_import() -> None:
    evidence = importlib.import_module("plugins.kb_rss_connector.rss_evidence")
    packet = evidence.build_rss_evidence_packet(
        feed_url="https://example.invalid/hermes/rss.xml",
        feed_xml=SAMPLE_RSS_XML,
        max_items=1,
        max_bytes=1000,
        collected_at="2026-06-11T00:00:00Z",
    )

    assert packet["kind"] == "kb.source_evidence"
    assert packet["source_id"] == "rss"
    assert packet["connector_id"] == "hermes.plugin.rss"
    assert packet["harness_id"] == "hermes"
    assert packet["requested_journey"] == "kb_sync"
    assert packet["limits"] == {"max_items": 1, "max_bytes": 1000, "truncated": True}
    assert len(packet["items"]) == 1
    assert packet["provenance"]["retrieval_method"] == "harness_connector"
    assert packet["privacy"] == {"classification": "public", "redactions_applied": []}
    assert packet["connector_run"] == {
        "owner": "harness",
        "harness_id": "hermes",
        "connector_id": "hermes.plugin.rss",
        "source_access": "before_kb_boundary",
        "source_read": {
            "mode": "inline_fixture",
            "source_ref": "https://example.invalid/hermes/rss.xml",
            "bytes_read": len(SAMPLE_RSS_XML.encode("utf-8")),
        },
        "kb_engine_imported": False,
        "live_source_fetch_inside_kb_engine": False,
    }

    for path in (
        Path("plugins/kb_rss_connector/__init__.py"),
        Path("plugins/kb_rss_connector/rss_evidence.py"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "import kb_engine" not in source
        assert "from kb_engine" not in source


def test_hermes_rss_connector_parses_atom_fixture() -> None:
    evidence = importlib.import_module("plugins.kb_rss_connector.rss_evidence")
    packet = evidence.build_rss_evidence_packet(
        feed_url="https://example.invalid/hermes/atom.xml",
        feed_xml=SAMPLE_ATOM_XML,
        max_items=5,
        max_bytes=1000,
        collected_at="2026-06-11T00:00:00Z",
    )

    assert packet["limits"] == {"max_items": 5, "max_bytes": 1000, "truncated": False}
    assert packet["items"] == [
        {
            "external_id": packet["items"][0]["external_id"],
            "title": "Hermes can parse Atom too",
            "url": "https://example.invalid/hermes/atom/1",
        }
    ]
    assert packet["items"][0]["external_id"].startswith("rss:item:")


def test_hermes_rss_connector_rejects_unbounded_or_invalid_input() -> None:
    evidence = importlib.import_module("plugins.kb_rss_connector.rss_evidence")

    with pytest.raises(evidence.RssEvidenceError, match="feed exceeds max_bytes"):
        evidence.build_rss_evidence_packet(
            feed_url="https://example.invalid/hermes/rss.xml",
            feed_xml=SAMPLE_RSS_XML,
            max_items=10,
            max_bytes=10,
        )

    with pytest.raises(evidence.RssEvidenceError, match="invalid RSS/Atom XML"):
        evidence.build_rss_evidence_packet(
            feed_url="https://example.invalid/hermes/rss.xml",
            feed_xml="<rss>",
            max_items=10,
            max_bytes=1000,
        )


def test_hermes_rss_connector_tool_returns_packet_and_never_writes_kb() -> None:
    plugin = importlib.import_module("plugins.kb_rss_connector")
    result = json.loads(
        plugin.handle_kb_rss_gather_evidence(
            {
                "feed_url": "https://example.invalid/hermes/rss.xml",
                "feed_xml": SAMPLE_RSS_XML,
                "max_items": 1,
                "max_bytes": 1000,
            }
        )
    )

    assert "error" not in result
    assert result["harness_id"] == "hermes"
    assert result["connector_id"] == "hermes.plugin.rss"
    assert result["connector_run"]["live_source_fetch_inside_kb_engine"] is False
    rendered = json.dumps(result)
    assert "receipt_states" not in rendered
    assert "prod_write_status" not in rendered
    assert "kb_publication_status" not in rendered


def test_hermes_rss_connector_registers_as_harness_projection_tool() -> None:
    plugin = importlib.import_module("plugins.kb_rss_connector")
    calls = []

    class Context:
        def register_tool(self, **kwargs):
            calls.append(kwargs)

    plugin.register(Context())

    assert calls == [
        {
            "name": "kb_rss_gather_evidence",
            "toolset": "kb-source-access",
            "schema": plugin.RSS_GATHER_EVIDENCE_SCHEMA,
            "handler": plugin.handle_kb_rss_gather_evidence,
        }
    ]
