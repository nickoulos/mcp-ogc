# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
