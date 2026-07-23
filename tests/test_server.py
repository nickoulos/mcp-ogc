"""Unit tests for the FastMCP server entry point (main()) and tool registration.

Hermetic: mcp.run is monkeypatched so no port is ever bound and no server
process is started.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import asyncio

from mcp_ogc import server


def test_main_default_uses_stdio(monkeypatch):
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main([])

    assert calls == [{"transport": "stdio"}]


def test_main_explicit_stdio(monkeypatch):
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main(["--transport", "stdio"])

    assert calls == [{"transport": "stdio"}]


def test_main_streamable_http_sets_host_and_port(monkeypatch):
    calls = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main(
        ["--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8465"]
    )

    assert calls == [{"transport": "streamable-http"}]
    assert server.mcp.settings.host == "0.0.0.0"
    assert server.mcp.settings.port == 8465


def test_mcp_server_registers_expected_tools():
    tools = {t.name for t in asyncio.run(server.mcp.list_tools())}

    assert "list_wms_layers" in tools
    assert "get_wms_map" in tools
    assert "query_wfs_features" in tools
