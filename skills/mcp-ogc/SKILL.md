---
name: mcp-ogc
description: Use when the mcp-ogc MCP tools (list_wms_layers, get_wms_map, query_wfs_features, list_wmts_layers, get_wmts_tile) are available and a request involves maps, map tiles, aerial or orthophoto imagery, map layers, parcels, boundaries or other features from a WMS, WMTS or WFS geoservice (municipal GIS, INSPIRE, GeoServer, PDOK, Lantmäteriet), or when a map image comes back blank or a feature query comes back empty.
---

# mcp-ogc

## Overview

mcp-ogc talks WMS 1.3.0, WMTS and WFS 2.0.0 through owslib. Most failures are silent: HTTP 200 with a
near-blank image or an empty FeatureCollection. The cause is almost always the CRS or the bbox,
not the server.

**Core rule: every bbox is `(minx, miny, maxx, maxy)` and every WMTS `point` is `(x, y)`,
easting/longitude first, for every CRS.**
For northing-first CRSs (EPSG:3006, EPSG:3011, EPSG:4326, EPSG:4258) owslib swaps the axes on the
wire itself. This holds for WMS, and for WFS whenever the service advertises its CRS as a URN
(standard for WFS 2.0). Pre-swapping turns a correct request into a blank image.

**Reprojecting:** if you can run code, convert coordinates with pyproj instead of by hand:
`Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True).transform(lon, lat)`.
Hand-computed projections drift by tens of metres or more.

## WMS: a map or aerial photo of a place

1. `list_wms_layers(url)`: pick the layer. Read its `crs_options` and `bbox_wgs84` (lon/lat).
2. Set `crs` to one of that layer's `crs_options`. The default `EPSG:3857` only works if it is listed.
3. Convert the location into that CRS and build the bbox easting-first.
4. Match `width`/`height` to the bbox aspect ratio (a square bbox needs a square image). In
   EPSG:3857, ground distances are stretched by 1/cos(latitude), so 1 km on the ground needs a
   bbox about 2 km wide at 60°N. Prefer a local metric CRS from `crs_options` when one is listed.
5. Aerial photos: use `image_format: "image/jpeg"`. It is smaller, and transparent no-data areas in a
   PNG can look blank.
6. Time-aware layers: the available `time` values are **not** returned by `list_wms_layers`. Take a
   hint from the abstract and try a year (`"1975"`), then a full date (`"1975-01-01"`). If nothing
   renders, tell the user which values you tried rather than silently switching to another year.

## WFS: features in an area

1. **Feature type name unknown?** Call `query_wfs_features` with a deliberately wrong `type_name`
   (e.g. `"?"`). The error lists every available type with its namespace prefix
   (`bestuurlijkegebieden:Gemeentegebied`). Use the name exactly as listed.
2. **The bbox is in the feature type's default CRS, not WGS84**, and the GeoJSON comes back in that
   same CRS. To learn it, make one call without a bbox and with `max_features: 1`. Read the `crs`
   member if the GeoJSON has one, or else the coordinate magnitudes against the table below. Build
   later bboxes in those units. The same sample also shows the property names you can filter on.
3. Filter by attribute with `filters`, which works on any WFS 2.0 server and combines with `bbox`:
   `[{"property": "naam", "op": "like", "value": "Utr%"}]`. The ops are `=` (default), `!=`, `<`,
   `<=`, `>`, `>=`, `like` (`%` = any run of characters, `_` = one character) and `is_null` (no
   value). Conditions are AND-ed; for OR, make one call per alternative and merge the results.
   Never guess property names: copy them exactly (case-sensitive, no prefix) from a sample feature's
   `properties`. An unknown name comes back as an error quoting the server, so fix the name rather
   than dropping the filter.
4. `cql_filter` is a raw CQL string for **GeoServer only**. Other servers (e.g. MapServer, used by
   PDOK) silently ignore it and return unfiltered features, so prefer `filters`. It cannot be
   combined with `filters` or `bbox`. On GeoServer it is the one-call way to express OR or `IN`.
   For a spatial term put it inside the CQL as
   `BBOX(<geometry property>, minx, miny, maxx, maxy, 'EPSG:<code>')`, easting-first and always
   with the explicit CRS;
   without it GeoServer reads the box in the layer's native axis order and returns nothing. The
   geometry property name is in each feature's `geometry_name`.
