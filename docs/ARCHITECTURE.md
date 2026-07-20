# Architecture

`mcp-ogc` is a thin, deliberately small bridge between two worlds: LLM agents that speak the
Model Context Protocol (MCP), and public geodata services that speak the OGC standards (WMS, WFS).

## Why MCP

MCP is an open protocol that lets an LLM client attach to a server and call typed *tools*. It is
the cleanest way to give an agent a new capability without baking that capability into the model
or the client. By exposing geodata access as MCP tools, any MCP-compatible client — Claude
Desktop, a custom agent, an Eneo assistant — gains geospatial reasoning for free.

## Why OGC (WMS / WFS)

Municipal and national GIS data across Europe is overwhelmingly published via OGC web services.
WMS serves rendered map images for a bounding box; WFS serves vector features as GeoJSON/GML.
INSPIRE (the EU geospatial directive) mandates them, so a single OGC client reaches an enormous
amount of real public data without per-service integration work.

## Layering: pure core, thin MCP shell

The codebase separates the geospatial logic from the protocol plumbing:

```
src/mcp_ogc/
├── models.py        # LayerInfo — typed I/O (pydantic)
├── tools/
│   ├── wms.py       # list_wms_layers, get_wms_map  — plain functions
│   └── wfs.py       # query_wfs_features            — plain functions
└── server.py        # FastMCP wiring; registers the tools as MCP tools
```

- **`tools/` functions are pure and framework-agnostic.** They take ordinary arguments and return
  ordinary Python values (`list[LayerInfo]`, `bytes`, `dict`). They have no knowledge of MCP. This
  makes them trivial to unit-test (see `tests/`) and reusable as a plain Python library.
- **`server.py` is the only MCP-aware module.** It registers each tool with `FastMCP`. The one
  place this matters: `get_wms_map`'s core returns raw `bytes`, and the server wraps them in
  FastMCP's `Image` so MCP clients render the map. The core stays pure; the shell adapts it.

This boundary is the main design decision. It keeps each unit understandable on its own and means
the geospatial code can be tested and reused independently of the protocol.

## Why owslib

`owslib` is the standard Python client for OGC services. It handles GetCapabilities parsing, WMS/
WFS version quirks, and request construction, so `mcp-ogc` doesn't reimplement the OGC protocols.
One wrinkle it imposes: its `WebMapService.getmap()` names the coordinate-system argument `srs`
even for WMS 1.3.0, so our public `crs` argument is translated to `srs` inside `get_wms_map`.

A second wrinkle it *solves*: WMS 1.3.0 requires northing-first bbox order on the wire for
CRS whose official axis order is lat/north-first (e.g. EPSG:3006 / SWEREF99 TM), and getting
this wrong fails silently — GeoServer returns HTTP 200 with a nearly blank image, not an
error. owslib knows these CRS (`owslib.crs.axisorder_yx`) and swaps the bbox itself when
building the 1.3.0 request. The `get_wms_map` contract is therefore: **bbox is always
`(minx, miny, maxx, maxy)` easting-first, for every CRS — never pre-swap.** This is pinned
by `test_get_wms_map_epsg3006_sends_bbox_northing_first`, which asserts the on-wire order,
and was verified live against `karta.sundsvall.se` (correct order: 365 KB ortofoto PNG;
wrong order: 5.6 KB near-blank PNG, both HTTP 200).

## Deliberate v0.1.0 scope limits

Small and sharp beats big and half-broken. Intentionally **out** of v0.1.0:

- **WFS attribute filtering (CQL).** owslib's `getfeature()` exposes no CQL parameter (only an OGC
  XML filter). Supporting CQL well would mean fragile, vendor-specific request building, so
  v0.1.0 supports **spatial (bbox) filtering only**; CQL is a v0.2 roadmap item.
- **WMTS, WPS, OAuth/SAML auth, caching, retries, exotic CRS reprojection.** All deferred.

## Testing strategy

Tests are **hermetic** — no network. Because owslib uses the `requests` library internally, HTTP
is mocked with [`responses`](https://github.com/getsentry/responses) (not `pytest-httpx`, which
only intercepts `httpx`). Tiny capabilities/GeoJSON fixtures in `tests/fixtures.py` are served to
owslib so the real tool code paths run offline. CI (GitHub Actions) runs `ruff` + `pytest` on
every push.
