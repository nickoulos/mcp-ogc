"""WMS (Web Map Service) tools.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from owslib.wms import WebMapService

from mcp_ogc.models import LayerInfo


def list_wms_layers(wms_url: str) -> list[LayerInfo]:
    """Discover available layers on a WMS endpoint.

    Args:
        wms_url: Base URL of the WMS service, e.g.
            "https://kartor.eskilstuna.se/geoserver/wms". owslib appends the
            GetCapabilities request parameters automatically.

    Returns:
        One LayerInfo per named layer advertised by the service.
    """
    wms = WebMapService(wms_url, version="1.3.0")

    layers: list[LayerInfo] = []
    for key in wms.contents:
        layer = wms[key]

        # Skip container/group layers that have no requestable name.
        name = getattr(layer, "name", None) or getattr(layer, "id", None)
        if not name:
            continue

        bbox_wgs84 = None
        raw_bbox = getattr(layer, "boundingBoxWGS84", None)
        if raw_bbox and len(raw_bbox) >= 4:
            bbox_wgs84 = (
                float(raw_bbox[0]),
                float(raw_bbox[1]),
                float(raw_bbox[2]),
                float(raw_bbox[3]),
            )

        layers.append(
            LayerInfo(
                name=name,
                title=getattr(layer, "title", None) or name,
                abstract=getattr(layer, "abstract", None) or None,
                crs_options=list(getattr(layer, "crsOptions", []) or []),
                bbox_wgs84=bbox_wgs84,
            )
        )

    return layers
