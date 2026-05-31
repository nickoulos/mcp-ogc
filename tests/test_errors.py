"""Tests for agent-friendly error handling.

Hermetic — HTTP mocked with `responses`.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

import pytest
import responses

from mcp_ogc.errors import OGCError
from mcp_ogc.tools.wfs import query_wfs_features
from mcp_ogc.tools.wms import get_wms_map, list_wms_layers
from tests.fixtures import WFS_CAPABILITIES_200, WMS_CAPABILITIES_130

WMS_URL = "http://example.test/wms"
WMS_URL_RE = re.compile(r"^http://example\.test/wms")
WFS_URL = "http://example.test/wfs"
WFS_URL_RE = re.compile(r"^http://example\.test/wfs")


@responses.activate
def test_get_wms_map_unknown_layer_lists_available():
    responses.add(
        responses.GET, WMS_URL_RE, body=WMS_CAPABILITIES_130,
        content_type="text/xml", status=200,
    )

    with pytest.raises(OGCError) as exc:
        get_wms_map(WMS_URL, layer="does-not-exist", bbox=(10.0, 50.0, 11.0, 51.0))

    msg = str(exc.value)
    assert "does-not-exist" in msg
    # The message should help the agent recover by naming a real layer.
    assert "test:roads" in msg


@responses.activate
def test_query_wfs_features_unknown_type_lists_available():
    responses.add(
        responses.GET, WFS_URL_RE, body=WFS_CAPABILITIES_200,
        content_type="text/xml", status=200,
    )

    with pytest.raises(OGCError) as exc:
        query_wfs_features(WFS_URL, type_name="nope:missing")

    msg = str(exc.value)
    assert "nope:missing" in msg
    assert "test:buildings" in msg


@responses.activate
def test_list_wms_layers_connection_error_is_wrapped():
    responses.add(
        responses.GET, WMS_URL_RE,
        body=ConnectionError("boom"),
    )

    with pytest.raises(OGCError) as exc:
        list_wms_layers(WMS_URL)

    # A clear message mentioning the endpoint, not a raw requests traceback.
    assert WMS_URL in str(exc.value)
