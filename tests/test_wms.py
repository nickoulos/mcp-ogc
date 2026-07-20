"""Unit tests for the WMS tools.

owslib uses the `requests` library internally, so we mock HTTP with `responses`
(NOT pytest-httpx, which only intercepts httpx). Tests are hermetic — no network.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re
from urllib.parse import parse_qs, urlparse

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


@responses.activate
def test_get_wms_map_epsg3006_sends_bbox_northing_first():
    """WMS 1.3.0 + EPSG:3006 requires bbox on the wire as N,E (northing first).

    Callers always pass bbox as (minx, miny, maxx, maxy) = easting-first,
    regardless of CRS. A wrong axis order is NOT an error: GeoServer returns
    HTTP 200 with a nearly blank PNG, so this contract must be locked at the
    request-building level.
    """
    _register_capabilities()
    responses.add(
        responses.GET,
        WMS_URL_RE,
        body=PNG_1X1,
        content_type="image/png",
        status=200,
    )

    # Central Sundsvall in EPSG:3006 (SWEREF99 TM), easting-first as documented.
    get_wms_map(
        WMS_URL,
        layer="test:roads",
        bbox=(619000.0, 6917000.0, 620000.0, 6918000.0),
        crs="EPSG:3006",
        width=1,
        height=1,
    )

    getmap_request = responses.calls[-1].request
    params = {k.lower(): v for k, v in parse_qs(urlparse(getmap_request.url).query).items()}

    # WMS 1.3.0 names the parameter `crs`, not `srs`.
    assert params["crs"] == ["EPSG:3006"]
    assert "srs" not in params

    # On the wire the bbox must be northing-first: min_n,min_e,max_n,max_e.
    sent_bbox = [float(v) for v in params["bbox"][0].split(",")]
    assert sent_bbox == [6917000.0, 619000.0, 6918000.0, 620000.0]
