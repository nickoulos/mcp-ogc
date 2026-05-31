"""Error types for mcp-ogc.

These produce clear, agent-friendly messages instead of leaking raw owslib /
requests tracebacks to the LLM client.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager


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
        if any(
            hint in name
            for hint in ("Connection", "Timeout", "URLError", "HTTPError", "SSLError")
        ):
            raise OGCError(
                f"Could not reach the OGC service at {url}: {exc}"
            ) from exc
        raise

