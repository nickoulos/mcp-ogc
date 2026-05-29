"""Pydantic models for mcp-ogc tool inputs and outputs.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LayerInfo(BaseModel):
    """Discovery metadata for a single WMS layer.

    Fields map directly to owslib ContentMetadata attributes returned by
    WebMapService(...).contents.
    """

    name: str = Field(description="Layer identifier, used when requesting maps.")
    title: str = Field(description="Human-readable layer title.")
    abstract: str | None = Field(
        default=None, description="Free-text description, if the service provides one."
    )
    crs_options: list[str] = Field(
        default_factory=list,
        description="Coordinate reference systems the layer supports (e.g. 'EPSG:3857').",
    )
    bbox_wgs84: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Layer extent in WGS84 lon/lat as (minx, miny, maxx, maxy).",
    )
