"""Open owslib service clients with the shared per-host configuration.

Every tool goes through here, so authentication (and anything else that applies
to all endpoints) is configured in one place.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from owslib.wfs import WebFeatureService
from owslib.wms import WebMapService

from mcp_ogc.auth import auth_for_url


def open_wms(url: str):
    """Fetch and parse a WMS 1.3.0 GetCapabilities document."""
    return WebMapService(url, version="1.3.0", auth=auth_for_url(url))


def open_wfs(url: str):
    """Fetch and parse a WFS 2.0.0 GetCapabilities document."""
    return WebFeatureService(url, version="2.0.0", auth=auth_for_url(url))
