"""Error types for mcp-ogc.

These produce clear, agent-friendly messages instead of leaking raw owslib /
requests tracebacks to the LLM client.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit


class OGCError(Exception):
    """A user-actionable error talking to an OGC service.

    Raised for things an agent can fix by changing its input — an unreachable
    endpoint, an unknown layer, an unknown feature type — with a message that
    says what went wrong and, where possible, what the valid options are.
    """


@contextmanager
def wrap_connection_errors(url: str) -> Iterator[None]:
    """Turn low-level connection failures into a clear OGCError.

    owslib raises `requests` exceptions (and their underlying urllib3 errors)
    when an endpoint is unreachable. Those surface to an LLM client as noisy
    tracebacks; this re-raises them as a single readable message naming the URL.
    """
    try:
        yield
    except OGCError:
        raise
    except Exception as exc:  # noqa: BLE001 — deliberately broad: any transport failure
        name = type(exc).__name__
        # owslib has several unrelated ServiceException classes (util, wfs200,
        # wmts); openURL raises one for HTTP 400/401/403 with only the body.
        if name == "ServiceException":
            raise OGCError(_rejected_message(url, exc)) from exc
        if any(
            hint in name
            for hint in ("Connection", "Timeout", "URLError", "HTTPError", "SSLError")
        ):
            raise OGCError(
                f"Could not reach the OGC service at {url}: {exc}"
            ) from exc
        raise


def _rejected_message(url: str, exc: Exception) -> str:
    # Imported here: mcp_ogc.auth imports this module.
    from mcp_ogc.auth import AUTH_ENV_VAR, auth_for_url

    detail = " ".join(str(exc).split())[:300] or "(no details)"
    host = urlsplit(url).hostname or url
    try:
        has_credentials = auth_for_url(url) is not None
    except OGCError:
        has_credentials = True
    hint = (
        f"check the credentials configured for host {host!r} in {AUTH_ENV_VAR}"
        if has_credentials
        else f"if this endpoint requires authentication, configure credentials for "
        f"host {host!r} in {AUTH_ENV_VAR}"
    )
    return f"The OGC service at {url} rejected the request: {detail} ({hint})."

