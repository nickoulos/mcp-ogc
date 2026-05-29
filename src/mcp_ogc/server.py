"""mcp-ogc MCP server entry point.

Exposes the OGC tools as Model Context Protocol tools via FastMCP.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from mcp_ogc.models import LayerInfo
from mcp_ogc.tools.wfs import query_wfs_features as _query_wfs_features
from mcp_ogc.tools.wms import get_wms_map as _get_wms_map
from mcp_ogc.tools.wms import list_wms_layers as _list_wms_layers

mcp = FastMCP("mcp-ogc")


@mcp.tool()
def list_wms_layers(wms_url: str) -> list[LayerInfo]:
    """Discover the layers a WMS endpoint exposes.

    Args:
        wms_url: Base URL of the WMS service.

    Returns:
        One LayerInfo per named layer (name, title, abstract, CRS options, bbox).
    """
    return _list_wms_layers(wms_url)


@mcp.tool()
def get_wms_map(
    wms_url: str,
    layer: str,
    bbox: tuple[float, float, float, float],
    crs: str = "EPSG:3857",
    width: int = 800,
    height: int = 600,
    image_format: str = "image/png",
    time: str | None = None,
) -> Image:
    """Fetch a rendered map image from a WMS endpoint.

    Args:
        wms_url: Base URL of the WMS service.
        layer: Layer name (from list_wms_layers).
        bbox: (minx, miny, maxx, maxy) in the requested CRS.
        crs: Coordinate reference system (default EPSG:3857, Web Mercator).
        width: Output image width in pixels.
        height: Output image height in pixels.
        image_format: MIME type of the image (default "image/png").
        time: Optional ISO 8601 time value for time-aware layers.

    Returns:
        The rendered map as an image the client can display.
    """
    data = _get_wms_map(
        wms_url=wms_url,
        layer=layer,
        bbox=bbox,
        crs=crs,
        width=width,
        height=height,
        image_format=image_format,
        time=time,
    )
    # image_format is a MIME type like "image/png"; FastMCP wants the subtype.
    subtype = image_format.split("/")[-1] if "/" in image_format else image_format
    return Image(data=data, format=subtype)


@mcp.tool()
def query_wfs_features(
    wfs_url: str,
    type_name: str,
    bbox: tuple[float, float, float, float] | None = None,
    max_features: int = 100,
) -> dict[str, Any]:
    """Query vector features from a WFS endpoint as GeoJSON.

    Args:
        wfs_url: Base URL of the WFS service.
        type_name: Feature type to query (from the service's capabilities).
        bbox: Optional bounding box filter (minx, miny, maxx, maxy).
        max_features: Maximum number of features to return.

    Returns:
        A GeoJSON FeatureCollection as a dict.
    """
    return _query_wfs_features(
        wfs_url=wfs_url,
        type_name=type_name,
        bbox=bbox,
        max_features=max_features,
    )


def main() -> None:
    """Console-script entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
