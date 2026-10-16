"""Open owslib service clients with the shared per-host configuration.

Every tool goes through here, so authentication, the capabilities cache and
retry/backoff are configured in one place. Cache and retry are opt-in via
environment variables and off by default:

- ``MCP_OGC_CACHE_TTL``: seconds to keep parsed GetCapabilities documents in
  memory (default 0 = no cache).
- ``MCP_OGC_RETRIES``: retries for transient failures — connection errors,
  timeouts, HTTP 5xx (default 0). Client errors (4xx) are never retried.
- ``MCP_OGC_RETRY_BACKOFF``: base delay in seconds; attempt n waits
  ``base * 2**n`` (default 0.5).

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import hashlib
import math
import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import requests
from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService
from owslib.wmts import WebMapTileService

from mcp_ogc.auth import AUTH_ENV_VAR, auth_for_url
from mcp_ogc.errors import OGCError

CACHE_TTL_ENV_VAR = "MCP_OGC_CACHE_TTL"
RETRIES_ENV_VAR = "MCP_OGC_RETRIES"
RETRY_BACKOFF_ENV_VAR = "MCP_OGC_RETRY_BACKOFF"

_CACHE_MAX_ENTRIES = 64

# Indirections so tests can control time without real sleeping.
_now = time.monotonic
_sleep = time.sleep

_cache: OrderedDict[tuple[str, str, str], tuple[float, Any]] = OrderedDict()
_cache_lock = threading.Lock()


def clear_cache() -> None:
    """Drop every cached capabilities document."""
    with _cache_lock:
        _cache.clear()


def _env_number[T: (int, float)](name: str, default: T, cast: Callable[[str], T]) -> T:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = cast(raw)
    except ValueError:
        value = None
    if value is None or not math.isfinite(value) or value < 0:
        raise OGCError(f"{name} must be a non-negative number, got {raw!r}.")
    return value


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code >= 500
    return False


def call_with_retry[T](fn: Callable[[], T]) -> T:
    """Call ``fn``, retrying transient failures per MCP_OGC_RETRIES / _BACKOFF.

    owslib makes module-level ``requests`` calls with no session to attach a
    retry adapter to, so retries wrap whole owslib operations instead.
    """
    retries = _env_number(RETRIES_ENV_VAR, 0, int)
    backoff = _env_number(RETRY_BACKOFF_ENV_VAR, 0.5, float)
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            if attempt >= retries or not _is_transient(exc):
                raise
            _sleep(backoff * 2**attempt)
            attempt += 1


def _auth_fingerprint() -> str:
    # Different credentials may see different capabilities, so they must not
    # share cache entries. Hash rather than keep the raw secret in the key.
    return hashlib.sha256(os.environ.get(AUTH_ENV_VAR, "").encode()).hexdigest()


def _capabilities[T](kind: str, url: str, fetch: Callable[[], T]) -> T:
    ttl = _env_number(CACHE_TTL_ENV_VAR, 0.0, float)
    if ttl <= 0:
        return call_with_retry(fetch)

    key = (kind, url, _auth_fingerprint())
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] > _now():
            _cache.move_to_end(key)
            return hit[1]

    service = call_with_retry(fetch)  # failures raise, so they are never cached
    with _cache_lock:
        _cache[key] = (_now() + ttl, service)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return service


def open_wms(url: str):
    """Fetch and parse a WMS 1.3.0 GetCapabilities document."""
    return _capabilities(
        "wms", url, lambda: WebMapService(url, version="1.3.0", auth=auth_for_url(url))
    )


def open_wfs(url: str):
    """Fetch and parse a WFS 2.0.0 GetCapabilities document."""
    return _capabilities(
        "wfs", url, lambda: WebFeatureService(url, version="2.0.0", auth=auth_for_url(url))
    )


def open_wmts(url: str):
    """Fetch and parse a WMTS 1.0.0 GetCapabilities document."""
    return _capabilities(
        "wmts", url, lambda: WebMapTileService(url, version="1.0.0", auth=auth_for_url(url))
    )
