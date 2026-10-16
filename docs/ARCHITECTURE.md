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
├── errors.py        # OGCError + agent-friendly wrapping of transport/service errors
├── auth.py          # per-host credentials from MCP_OGC_AUTH
├── services.py      # open_wms / open_wfs + opt-in capabilities cache and retry/backoff
├── tools/
│   ├── wms.py       # list_wms_layers, get_wms_map  — plain functions
│   ├── wmts.py      # list_wmts_layers, get_wmts_tile — plain functions
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

## Authentication

Credentials live in the `MCP_OGC_AUTH` environment variable as a JSON object keyed by host, and
`services.py` attaches the matching entry when it builds an owslib client. They are deliberately
**not** tool arguments: anything in a tool call is visible to (and chosen by) the LLM. Because the
agent picks the URL, credentials are scoped to an exact host (or `host:port`) — never substring
matched — so they can't be redirected to an attacker-controlled endpoint, and they are only sent
over https unless an entry explicitly opts out.

The check runs **per request**, inside a `requests` auth hook (`_HostBoundAuth`), not once per
client. That matters because owslib sends GetMap/GetFeature to the URLs the capabilities document
*advertises*, which can be a different host or an http variant of the same one. Basic credentials
therefore go through the hook too (as an `auth_delegate`), never as owslib's `username`/`password`.
The host is read with urllib3's parser, the one `requests` connects with, and must agree with
`urllib.parse`; a URL the two read differently (e.g. `https://a\@b/`) gets no credentials.

owslib turns HTTP 400/401/403 into a `ServiceException` carrying only the response body, so the
status code is not available. `wrap_connection_errors` therefore reports "the service rejected
the request" and adds a hint: configure credentials for that host, or check the ones configured.

## WMTS: point to tile

`get_wmts_tile` accepts either a tile `row` + `column` or a `point`, because agents think in
coordinates, not tile indices. The point is converted with the formula in OGC WMTS 1.0.0
Annex H (`pixel_span = ScaleDenominator × 0.28 mm / metersPerUnit`). Two traps, both silent
(they just return a different, valid-looking tile):

- **Axis order.** `TopLeftCorner` is written in the CRS's own axis order, so it is northing-first
  for EPSG:3006 and EPSG:4326. owslib parses it in document order without swapping. We swap it
  when `owslib.crs.Crs(crs).axisorder == "yx"`. As with `get_wms_map`, callers always pass the
  point easting-first.
- **Units.** Degree-based CRS use `metersPerUnit = 2π × 6378137 / 360`; projected CRS are assumed
  to be in metres.

The core returns a `WMTSTile` (bytes + MIME type + resolved row/column). The MCP tool returns
both the image and a text line with the location, so an agent can request neighbouring tiles.

## WFS attribute filters

`query_wfs_features` takes structured `filters` (preferred) or a raw `cql_filter`:

- **`filters` → OGC Filter Encoding 2.0.** Built with the standard library's ElementTree and sent as
  the `FILTER` KVP parameter, so it works on any WFS 2.0 server. We build that request ourselves
  because owslib's GET `getfeature(filter=...)` sends the filter as `query=`, which servers ignore.
  WFS forbids `BBOX` together with `FILTER`, so a `bbox` is folded into the filter as an
  `fes:BBOX` (no `ValueReference` = default geometry), in the feature type's default CRS and
  axis order, mirroring owslib's own plain-bbox encoding. Verified live: on Sundsvall's GeoServer
  (EPSG:3006) the filter path and the plain-bbox path return the same 49 features.
- **`cql_filter` → GeoServer's `CQL_FILTER`.** Passed through verbatim. It can't be detected
  whether a server honours it: MapServer (e.g. PDOK) silently ignores it and returns unfiltered
  results, so the docs steer agents to `filters`.

Server rejections arrive as owslib `ServiceException`s (raw XML body for HTTP 400, extracted text
for an exception report in an HTTP 200). When a filter was used they become an `OGCError` quoting
the server's message plus a filter hint. Tags are stripped with a regex and entities unescaped, so
no untrusted XML is parsed by us.

## Caching and retries

Both live in `services.py` and are off unless their environment variable is set, so the default
behaviour is exactly v0.1's. The cache stores *parsed* owslib service objects, so a later
`get_wms_map` on the same endpoint skips both the GetCapabilities request and the XML parse.
Entries are keyed by service type, URL and a hash of `MCP_OGC_AUTH`, because different credentials
can see different layers. Failures are never cached.

Retries wrap whole owslib calls rather than the HTTP layer: owslib issues module-level
`requests.request(...)` calls with no session we could mount a retry adapter on. Only transient
failures are retried (connection errors, timeouts, 5xx). owslib reports 4xx as
`ServiceException`, which is never retried.

## Deliberate v0.1.0 scope limits

Small and sharp beats big and half-broken. Intentionally **out** of v0.1.0:

- **WFS attribute filtering (CQL).** owslib's `getfeature()` exposes no CQL parameter (only an OGC
  XML filter). Supporting CQL well would mean fragile, vendor-specific request building, so
  v0.1.0 supported **spatial (bbox) filtering only**. (Since added; see WFS attribute filters.)
- **WMTS, WPS, OAuth/SAML auth, caching, retries, exotic CRS reprojection.** All deferred.
  (HTTP Basic and static Bearer tokens have since been added — see Authentication above. Full
  OAuth flows and SAML remain out of scope.)

## Testing strategy

Tests are **hermetic** — no network. Because owslib uses the `requests` library internally, HTTP
is mocked with [`responses`](https://github.com/getsentry/responses) (not `pytest-httpx`, which
only intercepts `httpx`). Tiny capabilities/GeoJSON fixtures in `tests/fixtures.py` are served to
owslib so the real tool code paths run offline. CI (GitHub Actions) runs `ruff` + `pytest` on
every push.
