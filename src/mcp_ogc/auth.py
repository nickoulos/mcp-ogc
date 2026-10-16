"""Per-host credentials for protected OGC endpoints.

Credentials come from the ``MCP_OGC_AUTH`` environment variable, never from
tool arguments, so the LLM never sees them. The variable holds a JSON object
keyed by host name (optionally ``host:port``)::

    {
      "karta.example.se": {"username": "alice", "password": "..."},
      "tiles.example.se:8443": {"token": "..."}
    }

Each entry is sent only to its own host, so an agent cannot leak credentials by
pointing a tool at another URL. Credentials are only sent over https unless the
entry sets ``"allow_insecure_http": true``. Nothing here logs or persists them.

The host check runs on every outgoing request, not once per client: owslib
sends GetMap/GetFeature to whatever URLs the capabilities document advertises,
which may be another host or a plain-http variant of the same one.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlsplit

import requests
from owslib.util import Authentication
from urllib3.util import parse_url

from mcp_ogc.errors import OGCError

AUTH_ENV_VAR = "MCP_OGC_AUTH"

_DEFAULT_PORTS = {"http": 80, "https": 443}


class _BearerAuth(requests.auth.AuthBase):
    """Send a static token as ``Authorization: Bearer <token>``."""

    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self._token}"
        return request

    def __repr__(self) -> str:
        return "_BearerAuth(token=***)"


def _endpoint(url: str) -> tuple[str, str, int | None] | None:
    """Return (scheme, host, port) for ``url``, or None if it is ambiguous.

    The host comes from urllib3's parser, which is what requests uses to decide
    where to connect. If the stdlib parser disagrees (e.g. ``https://a\\@b/``,
    which urlsplit reads as host b but requests connects to a), the URL is
    treated as unknown so no credentials are attached.
    """
    try:
        parsed = parse_url(url)
        stdlib_host = urlsplit(url).hostname
    except ValueError:
        return None
    host = (parsed.host or "").strip("[]").lower()
    if not host or host != (stdlib_host or "").lower():
        return None
    scheme = (parsed.scheme or "").lower()
    return scheme, host, parsed.port or _DEFAULT_PORTS.get(scheme)


class _HostBoundAuth(requests.auth.AuthBase):
    """Apply ``inner`` only to requests whose own URL is the configured host.

    ``port`` is None when the config key had no port (any port on the host).
    """

    def __init__(
        self,
        host: str,
        port: int | None,
        allow_insecure_http: bool,
        inner: requests.auth.AuthBase,
    ) -> None:
        self._host = host
        self._port = port
        self._allow_insecure_http = allow_insecure_http
        self._inner = inner

    def matches(self, url: str) -> bool:
        endpoint = _endpoint(url)
        if endpoint is None:
            return False
        scheme, host, port = endpoint
        if host != self._host:
            return False
        if self._port is not None and port != self._port:
            return False
        return scheme == "https" or (scheme == "http" and self._allow_insecure_http)

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        if self.matches(request.url or ""):
            return self._inner(request)
        return request

    def __repr__(self) -> str:
        return f"_HostBoundAuth(host={self._host!r}, port={self._port!r}, credentials=***)"


def _load_config() -> dict[str, dict[str, Any]]:
    raw = os.environ.get(AUTH_ENV_VAR)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # `from None`: the decode error carries the raw document, i.e. secrets.
        raise OGCError(f"{AUTH_ENV_VAR} is not valid JSON.") from None
    if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
        raise OGCError(
            f"{AUTH_ENV_VAR} must be a JSON object mapping host names to credential objects."
        )
    return {host.lower(): entry for host, entry in data.items()}


def auth_for_url(url: str) -> Authentication | None:
    """Return the owslib Authentication configured for ``url``'s host, if any.

    The returned Authentication only ever adds credentials to requests that go
    to that same host (see _HostBoundAuth), whatever URLs owslib later uses.

    Raises:
        OGCError: if the configuration is malformed, or if credentials exist for
            the host but the URL is plain http without an explicit opt-in.
    """
    config = _load_config()
    if not config:
        return None

    endpoint = _endpoint(url)
    if endpoint is None:
        return None
    scheme, host, port = endpoint
    key_port: int | None = port
    entry = config.get(f"{host}:{port}")
    if entry is None:
        key_port = None
        entry = config.get(host)
    if entry is None:
        return None

    allow_insecure_http = bool(entry.get("allow_insecure_http", False))
    if scheme != "https" and not allow_insecure_http:
        raise OGCError(
            f"Credentials are configured for {host} in {AUTH_ENV_VAR}, but {url} uses "
            f"plain {scheme}; refusing to send them unencrypted. Use the https URL, "
            f'or set "allow_insecure_http": true for this host.'
        )

    inner: requests.auth.AuthBase
    if entry.get("token"):
        inner = _BearerAuth(entry["token"])
    elif entry.get("username") and entry.get("password"):
        inner = requests.auth.HTTPBasicAuth(entry["username"], entry["password"])
    else:
        raise OGCError(
            f'The {AUTH_ENV_VAR} entry for {host} needs either "username" and "password", '
            f'or "token".'
        )
    # Passed as a delegate (never as owslib username/password) so the host check
    # applies to Basic credentials too.
    return Authentication(
        auth_delegate=_HostBoundAuth(host, key_port, allow_insecure_http, inner)
    )
