"""Pydantic models for mcp-ogc tool inputs and outputs.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class TileMatrixSetInfo(BaseModel):
    """A WMTS tile matrix set: a CRS plus a pyramid of zoom levels (tile matrices)."""

    identifier: str = Field(description="Tile matrix set identifier, used when requesting tiles.")
    crs: str = Field(description="CRS of the tile grid, e.g. 'urn:ogc:def:crs:EPSG::3857'.")
    tile_matrices: list[str] = Field(
        default_factory=list,
        description="Tile matrix (zoom level) identifiers, coarsest first as advertised.",
    )


class WMTSLayerInfo(BaseModel):
    """Discovery metadata for a single WMTS layer."""

    name: str = Field(description="Layer identifier, used when requesting tiles.")
    title: str = Field(description="Human-readable layer title.")
    abstract: str | None = Field(
        default=None, description="Free-text description, if the service provides one."
    )
    formats: list[str] = Field(
        default_factory=list, description="Image formats offered, e.g. 'image/png'."
    )
    styles: list[str] = Field(default_factory=list, description="Style identifiers offered.")
    default_style: str | None = Field(
        default=None, description="The style used when none is requested."
    )
    tile_matrix_sets: list[TileMatrixSetInfo] = Field(
        default_factory=list, description="Tile matrix sets this layer can be requested in."
    )
    bbox_wgs84: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Layer extent in WGS84 lon/lat as (minx, miny, maxx, maxy).",
    )


@dataclass(frozen=True)
class WMTSTile:
    """A fetched WMTS tile and where it sits in the tile matrix."""

    data: bytes
    mime_type: str
    tile_matrix_set: str
    tile_matrix: str
    row: int
    column: int


class AttributeFilter(BaseModel):
    """One attribute condition for query_wfs_features; several are AND-ed.

    Sent to the server as a standard OGC Filter Encoding 2.0 filter, so it works
    on any WFS 2.0 server (GeoServer, MapServer, deegree, QGIS Server, ...).
    """

    property: str = Field(min_length=1, description="Attribute (property) name to test.")
    op: Literal["=", "!=", "<", "<=", ">", ">=", "like", "is_null"] = Field(
        default="=",
        description=(
            "Comparison operator. 'like' matches a pattern where % is any run of "
            "characters and _ is one character; 'is_null' takes no value."
        ),
    )
    value: str | int | float | bool | None = Field(
        default=None, description="Value to compare against (omit for 'is_null')."
    )

    @model_validator(mode="after")
    def _value_required(self) -> AttributeFilter:
        if self.op != "is_null" and self.value is None:
            raise ValueError(f"op {self.op!r} needs a value")
        return self
