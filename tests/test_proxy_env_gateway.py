"""Proxy env must exempt the Docker host gateway.

A self-hosted PanWatch commonly points its AI base_url at
http://host.docker.internal:<port>/v1. apply_proxy_env() sets HTTP_PROXY, and
every openai SDK client is httpx with trust_env=True, so that request is routed
through the proxy unless the host appears in NO_PROXY. The default list only had
loopback names, which made the AI call fail while the same proxy was required for
market data.
"""

from __future__ import annotations

import os

import pytest

from server import apply_proxy_env


@pytest.fixture(autouse=True)
def _clean_env():
    keys = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
    saved = {key: os.environ.get(key) for key in keys}
    for key in keys:
        os.environ.pop(key, None)
    yield
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

def _no_proxy_hosts() -> set[str]:
    raw = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def test_proxy_env_exempts_docker_host_gateway():
    apply_proxy_env("http://127.0.0.1:7897")
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:7897"
    hosts = _no_proxy_hosts()
    assert "host.docker.internal" in hosts


def test_proxy_env_preserves_existing_no_proxy_entries():
    os.environ["NO_PROXY"] = "localhost,127.0.0.1,my.internal.host"
    apply_proxy_env("http://127.0.0.1:7897")
    hosts = _no_proxy_hosts()
    assert "my.internal.host" in hosts
    assert "host.docker.internal" in hosts


def test_clearing_proxy_removes_env_but_keeps_gateway_exempt():
    apply_proxy_env("http://127.0.0.1:7897")
    apply_proxy_env("")
    assert "HTTP_PROXY" not in os.environ
    assert "HTTPS_PROXY" not in os.environ
    hosts = _no_proxy_hosts()
    assert "host.docker.internal" in hosts
