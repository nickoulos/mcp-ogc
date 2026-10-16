"""The runtime version must match the installed package metadata.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from importlib.metadata import version

import mcp_ogc


def test_version_matches_package_metadata():
    assert mcp_ogc.__version__ == version("mcp-ogc")
