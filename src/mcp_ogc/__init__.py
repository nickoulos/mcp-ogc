"""mcp-ogc — OGC WMS/WMTS/WFS services as Model Context Protocol tools."""

from importlib.metadata import version

# Read from the installed package metadata (pyproject.toml) so it can't drift.
__version__ = version("mcp-ogc")