5. Every feature comes back with its full geometry, and polygons are large. Keep `max_features`
   small, and split a big area into several bboxes instead of one huge query.
6. If the number of features equals `max_features`, the result may be truncated. Raise the limit or
   shrink the bbox.
7. The bbox matches by intersection, not containment. A tiny box on a border can return neighbours,
   so check the geometry when that matters.

## WMTS: tiles from a tiled (cached) map service

Use WMTS when the service only offers tiles (many national base maps), or for fast cached base
maps. Use WMS when you need an arbitrary bbox at a chosen image size.

1. `list_wmts_layers(url)`: pick the layer, then a `tile_matrix_sets` entry, preferring a local
   metric CRS as for WMS. Its `tile_matrices` are zoom ids (strings) ordered coarsest first; later
   ids show more detail. The listing gives no scale, so start near the finest third for street
   level, look at the tile, and step one id at a time.
2. `get_wmts_tile(url, layer, tile_matrix_set, tile_matrix, point=[x, y])`: pass `point` in that
   set's CRS, easting-first (lon/lat for degrees). The tool handles the tile origin for
   northing-first CRSs, so do not pre-swap and do not compute row/column yourself. Pass either
   `point` or `row` + `column`, never both.
3. Each call returns one fixed-size tile plus a line `tile_matrix_set=… tile_matrix=… row=… column=…`.
   The point can sit anywhere in that tile, not at its centre. To see around it, pan at the same
   zoom: north = `row - 1`, south = `row + 1`, east = `column + 1`, west = `column - 1`.
   When changing zoom, locate again with `point`; row/column do not carry over between zoom ids.
4. `style` and `image_format` default sensibly (the default style; PNG when offered). The errors list
   valid layers, sets, zoom ids, styles, formats and row/column ranges.

## Blank image or empty result: check in this order

| Check | Fix |
|---|---|
| `crs` is not in the layer's `crs_options` | Use a listed CRS |
| The bbox is in different units than `crs` (lon/lat sent with EPSG:3006) | Reproject the bbox |
| The bbox is outside the layer's `bbox_wgs84` | Recheck the location and the conversion |
| WMS `time` value has no data | Try another value, and tell the user |
| `cql_filter` returned unfiltered features | The server is not GeoServer: use `filters` |
| `cql_filter` with a `BBOX(...)` term returned nothing | Add the `'EPSG:<code>'` argument |
| WFS returns empty, default CRS is in degrees, bbox is certainly right | Retry once with lat/lon swapped (some servers advertise the CRS in a form owslib does not swap) |

A tiny file (a few KB) for an aerial photo is the tell for a blank image. For WMS, swapping the axes
is never the fix. Control test: request the layer's whole extent (from `bbox_wgs84`, converted) at
a small size; distortion doesn't matter for this pass/fail check. If that renders, your bbox is
wrong, not the server.

## Common CRSs

| CRS | Units | Typical range of what you pass |
|---|---|---|
| EPSG:4326 / 4258 | degrees | lon, lat |
| EPSG:3857 | metres (Web Mercator) | x, y |
| EPSG:3006 SWEREF99 TM (Sweden) | metres | E 200k–1M, N 6.1M–7.7M |
| EPSG:28992 RD New (Netherlands) | metres | x 0–300k, y 300k–625k |
| EPSG:25832 / 25833 ETRS89 UTM | metres | E, N |

## Errors

- `Unknown WMS layer ... Available layers: ...` / `Unknown WFS feature type ...`: pick from the list.
- `Could not reach the OGC service at ...`: the URL is wrong or unreachable. Pass the base service URL;
  owslib appends the request parameters.
- `The OGC service at ... rejected the request: <detail> (... MCP_OGC_AUTH)`: read the detail first.
  A rejection is often a bad parameter (unsupported CRS, malformed bbox, unknown time value), not
  auth. If the detail says unauthorized or forbidden, credentials are missing or wrong. They live in
  the server's `MCP_OGC_AUTH` environment variable, never in tool arguments, so tell the user to
  configure it. Do not ask them to paste credentials into the chat.
- Intermittent timeouts or slow repeated calls: caching and retries are opt-in server settings
  (`MCP_OGC_CACHE_TTL`, `MCP_OGC_RETRIES`, `MCP_OGC_RETRY_BACKOFF` environment variables), not tool
  arguments. Suggest them to the user rather than hammering the service.
