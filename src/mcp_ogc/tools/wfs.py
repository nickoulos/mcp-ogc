"""WFS (Web Feature Service) tools.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
from typing import Any

from mcp_ogc.errors import OGCError, wrap_connection_errors
from mcp_ogc.services import call_with_retry, open_wfs


def query_wfs_features(
    wfs_url: str,
    type_name: str,
    bbox: tuple[float, float, float, float] | None = None,
    max_features: int = 100,
) -> dict[str, Any]:
    """Query vector features from a WFS endpoint as GeoJSON.

    Args:
        wfs_url: Base URL of the WFS service.
        type_name: Feature type to query (as advertised by the service's
            DescribeFeatureType / capabilities).
        bbox: Optional bounding box filter (minx, miny, maxx, maxy) in the
            feature type's coordinates.
        max_features: Maximum number of features to return (default 100).

    Returns:
        A GeoJSON FeatureCollection as a dict.

    Raises:
        OGCError: if the endpoint cannot be reached or `type_name` is not one of
            the feature types the service advertises.

    Note:
        Attribute filtering (e.g. CQL) is intentionally out of scope for
        v0.1.0; see the roadmap. Only spatial (bbox) filtering is supported here.
    """
    with wrap_connection_errors(wfs_url):
        wfs = open_wfs(wfs_url)

        if type_name not in wfs.contents:
            available = ", ".join(sorted(wfs.contents)) or "(none advertised)"
            raise OGCError(
                f"Unknown WFS feature type {type_name!r}. "
                f"Available feature types: {available}"
            )

        response = call_with_retry(
            lambda: wfs.getfeature(
                typename=[type_name],
                bbox=bbox,
                maxfeatures=max_features,
                outputFormat="application/json",
            )
        )

    return json.loads(response.read())
