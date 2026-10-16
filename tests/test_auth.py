"""Tests for per-host authentication (MCP_OGC_AUTH).

Hermetic — HTTP mocked with `responses`.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import base64
import json
import re

import pytest
import requests
import responses

from mcp_ogc.auth import AUTH_ENV_VAR, auth_for_url
from mcp_ogc.errors import OGCError
from mcp_ogc.tools.wfs import query_wfs_features
from mcp_ogc.tools.wms import get_wms_map, list_wms_layers
from tests.fixtures import (
    PNG_1X1,
    WFS_CAPABILITIES_200,
    WFS_GEOJSON_RESPONSE,
    WMS_CAPABILITIES_130,
)

SECURE_WMS_URL = "https://secure.example.test/wms"
SECURE_WMS_URL_RE = re.compile(r"^https://secure\.example\.test/wms")


def _set_auth(monkeypatch, mapping) -> None:
    monkeypatch.setenv(AUTH_ENV_VAR, json.dumps(mapping))


def _header_for(url: str, request_url: str | None = None) -> str | None:
    """Authorization header owslib would send to `request_url` with url's auth.

    Mirrors owslib's openURL: Basic credentials as a tuple, otherwise the delegate.
    """
    auth = auth_for_url(url)
    if auth is None:
        return None
    request = requests.Request("GET", request_url or url)
    if auth.username and auth.password:
        request.auth = (auth.username, auth.password)
    else:
        request.auth = auth.auth_delegate
    return request.prepare().headers.get("Authorization")


def _basic(username: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()


def test_no_env_means_no_auth(monkeypatch):
    monkeypatch.delenv(AUTH_ENV_VAR, raising=False)

    assert auth_for_url(SECURE_WMS_URL) is None


def test_basic_credentials_for_matching_host(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})

    assert _header_for(SECURE_WMS_URL) == _basic("u", "p")


def test_host_match_is_case_insensitive(monkeypatch):
    _set_auth(monkeypatch, {"Secure.Example.TEST": {"username": "u", "password": "p"}})

    assert _header_for("https://SECURE.example.test/wms") == _basic("u", "p")


def test_host_with_port_key_matches_only_that_port(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test:8443": {"username": "u", "password": "p"}})

    assert _header_for("https://secure.example.test:8443/wms") == _basic("u", "p")
    assert auth_for_url("https://secure.example.test/wms") is None


def test_credentials_never_sent_to_other_hosts(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})

    assert auth_for_url("https://evil.example.test/wms") is None
    # A lookalike host that merely *contains* the configured name must not match.
    assert auth_for_url("https://secure.example.test.evil.test/wms") is None


def test_bearer_token_sets_authorization_header(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"token": "s3cret"}})

    assert _header_for(SECURE_WMS_URL) == "Bearer s3cret"


def test_refuses_credentials_over_plain_http(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "hunter2"}})

    with pytest.raises(OGCError) as exc:
        auth_for_url("http://secure.example.test/wms")

    msg = str(exc.value)
    assert "https" in msg
    assert "hunter2" not in msg


def test_plain_http_allowed_when_explicitly_opted_in(monkeypatch):
    _set_auth(
        monkeypatch,
        {
            "secure.example.test": {
                "username": "u",
                "password": "p",
                "allow_insecure_http": True,
            }
        },
    )

    assert _header_for("http://secure.example.test/wms") == _basic("u", "p")


def test_invalid_json_is_a_clear_error_without_echoing_secrets(monkeypatch):
    monkeypatch.setenv(AUTH_ENV_VAR, '{"secure.example.test": {"password": "hunter2"')

    with pytest.raises(OGCError) as exc:
        auth_for_url(SECURE_WMS_URL)

    assert AUTH_ENV_VAR in str(exc.value)
    assert "hunter2" not in str(exc.value)


def test_entry_without_usable_credentials_is_rejected(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u"}})

    with pytest.raises(OGCError) as exc:
        auth_for_url(SECURE_WMS_URL)

    assert "secure.example.test" in str(exc.value)


@responses.activate
def test_list_wms_layers_sends_basic_auth_to_configured_host(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})
    responses.add(
        responses.GET, SECURE_WMS_URL_RE, body=WMS_CAPABILITIES_130,
        content_type="text/xml", status=200,
    )

    list_wms_layers(SECURE_WMS_URL)

    assert responses.calls[0].request.headers["Authorization"] == _basic("u", "p")


@responses.activate
def test_unconfigured_host_gets_no_authorization_header(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})
    responses.add(
        responses.GET, re.compile(r"^http://example\.test/wfs"), body=WFS_CAPABILITIES_200,
        content_type="text/xml", status=200,
    )
    responses.add(
        responses.GET, re.compile(r"^http://example\.test/wfs"), body=WFS_GEOJSON_RESPONSE,
        content_type="application/json", status=200,
    )

    query_wfs_features("http://example.test/wfs", type_name="test:buildings")

    assert all("Authorization" not in c.request.headers for c in responses.calls)


@responses.activate
def test_rejected_request_hints_at_auth_config(monkeypatch):
    monkeypatch.delenv(AUTH_ENV_VAR, raising=False)
    responses.add(
        responses.GET, SECURE_WMS_URL_RE, body="Unauthorized", status=401,
    )

    with pytest.raises(OGCError) as exc:
        list_wms_layers(SECURE_WMS_URL)

    msg = str(exc.value)
    assert SECURE_WMS_URL in msg
    assert AUTH_ENV_VAR in msg
    assert "secure.example.test" in msg


# --- credentials are bound to each request's host, not to the client ------------


def _secure_capabilities(advertised_url: str) -> str:
    """WMS capabilities served by the secure host but advertising `advertised_url` for GetMap."""
    return WMS_CAPABILITIES_130.replace("http://example.test/wms?", advertised_url)


def _get_map_secure(monkeypatch, advertised_url: str, getmap_url_re) -> requests.PreparedRequest:
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})
    responses.add(
        responses.GET, SECURE_WMS_URL_RE, body=_secure_capabilities(advertised_url),
        content_type="text/xml", status=200,
    )
    responses.add(
        responses.GET, getmap_url_re, body=PNG_1X1, content_type="image/png", status=200,
    )
    get_wms_map(
        SECURE_WMS_URL, layer="test:roads", bbox=(10.0, 50.0, 11.0, 51.0), crs="EPSG:4326",
    )
    return responses.calls[-1].request


@responses.activate
def test_no_credentials_to_a_foreign_host_advertised_in_capabilities(monkeypatch):
    # owslib sends GetMap to the URL the capabilities document advertises.
    getmap = _get_map_secure(
        monkeypatch, "https://evil.test/wms?", re.compile(r"^https://evil\.test/wms")
    )

    assert getmap.url.startswith("https://evil.test/")
    assert "Authorization" not in getmap.headers


@responses.activate
def test_no_credentials_on_http_downgrade_advertised_by_same_host(monkeypatch):
    getmap = _get_map_secure(
        monkeypatch,
        "http://secure.example.test/wms?",
        re.compile(r"^http://secure\.example\.test/wms"),
    )

    assert getmap.url.startswith("http://secure.example.test/")
    assert "Authorization" not in getmap.headers


@responses.activate
def test_credentials_sent_to_same_host_operation_url(monkeypatch):
    getmap = _get_map_secure(
        monkeypatch,
        "https://secure.example.test/ows?",
        re.compile(r"^https://secure\.example\.test/ows"),
    )

    assert getmap.headers["Authorization"] == _basic("u", "p")


def test_auth_not_reused_for_another_host(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"token": "s3cret"}})

    assert _header_for(SECURE_WMS_URL, request_url="https://evil.test/wms") is None


def test_parser_differential_url_gets_no_credentials(monkeypatch):
    # urlsplit says secure.example.test; requests/urllib3 actually connect to evil.test.
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})
    tricky = r"https://evil.test\@secure.example.test/wms"

    assert _header_for(tricky) is None


@responses.activate
def test_parser_differential_url_sends_no_header_on_the_wire(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})
    responses.add(
        responses.GET, re.compile(r"^https://evil\.test/"), body=WMS_CAPABILITIES_130,
        content_type="text/xml", status=200,
    )

    list_wms_layers(r"https://evil.test\@secure.example.test/wms")

    assert responses.calls[0].request.url.startswith("https://evil.test/")
    assert "Authorization" not in responses.calls[0].request.headers
