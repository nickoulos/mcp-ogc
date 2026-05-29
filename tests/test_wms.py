"""Unit tests for the WMS tools.

owslib uses the `requests` library internally, so we mock HTTP with `responses`
(NOT pytest-httpx, which only intercepts httpx). Tests are hermetic — no network.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

import responses

from mcp_ogc.models import LayerInfo
from mcp_ogc.tools.wms import get_wms_map, list_wms_layers
from tests.fixtures import PNG_1X1, WMS_CAPABILITIES_130

WMS_URL = "http://example.test/wms"
# owslib appends ?service=WMS&request=GetCapabilities&... to the base URL,
# so match the endpoint regardless of query string.
WMS_URL_RE = re.compile(r"^http://example\.test/wms")


def _register_capabilities() -> None:
    responses.add(
        responses.GET,
        WMS_URL_RE,
        body=WMS_CAPABILITIES_130,
        content_type="text/xml",
        status=200,
    )


@responses.activate
def test_list_wms_layers_returns_layerinfo():
    _register_capabilities()

    layers = list_wms_layers(WMS_URL)

    assert len(layers) == 1
    assert isinstance(layers[0], LayerInfo)


@responses.activate
def test_list_wms_layers_maps_metadata():
    _register_capabilities()

    layer = list_wms_layers(WMS_URL)[0]

    assert layer.name == "test:roads"
    assert layer.title == "Roads"
    assert layer.abstract == "Test road network."
    assert "EPSG:3857" in layer.crs_options
    assert "EPSG:4326" in layer.crs_options


@responses.activate
def test_list_wms_layers_parses_bbox():
    _register_capabilities()

    layer = list_wms_layers(WMS_URL)[0]

    assert layer.bbox_wgs84 == (10.0, 50.0, 11.0, 51.0)


@responses.activate
def test_get_wms_map_returns_png_bytes():
    _register_capabilities()
    # GetMap hits the same endpoint with different query params.
    responses.add(
        responses.GET,
        WMS_URL_RE,
        body=PNG_1X1,
        content_type="image/png",
        status=200,
    )

    img = get_wms_map(
        WMS_URL,
        layer="test:roads",
        bbox=(10.0, 50.0, 11.0, 51.0),
        crs="EPSG:4326",
        width=1,
        height=1,
    )

    assert isinstance(img, bytes)
    assert img[:8] == b"\x89PNG\r\n\x1a\n"


@responses.activate
def test_get_wms_map_sends_crs_as_srs_param():
    _register_capabilities()
    responses.add(
        responses.GET,
        WMS_URL_RE,
        body=PNG_1X1,
        content_type="image/png",
        status=200,
    )

    get_wms_map(
        WMS_URL,
        layer="test:roads",
        bbox=(10.0, 50.0, 11.0, 51.0),
        crs="EPSG:3857",
        width=1,
        height=1,
    )

    # The final request is the GetMap call; confirm the CRS was forwarded.
    getmap_request = responses.calls[-1].request
    assert "EPSG%3A3857" in getmap_request.url or "EPSG:3857" in getmap_request.url
