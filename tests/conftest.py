"""Shared test setup.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import pytest

from mcp_ogc import services


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch):
    """Keep tests hermetic: ignore the developer's own env config, start with an empty cache."""
    for name in (
        "MCP_OGC_AUTH",
        "MCP_OGC_CACHE_TTL",
        "MCP_OGC_RETRIES",
        "MCP_OGC_RETRY_BACKOFF",
    ):
        monkeypatch.delenv(name, raising=False)
    services.clear_cache()
    yield
    services.clear_cache()
