from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gateway import run as gateway_run


def test_kb_journeys_runtime_lookup_prefers_active_plugin(monkeypatch):
    def external_allowlist(*, session_id: str, message: str):
        return {f"external:{session_id}:{message}"}

    fake_loaded = SimpleNamespace(
        enabled=True,
        module=SimpleNamespace(scoped_mcp_tool_allowlist_for_message=external_allowlist),
    )
    fake_manager = SimpleNamespace(_plugins={"kb_journeys": fake_loaded})

    monkeypatch.setattr("hermes_cli.plugins.discover_plugins", lambda: None)
    monkeypatch.setattr("hermes_cli.plugins.get_plugin_manager", lambda: fake_manager)

    resolved = gateway_run._resolve_kb_journeys_plugin_attr("scoped_mcp_tool_allowlist_for_message")

    assert resolved is external_allowlist
    assert resolved(session_id="s1", message="/kb queue") == {"external:s1:/kb queue"}


def test_kb_journeys_runtime_lookup_keeps_bundled_fallback(monkeypatch):
    fake_manager = SimpleNamespace(_plugins={})

    monkeypatch.setattr("hermes_cli.plugins.discover_plugins", lambda: None)
    monkeypatch.setattr("hermes_cli.plugins.get_plugin_manager", lambda: fake_manager)

    resolved = gateway_run._resolve_kb_journeys_plugin_attr("scoped_mcp_tool_allowlist_for_message")

    assert callable(resolved)


def test_gateway_no_longer_directly_imports_bundled_kb_journeys_allowlist():
    source = (Path(__file__).resolve().parents[2] / "gateway" / "run.py").read_text(encoding="utf-8")

    assert "from plugins.kb_journeys import scoped_mcp_tool_allowlist_for_message" not in source
