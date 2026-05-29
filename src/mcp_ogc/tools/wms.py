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


def get_wms_map(
    wms_url: str,
    layer: str,
    bbox: tuple[float, float, float, float],
    crs: str = "EPSG:3857",
    width: int = 800,
    height: int = 600,
    image_format: str = "image/png",
    time: str | None = None,
) -> bytes:
    """Fetch a rendered map image from a WMS endpoint.

    Args:
        wms_url: Base URL of the WMS service.
        layer: Layer name (as returned by list_wms_layers).
        bbox: (minx, miny, maxx, maxy) in the requested CRS.
        crs: Coordinate reference system (default Web Mercator, EPSG:3857).
        width: Output image width in pixels.
        height: Output image height in pixels.
        image_format: MIME type of the image (default "image/png").
        time: Optional ISO 8601 time value for time-aware layers
            (e.g. historical orthophoto archives).

    Returns:
        Raw image bytes (PNG by default).
    """
    wms = WebMapService(wms_url, version="1.3.0")

    # owslib's getmap() names the coordinate system parameter `srs`, even for
    # WMS 1.3.0 where the protocol calls it CRS. We expose `crs` publicly and
    # translate here.
    getmap_kwargs: dict = {
        "layers": [layer],
        "srs": crs,
        "bbox": bbox,
        "size": (width, height),
        "format": image_format,
    }
    if time is not None:
        getmap_kwargs["time"] = time

    response = wms.getmap(**getmap_kwargs)
    return response.read()
