"""Unit tests for the WMTS tools.

Hermetic — HTTP mocked with `responses`. Expected tiles for `point` lookups are
worked out by hand from the OGC WMTS 1.0.0 formula (Annex H):
    pixel_span = scale_denominator * 0.28e-3 / meters_per_unit
    column = floor((x - top_left_x) / (tile_width * pixel_span))
    row    = floor((top_left_y - y) / (tile_height * pixel_span))

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import re
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from mcp_ogc.errors import OGCError
from mcp_ogc.models import WMTSLayerInfo
from mcp_ogc.tools.wmts import get_wmts_tile, list_wmts_layers
from tests.fixtures import PNG_1X1, WMTS_CAPABILITIES_100

WMTS_URL = "http://example.test/wmts"
WMTS_URL_RE = re.compile(r"^http://example\.test/wmts")


def _register_capabilities() -> None:
    responses.add(
        responses.GET, WMTS_URL_RE, body=WMTS_CAPABILITIES_100,
        content_type="text/xml", status=200,
    )


def _register_tile() -> None:
    responses.add(
        responses.GET, WMTS_URL_RE, body=PNG_1X1, content_type="image/png", status=200,
    )


def _tile_params() -> dict[str, str]:
    query = parse_qs(urlparse(responses.calls[-1].request.url).query)
    return {k.lower(): v[0] for k, v in query.items()}


def _get_tile(**kwargs):
    _register_capabilities()
    _register_tile()
    return get_wmts_tile(WMTS_URL, layer="test:basemap", **kwargs)


# --- list_wmts_layers ---------------------------------------------------------


@responses.activate
def test_list_wmts_layers_maps_metadata():
    _register_capabilities()

    layers = list_wmts_layers(WMTS_URL)

    assert len(layers) == 1
    layer = layers[0]
    assert isinstance(layer, WMTSLayerInfo)
    assert layer.name == "test:basemap"
    assert layer.title == "Basemap"
    assert layer.abstract == "Test basemap."
    assert layer.formats == ["image/jpeg", "image/png"]
    assert layer.styles == ["night", "default"]
    assert layer.default_style == "default"
    assert layer.bbox_wgs84 == (10.0, 50.0, 11.0, 51.0)


@responses.activate
def test_list_wmts_layers_describes_linked_tile_matrix_sets():
    _register_capabilities()

    sets = {s.identifier: s for s in list_wmts_layers(WMTS_URL)[0].tile_matrix_sets}

    assert set(sets) == {"WebMercatorQuad", "sweref99tm", "wgs84"}
    assert sets["WebMercatorQuad"].crs == "urn:ogc:def:crs:EPSG::3857"
    assert sets["WebMercatorQuad"].tile_matrices == ["0", "1"]


# --- get_wmts_tile by row/column ----------------------------------------------


@responses.activate
def test_get_wmts_tile_returns_image_bytes_and_location():
    tile = _get_tile(tile_matrix_set="WebMercatorQuad", tile_matrix="1", row=1, column=0)

    assert tile.data[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tile.tile_matrix, tile.row, tile.column) == ("1", 1, 0)


@responses.activate
def test_get_wmts_tile_sends_kvp_gettile_request():
    _get_tile(tile_matrix_set="WebMercatorQuad", tile_matrix="1", row=1, column=0)

    params = _tile_params()
    assert params["request"] == "GetTile"
    assert params["layer"] == "test:basemap"
    assert params["tilematrixset"] == "WebMercatorQuad"
    assert params["tilematrix"] == "1"
    assert params["tilerow"] == "1"
    assert params["tilecol"] == "0"


@responses.activate
def test_get_wmts_tile_defaults_to_png_and_default_style():
    tile = _get_tile(tile_matrix_set="WebMercatorQuad", tile_matrix="0", row=0, column=0)

    params = _tile_params()
    # PNG is preferred when offered, even though JPEG is listed first.
    assert params["format"] == "image/png"
    assert tile.mime_type == "image/png"
    # The style flagged isDefault, not merely the first one listed.
    assert params["style"] == "default"


@responses.activate
def test_get_wmts_tile_honours_explicit_format_and_style():
    tile = _get_tile(
        tile_matrix_set="WebMercatorQuad", tile_matrix="0", row=0, column=0,
        image_format="image/jpeg", style="night",
    )

    params = _tile_params()
    assert params["format"] == "image/jpeg"
    assert params["style"] == "night"
    assert tile.mime_type == "image/jpeg"


# --- get_wmts_tile by point ---------------------------------------------------


@responses.activate
def test_point_to_tile_in_web_mercator():
    # Just east of the origin and just south of the equator, zoom 1 (2x2).
    tile = _get_tile(tile_matrix_set="WebMercatorQuad", tile_matrix="1", point=(1000.0, -1000.0))

    assert (tile.row, tile.column) == (1, 1)
    assert _tile_params()["tilerow"] == "1"
    assert _tile_params()["tilecol"] == "1"


@responses.activate
def test_point_to_tile_swaps_northing_first_top_left_corner():
    # EPSG:3006 TopLeftCorner is "N E" = (8500000, -1200000); tile span 1048576 m.
    # point is easting-first: column = (619000 + 1200000) // 1048576 = 1,
    # row = (8500000 - 5000000) // 1048576 = 3. Without the swap: out of range.
    tile = _get_tile(tile_matrix_set="sweref99tm", tile_matrix="0", point=(619000.0, 5000000.0))

    assert (tile.row, tile.column) == (3, 1)


@responses.activate
def test_point_to_tile_in_degrees_uses_meters_per_degree():
    # EPSG:4326: TopLeftCorner "lat lon" = (90, -180); one tile spans 180 degrees.
    # point (lon 10, lat 50): column = (10 + 180) // 180 = 1, row = (90 - 50) // 180 = 0.
    tile = _get_tile(tile_matrix_set="wgs84", tile_matrix="0", point=(10.0, 50.0))

    assert (tile.row, tile.column) == (0, 1)


@responses.activate
def test_point_outside_the_matrix_is_a_clear_error():
    _register_capabilities()

    with pytest.raises(OGCError) as exc:
        get_wmts_tile(
            WMTS_URL, layer="test:basemap", tile_matrix_set="sweref99tm", tile_matrix="0",
            point=(9_000_000.0, 5_000_000.0),
        )

    assert "outside" in str(exc.value)


# --- validation ---------------------------------------------------------------


@responses.activate
@pytest.mark.parametrize(
    ("kwargs", "expected_in_message"),
    [
        ({"layer": "nope"}, "test:basemap"),
        ({"tile_matrix_set": "nope"}, "WebMercatorQuad"),
        ({"tile_matrix": "99"}, "0, 1"),
        ({"image_format": "image/webp"}, "image/png"),
        ({"style": "nope"}, "default"),
        ({"row": 2}, "row"),
        ({"column": -1}, "column"),
    ],
)
def test_invalid_input_lists_valid_options(kwargs, expected_in_message):
    _register_capabilities()
    args = {
        "layer": "test:basemap", "tile_matrix_set": "WebMercatorQuad",
        "tile_matrix": "1", "row": 0, "column": 0,
    }
    args.update(kwargs)

    with pytest.raises(OGCError) as exc:
        get_wmts_tile(WMTS_URL, **args)

    assert expected_in_message in str(exc.value)


@responses.activate
@pytest.mark.parametrize(
    "location",
    [
        {},
        {"row": 0},
        {"row": 0, "column": 0, "point": (0.0, 0.0)},
    ],
)
def test_needs_exactly_one_of_row_column_or_point(location):
    _register_capabilities()

    with pytest.raises(OGCError) as exc:
        get_wmts_tile(
            WMTS_URL, layer="test:basemap", tile_matrix_set="WebMercatorQuad",
            tile_matrix="1", **location,
        )

    assert "point" in str(exc.value)
