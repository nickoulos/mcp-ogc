"""Unit tests for the FastMCP server entry point (main()) and tool registration.

Hermetic: mcp.run is monkeypatched so no port is ever bound and no server
process is started.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import asyncio
import re

import responses

from mcp_ogc import server
from tests.fixtures import PNG_1X1, WMTS_CAPABILITIES_100


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
    assert "list_wmts_layers" in tools
    assert "get_wmts_tile" in tools


@responses.activate
def test_get_wmts_tile_tool_returns_image_and_tile_location():
    responses.add(
        responses.GET, re.compile(r"^http://example\.test/wmts"), body=WMTS_CAPABILITIES_100,
        content_type="text/xml", status=200,
    )
    responses.add(
        responses.GET, re.compile(r"^http://example\.test/wmts"), body=PNG_1X1,
        content_type="image/png", status=200,
    )

    result = asyncio.run(
        server.mcp.call_tool(
            "get_wmts_tile",
            {
                "wmts_url": "http://example.test/wmts",
                "layer": "test:basemap",
                "tile_matrix_set": "WebMercatorQuad",
                "tile_matrix": "1",
                "point": [1000.0, -1000.0],
            },
        )
    )
    content = result[0] if isinstance(result, tuple) else result

    assert content[0].type == "image"
    assert content[0].mimeType == "image/png"
    assert content[1].type == "text"
    assert "row=1" in content[1].text
    assert "column=1" in content[1].text
