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

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlsplit

import requests
from owslib.util import Authentication

from mcp_ogc.errors import OGCError

AUTH_ENV_VAR = "MCP_OGC_AUTH"


class _BearerAuth(requests.auth.AuthBase):
    """Send a static token as ``Authorization: Bearer <token>``."""

    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        request.headers["Authorization"] = f"Bearer {self._token}"
        return request

    def __repr__(self) -> str:
        return "_BearerAuth(token=***)"


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

    Raises:
        OGCError: if the configuration is malformed, or if credentials exist for
            the host but the URL is plain http without an explicit opt-in.
    """
    config = _load_config()
    if not config:
        return None

    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    entry = config.get(f"{host}:{parts.port}") if parts.port is not None else None
    if entry is None:
        entry = config.get(host)
    if entry is None:
        return None

    if parts.scheme != "https" and not entry.get("allow_insecure_http", False):
        raise OGCError(
            f"Credentials are configured for {host} in {AUTH_ENV_VAR}, but {url} uses "
            f"plain {parts.scheme}; refusing to send them unencrypted. Use the https URL, "
            f'or set "allow_insecure_http": true for this host.'
        )

    if entry.get("token"):
        return Authentication(auth_delegate=_BearerAuth(entry["token"]))
    if entry.get("username") and entry.get("password"):
        return Authentication(username=entry["username"], password=entry["password"])
    raise OGCError(
        f'The {AUTH_ENV_VAR} entry for {host} needs either "username" and "password", '
        f'or "token".'
    )
