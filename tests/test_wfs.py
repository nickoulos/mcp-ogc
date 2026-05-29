"""Unit tests for the WFS tool.

Hermetic — HTTP mocked with `responses` (owslib uses requests internally).

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

import responses

from mcp_ogc.tools.wfs import query_wfs_features
from tests.fixtures import WFS_CAPABILITIES_200, WFS_GEOJSON_RESPONSE

WFS_URL = "http://example.test/wfs"
WFS_URL_RE = re.compile(r"^http://example\.test/wfs")


def _register_capabilities() -> None:
    responses.add(
        responses.GET,
        WFS_URL_RE,
        body=WFS_CAPABILITIES_200,
        content_type="text/xml",
        status=200,
    )


def _register_getfeature() -> None:
    responses.add(
        responses.GET,
        WFS_URL_RE,
        body=WFS_GEOJSON_RESPONSE,
        content_type="application/json",
        status=200,
    )


@responses.activate
def test_query_wfs_features_returns_feature_collection():
    _register_capabilities()
    _register_getfeature()

    result = query_wfs_features(WFS_URL, type_name="test:buildings")

    assert result["type"] == "FeatureCollection"
    assert isinstance(result["features"], list)


@responses.activate
def test_query_wfs_features_parses_feature_properties():
    _register_capabilities()
    _register_getfeature()

    result = query_wfs_features(WFS_URL, type_name="test:buildings")

    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["name"] == "Town Hall"


@responses.activate
def test_query_wfs_features_requests_json_output():
    _register_capabilities()
    _register_getfeature()

    query_wfs_features(WFS_URL, type_name="test:buildings", max_features=50)

    url = responses.calls[-1].request.url
    assert "application%2Fjson" in url or "application/json" in url
