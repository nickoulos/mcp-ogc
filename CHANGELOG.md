# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0]: https://github.com/nickoulos/mcp-ogc/releases/tag/v0.1.0
