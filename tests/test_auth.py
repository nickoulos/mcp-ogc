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
from mcp_ogc.tools.wms import list_wms_layers
from tests.fixtures import (
    WFS_CAPABILITIES_200,
    WFS_GEOJSON_RESPONSE,
    WMS_CAPABILITIES_130,
)

SECURE_WMS_URL = "https://secure.example.test/wms"
SECURE_WMS_URL_RE = re.compile(r"^https://secure\.example\.test/wms")


def _set_auth(monkeypatch, mapping) -> None:
    monkeypatch.setenv(AUTH_ENV_VAR, json.dumps(mapping))


def _apply(auth) -> requests.PreparedRequest:
    """Run an owslib Authentication through requests, as owslib's openURL does."""
    request = requests.Request("GET", SECURE_WMS_URL)
    if auth.username and auth.password:
        request.auth = (auth.username, auth.password)
    else:
        request.auth = auth.auth_delegate
    return request.prepare()


def test_no_env_means_no_auth(monkeypatch):
    monkeypatch.delenv(AUTH_ENV_VAR, raising=False)

    assert auth_for_url(SECURE_WMS_URL) is None


def test_basic_credentials_for_matching_host(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})

    auth = auth_for_url(SECURE_WMS_URL)

    assert auth.username == "u"
    assert auth.password == "p"


def test_host_match_is_case_insensitive(monkeypatch):
    _set_auth(monkeypatch, {"Secure.Example.TEST": {"username": "u", "password": "p"}})

    assert auth_for_url("https://SECURE.example.test/wms").username == "u"


def test_host_with_port_key_matches_only_that_port(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test:8443": {"username": "u", "password": "p"}})

    assert auth_for_url("https://secure.example.test:8443/wms").username == "u"
    assert auth_for_url("https://secure.example.test/wms") is None


def test_credentials_never_sent_to_other_hosts(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"username": "u", "password": "p"}})

    assert auth_for_url("https://evil.example.test/wms") is None
    # A lookalike host that merely *contains* the configured name must not match.
    assert auth_for_url("https://secure.example.test.evil.test/wms") is None


def test_bearer_token_sets_authorization_header(monkeypatch):
    _set_auth(monkeypatch, {"secure.example.test": {"token": "s3cret"}})

    prepared = _apply(auth_for_url(SECURE_WMS_URL))

    assert prepared.headers["Authorization"] == "Bearer s3cret"


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

    assert auth_for_url("http://secure.example.test/wms").username == "u"


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

    expected = "Basic " + base64.b64encode(b"u:p").decode()
    assert responses.calls[0].request.headers["Authorization"] == expected


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
