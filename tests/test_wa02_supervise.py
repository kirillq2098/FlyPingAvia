"""WA-02 review: supervise.sh production fail-fast (source inspection)."""

from __future__ import annotations

from pathlib import Path

import pytest

SUPERVISE = Path(__file__).resolve().parents[1] / "scripts" / "supervise.sh"


@pytest.fixture(scope="module")
def supervise_src() -> str:
    return SUPERVISE.read_text(encoding="utf-8")


def test_no_swallow_production_restart(supervise_src: str) -> None:
    assert "restart_stack_production || true" not in supervise_src


def test_production_startup_exits_on_failure(supervise_src: str) -> None:
    assert "FATAL: production stack не запущен" in supervise_src
    assert "exit 1" in supervise_src
    # Initial production path must call restart without || true
    assert "if ! restart_stack_production; then" in supervise_src


def test_trycloudflare_is_error_not_warning(supervise_src: str) -> None:
    assert "WARNING: trycloudflare.com" not in supervise_src
    assert "ERROR: temporary trycloudflare URL запрещён в production" in supervise_src
    assert 'host == "trycloudflare.com"' in supervise_src or (
        '"trycloudflare.com"' in supervise_src and "*.trycloudflare.com" in supervise_src
    )


def test_production_does_not_call_ensure_url_synced(supervise_src: str) -> None:
    # Extract restart_stack_production function body roughly
    start = supervise_src.index("restart_stack_production()")
    end = supervise_src.index("cleanup()", start)
    body = supervise_src[start:end]
    assert "ensure_url_synced" not in body
    assert "write_env_url" not in body


def test_development_still_syncs_url(supervise_src: str) -> None:
    assert "restart_stack_dev_tunnel" in supervise_src
    assert "ensure_url_synced" in supervise_src
    start = supervise_src.index("restart_stack_dev_tunnel()")
    end = supervise_src.index("restart_stack_production()", start)
    body = supervise_src[start:end]
    assert "ensure_url_synced" in body
    assert "start_tunnel" in body


def test_dev_tunnel_may_still_retry(supervise_src: str) -> None:
    assert "restart_stack_dev_tunnel || true" in supervise_src
