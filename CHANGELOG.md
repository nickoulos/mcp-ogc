# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Authentication for protected endpoints (#3). Per-host credentials are read from the
  `MCP_OGC_AUTH` environment variable (JSON keyed by host or `host:port`): HTTP Basic
  (`username` + `password`) or a Bearer `token`. Credentials are never tool arguments, are sent
  only to their exact host, only over https unless `"allow_insecure_http": true`, and are never
  logged or echoed in errors.
- When a service rejects a request (HTTP 400/401/403), tools now raise an `OGCError` naming the
  endpoint and hinting at `MCP_OGC_AUTH`, instead of a raw owslib `ServiceException`.
- Opt-in capabilities cache and retry/backoff (#4). `MCP_OGC_CACHE_TTL` keeps parsed
  GetCapabilities documents in memory (bounded LRU, keyed by endpoint and auth config).
  `MCP_OGC_RETRIES` / `MCP_OGC_RETRY_BACKOFF` retry connection errors, timeouts and HTTP 5xx with
  exponential backoff, for both capabilities and data requests; 4xx is never retried. Both are
  off by default.

- WMTS support (#2). `list_wmts_layers` lists layers with their formats, styles and tile matrix
  sets; `get_wmts_tile` fetches one tile by `row` + `column`, or by a `point` in the tile matrix
  set's CRS (always easting-first). Converting a point uses the OGC WMTS formula, swaps the
  TopLeftCorner for northing-first CRS such as EPSG:3006 and EPSG:4326, and handles degree-based
  CRS. The tool returns the tile image plus its resolved row/column. Verified live against
  TopPlusOpen (EPSG:3857 and EPSG:25832).

- WFS attribute filtering (#1). `query_wfs_features` accepts `filters`, a list of
  `{property, op, value}` conditions (`=`, `!=`, `<`, `<=`, `>`, `>=`, `like`, `is_null`) AND-ed
  into a standard OGC FES 2.0 filter that works on any WFS 2.0 server and combines with `bbox`. It
  also accepts `cql_filter`, a raw CQL string sent as GeoServer's `CQL_FILTER` vendor parameter
  (GeoServer only; mutually exclusive with `filters` and `bbox`). Verified live on GeoServer
  (GeoSolutions, Sundsvall) and MapServer (PDOK).
- A query the server rejects now produces an `OGCError` quoting the server's message (tags stripped,
  entities unescaped), and a response that isn't GeoJSON gets a clear error instead of a JSON
  decode traceback.

### Security

- Server error text is truncated *before* tags are stripped. A hostile or broken server body
  with many unclosed `<` made the tag-stripping regex quadratic (about 107 s for 400 KB); it is
  now bounded and the pattern can't scan past the next `<`. The flaw never shipped in a release.
- Credentials are now bound to each outgoing request's host, not to the owslib client. Before,
  a capabilities document that advertised a GetMap/GetFeature URL on another host (or a plain
  http variant of the same host) received the configured credentials. The host is now parsed
  with urllib3 (the parser `requests` connects with) and must agree with the stdlib parser, so
  URLs such as `https://evil.test\@trusted.host/` no longer match `trusted.host`. Never released.

## [0.2.0] - 2026-07-23

### Added

- Regression test pinning the WMS 1.3.0 axis-order contract for northing-first
  CRS (EPSG:3006 / SWEREF99 TM): `get_wms_map` takes bbox easting-first for
  every CRS and owslib swaps to northing-first on the wire. A wrong order fails
  silently (HTTP 200, near-blank image), so the on-wire order is now asserted
  in tests and documented in the `get_wms_map` docstring and ARCHITECTURE.md.
  Verified live against karta.sundsvall.se (365 KB imagery vs 5.6 KB blank).

- Streamable HTTP transport mode, so `mcp-ogc` can be consumed by MCP clients
  that require it (e.g. Eneo) instead of stdio. `mcp-ogc --transport
  streamable-http --host 0.0.0.0 --port 8000` serves over HTTP; the console
  script defaults to `--transport stdio` unchanged, so existing stdio
  consumers are unaffected.
- `TransportSecuritySettings` on the FastMCP instance (DNS-rebinding
  protection with an allowlist covering `127.0.0.1`, `localhost`, `[::1]`, and
  `host.docker.internal`), so the server is reachable from clients running in
  Docker. This only gates the HTTP transport and has no effect on stdio.

## [0.1.1] - 2026-05-31

### Added

- Agent-friendly error handling. Tools now raise a clear `OGCError` instead of
  leaking raw owslib/requests tracebacks:
  - `get_wms_map` / `query_wfs_features` validate the requested layer / feature
    type and, when it is unknown, list the available ones in the message.
  - Unreachable endpoints raise a single readable error naming the URL.

## [0.1.0] - 2026-05-29

Initial release. An MCP server exposing OGC WMS and WFS services as LLM-callable tools.

### Added

- `list_wms_layers(wms_url)` — discover the layers a WMS endpoint exposes (name, title,
  abstract, supported CRS, WGS84 bounding box).
- `get_wms_map(wms_url, layer, bbox, ...)` — fetch a rendered map image (PNG by default) for a
  bounding box, with optional time dimension for time-aware layers.
- `query_wfs_features(wfs_url, type_name, bbox, max_features)` — query vector features from a WFS
  endpoint as a GeoJSON FeatureCollection (spatial/bbox filtering).
- FastMCP server (`mcp-ogc` console script) registering all three tools.
- Example Claude Desktop config and a tool-walkthrough demo notebook.
- Hermetic test suite (pytest + `responses`) and GitHub Actions CI (ruff + pytest).

### Notes

- WFS attribute filtering (CQL) is not included in this release; only spatial (bbox) filtering is
  supported. See the roadmap.
- Requires Python 3.12+.

[0.2.0]: https://github.com/nickoulos/mcp-ogc/releases/tag/v0.2.0
[0.1.1]: https://github.com/nickoulos/mcp-ogc/releases/tag/v0.1.1
[0.1.0]: https://github.com/nickoulos/mcp-ogc/releases/tag/v0.1.0
