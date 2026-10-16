"""Tests for the opt-in capabilities cache and retry/backoff.

Hermetic — HTTP mocked with `responses`; sleeping and the clock are patched.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re

import pytest
import requests
import responses

from mcp_ogc import services
from mcp_ogc.errors import OGCError
from mcp_ogc.tools.wfs import query_wfs_features
from mcp_ogc.tools.wms import get_wms_map, list_wms_layers
from tests.fixtures import (
    PNG_1X1,
    WFS_CAPABILITIES_200,
    WFS_GEOJSON_RESPONSE,
    WMS_CAPABILITIES_130,
)

WMS_URL = "http://example.test/wms"
WMS_URL_RE = re.compile(r"^http://example\.test/wms")
OTHER_WMS_URL = "http://other.test/wms"
OTHER_WMS_URL_RE = re.compile(r"^http://other\.test/wms")
WFS_URL = "http://example.test/wfs"
WFS_URL_RE = re.compile(r"^http://example\.test/wfs")


@pytest.fixture
def sleeps(monkeypatch):
    """Record backoff delays instead of actually sleeping."""
    delays: list[float] = []
    monkeypatch.setattr(services, "_sleep", delays.append)
    return delays


def _wms_capabilities(url_re=WMS_URL_RE) -> None:
    responses.add(
        responses.GET, url_re, body=WMS_CAPABILITIES_130,
        content_type="text/xml", status=200,
    )


def _capabilities_requests() -> int:
    return sum("GetCapabilities" in c.request.url for c in responses.calls)


# --- capabilities cache -------------------------------------------------------


@responses.activate
def test_capabilities_refetched_every_call_by_default():
    _wms_capabilities()

    list_wms_layers(WMS_URL)
    list_wms_layers(WMS_URL)

    assert _capabilities_requests() == 2


@responses.activate
def test_capabilities_cached_when_ttl_set(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    _wms_capabilities()

    list_wms_layers(WMS_URL)
    list_wms_layers(WMS_URL)

    assert _capabilities_requests() == 1


@responses.activate
def test_cache_shared_across_tools_for_same_endpoint(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    _wms_capabilities()
    responses.add(
        responses.GET, WMS_URL_RE, body=PNG_1X1, content_type="image/png", status=200,
    )

    list_wms_layers(WMS_URL)
    get_wms_map(WMS_URL, layer="test:roads", bbox=(10.0, 50.0, 11.0, 51.0), crs="EPSG:4326")

    assert _capabilities_requests() == 1


@responses.activate
def test_cache_entry_expires_after_ttl(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    clock = [1000.0]
    monkeypatch.setattr(services, "_now", lambda: clock[0])
    _wms_capabilities()

    list_wms_layers(WMS_URL)
    clock[0] += 61
    list_wms_layers(WMS_URL)

    assert _capabilities_requests() == 2


@responses.activate
def test_cache_is_per_endpoint(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    _wms_capabilities()
    _wms_capabilities(OTHER_WMS_URL_RE)

    list_wms_layers(WMS_URL)
    list_wms_layers(OTHER_WMS_URL)

    assert _capabilities_requests() == 2


@responses.activate
def test_cache_evicts_least_recently_used_beyond_max_entries(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    monkeypatch.setattr(services, "_CACHE_MAX_ENTRIES", 1)
    _wms_capabilities()
    _wms_capabilities(OTHER_WMS_URL_RE)

    list_wms_layers(WMS_URL)
    list_wms_layers(OTHER_WMS_URL)  # evicts WMS_URL
    list_wms_layers(WMS_URL)

    assert _capabilities_requests() == 3


@responses.activate
def test_cache_invalidated_when_auth_config_changes(monkeypatch):
    # Different credentials may see different layers, so they must not share entries.
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    _wms_capabilities()

    list_wms_layers(WMS_URL)
    monkeypatch.setenv("MCP_OGC_AUTH", '{"unrelated.test": {"token": "t"}}')
    list_wms_layers(WMS_URL)

    assert _capabilities_requests() == 2


@responses.activate
def test_failed_capabilities_fetch_is_not_cached(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "60")
    responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))
    _wms_capabilities()

    with pytest.raises(OGCError):
        list_wms_layers(WMS_URL)
    assert len(list_wms_layers(WMS_URL)) == 1


def test_invalid_cache_ttl_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("MCP_OGC_CACHE_TTL", "soon")

    with pytest.raises(OGCError) as exc:
        list_wms_layers(WMS_URL)

    assert "MCP_OGC_CACHE_TTL" in str(exc.value)


# --- retry / backoff ----------------------------------------------------------


@responses.activate
def test_no_retry_by_default(sleeps):
    responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))

    with pytest.raises(OGCError):
        list_wms_layers(WMS_URL)

    assert len(responses.calls) == 1
    assert sleeps == []


@responses.activate
def test_connection_error_retried_with_exponential_backoff(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "3")
    responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))
    responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))
    _wms_capabilities()

    layers = list_wms_layers(WMS_URL)

    assert len(layers) == 1
    assert sleeps == [0.5, 1.0]


@responses.activate
def test_backoff_base_is_configurable(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "1")
    monkeypatch.setenv("MCP_OGC_RETRY_BACKOFF", "2")
    responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))
    _wms_capabilities()

    list_wms_layers(WMS_URL)

    assert sleeps == [2.0]


@responses.activate
def test_gives_up_after_configured_retries(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "2")
    for _ in range(3):
        responses.add(responses.GET, WMS_URL_RE, body=requests.ConnectionError("down"))

    with pytest.raises(OGCError) as exc:
        list_wms_layers(WMS_URL)

    assert len(responses.calls) == 3
    assert WMS_URL in str(exc.value)


@responses.activate
def test_server_error_is_retried(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "1")
    responses.add(responses.GET, WMS_URL_RE, body="busy", status=503)
    _wms_capabilities()

    assert len(list_wms_layers(WMS_URL)) == 1
    assert len(responses.calls) == 2


@responses.activate
def test_client_error_is_not_retried(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "3")
    responses.add(responses.GET, WMS_URL_RE, body="Unauthorized", status=401)

    with pytest.raises(OGCError):
        list_wms_layers(WMS_URL)

    assert len(responses.calls) == 1
    assert sleeps == []


@responses.activate
def test_data_requests_are_retried_too(monkeypatch, sleeps):
    monkeypatch.setenv("MCP_OGC_RETRIES", "1")
    responses.add(
        responses.GET, WFS_URL_RE, body=WFS_CAPABILITIES_200,
        content_type="text/xml", status=200,
    )
    responses.add(responses.GET, WFS_URL_RE, body="busy", status=502)
    responses.add(
        responses.GET, WFS_URL_RE, body=WFS_GEOJSON_RESPONSE,
        content_type="application/json", status=200,
    )

    result = query_wfs_features(WFS_URL, type_name="test:buildings")

    assert result["type"] == "FeatureCollection"
    assert sleeps == [0.5]


def test_invalid_retry_count_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("MCP_OGC_RETRIES", "-1")

    with pytest.raises(OGCError) as exc:
        list_wms_layers(WMS_URL)

    assert "MCP_OGC_RETRIES" in str(exc.value)
