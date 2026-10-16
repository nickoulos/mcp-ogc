"""WMTS (Web Map Tile Service) tools.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import math

from owslib.crs import Crs

from mcp_ogc.errors import OGCError, wrap_connection_errors
from mcp_ogc.models import TileMatrixSetInfo, WMTSLayerInfo, WMTSTile
from mcp_ogc.services import call_with_retry, open_wmts

# OGC WMTS 1.0.0: a "standardized rendering pixel" is 0.28 mm, and degree-based
# CRS use the equatorial circumference of the WGS84 ellipsoid / 360 m per unit.
_PIXEL_SIZE_M = 0.28e-3
_METERS_PER_DEGREE = 2 * math.pi * 6378137 / 360

# Geographic (degree-based) CRS commonly used for tile grids.
_GEOGRAPHIC_CODES = {"4326", "4258", "4269", "4283", "4612", "4674", "4167", "4619", "CRS84"}


def list_wmts_layers(wmts_url: str) -> list[WMTSLayerInfo]:
    """Discover the layers a WMTS endpoint exposes, with their tile matrix sets.

    Args:
        wmts_url: Base URL of the WMTS service (KVP endpoint).

    Returns:
        One WMTSLayerInfo per layer: formats, styles and the tile matrix sets
        (CRS + zoom-level identifiers) it can be requested in.

    Raises:
        OGCError: if the endpoint cannot be reached.
    """
    with wrap_connection_errors(wmts_url):
        wmts = open_wmts(wmts_url)

    layers: list[WMTSLayerInfo] = []
    for layer in wmts.contents.values():
        tile_matrix_sets = []
        for identifier in layer.tilematrixsetlinks:
            tms = wmts.tilematrixsets.get(identifier)
            if tms is not None:
                tile_matrix_sets.append(
                    TileMatrixSetInfo(
                        identifier=identifier, crs=tms.crs, tile_matrices=list(tms.tilematrix)
                    )
                )
        raw_bbox = getattr(layer, "boundingBoxWGS84", None)
        layers.append(
            WMTSLayerInfo(
                name=layer.id,
                title=getattr(layer, "title", None) or layer.id,
                abstract=getattr(layer, "abstract", None) or None,
                formats=list(layer.formats),
                styles=list(layer.styles),
                default_style=_default_style(layer),
                tile_matrix_sets=tile_matrix_sets,
                bbox_wgs84=tuple(float(v) for v in raw_bbox[:4]) if raw_bbox else None,
            )
        )
    return layers


def get_wmts_tile(
    wmts_url: str,
    layer: str,
    tile_matrix_set: str,
    tile_matrix: str,
    row: int | None = None,
    column: int | None = None,
    point: tuple[float, float] | None = None,
    style: str | None = None,
    image_format: str | None = None,
) -> WMTSTile:
    """Fetch one tile from a WMTS endpoint.

    Locate the tile either by ``row`` + ``column`` or by ``point``, not both.

    Args:
        wmts_url: Base URL of the WMTS service (KVP endpoint).
        layer: Layer identifier (from list_wmts_layers).
        tile_matrix_set: Tile matrix set identifier linked to the layer.
        tile_matrix: Tile matrix (zoom level) identifier within the set.
        row: Tile row, 0 at the top.
        column: Tile column, 0 at the left.
        point: (x, y) in the tile matrix set's CRS — ALWAYS easting-first
            (lon/lat for degree-based CRS), even for northing-first CRS such as
            EPSG:3006 or EPSG:4326. The tile containing it is computed; the
            CRS's axis order in the capabilities is handled here.
        style: Style identifier; defaults to the layer's default style.
        image_format: MIME type; defaults to image/png when offered, otherwise
            the layer's first format.

    Returns:
        The tile bytes plus its MIME type and resolved row/column.

    Raises:
        OGCError: if the endpoint cannot be reached, or any argument does not
            match what the service advertises (the message lists valid options).
    """
    with wrap_connection_errors(wmts_url):
        wmts = open_wmts(wmts_url)

        if layer not in wmts.contents:
            raise OGCError(
                f"Unknown WMTS layer {layer!r}. Available layers: {_options(wmts.contents)}"
            )
        content = wmts.contents[layer]

        if tile_matrix_set not in content.tilematrixsetlinks:
            raise OGCError(
                f"Layer {layer!r} is not offered in tile matrix set {tile_matrix_set!r}. "
                f"Available tile matrix sets: {_options(content.tilematrixsetlinks)}"
            )
        tms = wmts.tilematrixsets[tile_matrix_set]

        if tile_matrix not in tms.tilematrix:
            raise OGCError(
                f"Unknown tile matrix {tile_matrix!r} in {tile_matrix_set!r}. "
                f"Available tile matrices: {_options(tms.tilematrix)}"
            )
        matrix = tms.tilematrix[tile_matrix]

        if point is not None and (row is not None or column is not None):
            raise OGCError("Pass either row and column, or point — not both.")
        if point is not None:
            row, column = _point_to_tile(matrix, tms.crs, point)
            if not (0 <= row < matrix.matrixheight and 0 <= column < matrix.matrixwidth):
                raise OGCError(
                    f"Point {point} is outside tile matrix {tile_matrix!r} of "
                    f"{tile_matrix_set!r} ({tms.crs}). Check that it is in that CRS and "
                    f"easting-first (lon/lat for degree-based CRS)."
                )
        elif row is None or column is None:
            raise OGCError("Pass both row and column, or a point to locate the tile.")
        _check_index("row", row, matrix.matrixheight, tile_matrix)
        _check_index("column", column, matrix.matrixwidth, tile_matrix)

        image_format = _resolve_format(content, image_format)
        style = _resolve_style(content, style)

        response = call_with_retry(
            lambda: wmts.gettile(
                layer=layer,
                tilematrixset=tile_matrix_set,
                tilematrix=tile_matrix,
                row=row,
                column=column,
                format=image_format,
                style=style,
            )
        )
        data = response.read()

    return WMTSTile(
        data=data,
        mime_type=image_format,
        tile_matrix_set=tile_matrix_set,
        tile_matrix=tile_matrix,
        row=row,
        column=column,
    )


def _options(names) -> str:
    return ", ".join(names) or "(none advertised)"


def _default_style(content) -> str | None:
    for name, style in content.styles.items():
        if style.get("isDefault"):
            return name
    return next(iter(content.styles), None)


def _resolve_style(content, style: str | None) -> str:
    if style is None:
        return _default_style(content) or "default"
    if content.styles and style not in content.styles:
        raise OGCError(f"Unknown style {style!r}. Available styles: {_options(content.styles)}")
    return style


def _resolve_format(content, image_format: str | None) -> str:
    if image_format is None:
        if not content.formats or "image/png" in content.formats:
            return "image/png"
        return content.formats[0]
    if content.formats and image_format not in content.formats:
        raise OGCError(
            f"Unsupported image format {image_format!r}. "
            f"Available formats: {_options(content.formats)}"
        )
    return image_format


def _check_index(name: str, value: int, size: int, tile_matrix: str) -> None:
    if not 0 <= value < size:
        raise OGCError(
            f"Tile {name} {value} is outside tile matrix {tile_matrix!r} "
            f"(valid {name}s: 0 to {size - 1})."
        )


def _point_to_tile(matrix, crs_name: str, point: tuple[float, float]) -> tuple[int, int]:
    """Row/column of the tile containing ``point`` (OGC WMTS 1.0.0, Annex H).

    TopLeftCorner is written in the CRS's own axis order, so for northing-first
    CRS (EPSG:3006, EPSG:4326, ...) it is (y, x) and must be swapped. A wrong
    order does not fail loudly; it just picks a different tile.
    """
    crs = Crs(crs_name)
    first, second = matrix.topleftcorner
    left, top = (second, first) if crs.axisorder == "yx" else (first, second)
    meters_per_unit = _METERS_PER_DEGREE if str(crs.code) in _GEOGRAPHIC_CODES else 1.0
    pixel_span = matrix.scaledenominator * _PIXEL_SIZE_M / meters_per_unit
    x, y = point
    column = math.floor((x - left) / (matrix.tilewidth * pixel_span))
    row = math.floor((top - y) / (matrix.tileheight * pixel_span))
    return row, column
