"""Guards for the multi-container Hermes WebUI install surface."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_docker_context_includes_license_file() -> None:
    """PEP 639 license-files metadata must resolve inside the Docker image."""
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in dockerignore.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert "LICENSE" not in active_lines
