"""WFS (Web Feature Service) tools.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlencode

from owslib.util import openURL
from pydantic import ValidationError

from mcp_ogc.errors import OGCError, service_text, wrap_connection_errors
from mcp_ogc.models import AttributeFilter
from mcp_ogc.services import call_with_retry, open_wfs

_FES_NS = "http://www.opengis.net/fes/2.0"
_GML_NS = "http://www.opengis.net/gml/3.2"
ET.register_namespace("fes", _FES_NS)
ET.register_namespace("gml", _GML_NS)

_FES_COMPARISONS = {
    "=": "PropertyIsEqualTo",
    "!=": "PropertyIsNotEqualTo",
    "<": "PropertyIsLessThan",
    "<=": "PropertyIsLessThanOrEqualTo",
    ">": "PropertyIsGreaterThan",
    ">=": "PropertyIsGreaterThanOrEqualTo",
}


def query_wfs_features(
    wfs_url: str,
    type_name: str,
    bbox: tuple[float, float, float, float] | None = None,
    max_features: int = 100,
    filters: Sequence[AttributeFilter | dict[str, Any]] | None = None,
    cql_filter: str | None = None,
) -> dict[str, Any]:
    """Query vector features from a WFS endpoint as GeoJSON.

    Args:
        wfs_url: Base URL of the WFS service.
        type_name: Feature type to query (as advertised by the service's
            DescribeFeatureType / capabilities).
        bbox: Optional bounding box filter (minx, miny, maxx, maxy) in the
            feature type's coordinates, easting-first.
        max_features: Maximum number of features to return (default 100).
        filters: Optional attribute conditions, AND-ed together and sent as a
            standard OGC Filter Encoding 2.0 filter (portable across WFS 2.0
            servers). Can be combined with ``bbox``.
        cql_filter: Optional raw CQL expression, sent as GeoServer's
            ``CQL_FILTER`` vendor parameter. GeoServer only — other servers may
            ignore it and return unfiltered features, so prefer ``filters``.
            Mutually exclusive with ``filters`` and ``bbox``.

    Returns:
        A GeoJSON FeatureCollection as a dict.

    Raises:
        OGCError: if the endpoint cannot be reached, ``type_name`` is not one of
            the advertised feature types, the filter arguments are invalid, or
            the server rejects the query (its message is included).
    """
    conditions = _validate_filters(filters)
    if conditions and cql_filter:
        raise OGCError("Pass either filters or cql_filter, not both.")
    if cql_filter and bbox:
        raise OGCError(
            "cql_filter cannot be combined with bbox: WFS forbids a BBOX alongside a filter. "
            "Either use filters together with bbox, or add a term like "
            "BBOX(<geometry property>, minx, miny, maxx, maxy, 'EPSG:<code>') to cql_filter. "
            "Keep the explicit 'EPSG:<code>': without it GeoServer reads the box in the "
            "layer's native axis order (lat/lon for EPSG:4326). GeoServer's GeoJSON features "
            "name the geometry property in their geometry_name field."
        )

    with wrap_connection_errors(wfs_url):
        wfs = open_wfs(wfs_url)

        if type_name not in wfs.contents:
            available = ", ".join(sorted(wfs.contents)) or "(none advertised)"
            raise OGCError(
                f"Unknown WFS feature type {type_name!r}. "
                f"Available feature types: {available}"
            )

        if conditions or cql_filter:
            # owslib's GET GetFeature sends a filter as `query=`, which WFS 2.0
            # servers ignore, so the filter parameter is added here instead.
            if cql_filter:
                extra = {"CQL_FILTER": cql_filter}
            else:
                extra = {"FILTER": _fes_filter(conditions, bbox, wfs.contents[type_name])}
            url = wfs.getGETGetFeatureRequest(
                typename=[type_name],
                maxfeatures=max_features,
                outputFormat="application/json",
            )
            url = f"{url}{'&' if '?' in url else '?'}{urlencode(extra)}"

            def fetch():
                return openURL(
                    url, method="Get", timeout=wfs.timeout, headers=wfs.headers, auth=wfs.auth
                )
        else:

            def fetch():
                return wfs.getfeature(
                    typename=[type_name],
                    bbox=bbox,
                    maxfeatures=max_features,
                    outputFormat="application/json",
                )

        try:
            response = call_with_retry(fetch)
        except Exception as exc:
            if (conditions or cql_filter) and type(exc).__name__ == "ServiceException":
                raise OGCError(_filter_rejected(wfs_url, exc, bool(cql_filter))) from exc
            raise
        data = response.read()

    try:
        return json.loads(data)
    except ValueError:
        raise OGCError(
            f"The WFS at {wfs_url} did not return GeoJSON (it may not support "
            f"outputFormat=application/json): {service_text(data.decode(errors='replace'))}"
        ) from None


def _validate_filters(
    filters: Sequence[AttributeFilter | dict[str, Any]] | None,
) -> list[AttributeFilter]:
    conditions = []
    for item in filters or []:
        try:
            conditions.append(
                item if isinstance(item, AttributeFilter) else AttributeFilter.model_validate(item)
            )
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc']) or 'filter'}: {e['msg']}"
                for e in exc.errors()
            )
            raise OGCError(f"Invalid filter {item!r}: {problems}") from None
    return conditions


def _literal(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _fes(tag: str) -> str:
    return f"{{{_FES_NS}}}{tag}"


def _condition(condition: AttributeFilter) -> ET.Element:
    if condition.op == "is_null":
        element = ET.Element(_fes("PropertyIsNull"))
    elif condition.op == "like":
        element = ET.Element(
            _fes("PropertyIsLike"), wildCard="%", singleChar="_", escapeChar="\\"
        )
    else:
        element = ET.Element(_fes(_FES_COMPARISONS[condition.op]))
    ET.SubElement(element, _fes("ValueReference")).text = condition.property
    if condition.op != "is_null":
        ET.SubElement(element, _fes("Literal")).text = _literal(condition.value)
    return element


def _bbox(bbox: tuple[float, float, float, float], feature_type) -> ET.Element:
    """FES BBOX on the default geometry, in the feature type's default CRS.

    Mirrors owslib's plain `bbox=` KVP encoding: callers pass the box
    easting-first, and it is swapped for a northing-first URN CRS.
    """
    crs = feature_type.crsOptions[0]
    minx, miny, maxx, maxy = bbox
    if crs.encoding == "urn":
        srs_name = crs.getcodeurn()
        if crs.axisorder == "yx":
            minx, miny, maxx, maxy = miny, minx, maxy, maxx
    else:
        srs_name = crs.getcode()
    element = ET.Element(_fes("BBOX"))
    envelope = ET.SubElement(element, f"{{{_GML_NS}}}Envelope", srsName=srs_name)
    ET.SubElement(envelope, f"{{{_GML_NS}}}lowerCorner").text = f"{minx} {miny}"
    ET.SubElement(envelope, f"{{{_GML_NS}}}upperCorner").text = f"{maxx} {maxy}"
    return element


def _fes_filter(
    conditions: list[AttributeFilter],
    bbox: tuple[float, float, float, float] | None,
    feature_type,
) -> str:
    parts = [_condition(c) for c in conditions]
    if bbox is not None:
        parts.append(_bbox(bbox, feature_type))
    root = ET.Element(_fes("Filter"))
    if len(parts) == 1:
        root.append(parts[0])
    else:
        ET.SubElement(root, _fes("And")).extend(parts)
    return ET.tostring(root, encoding="unicode")


def _filter_rejected(wfs_url: str, exc: Exception, used_cql: bool) -> str:
    hint = (
        "The server may not support CQL_FILTER (a GeoServer extension); try `filters` instead."
        if used_cql
        else "Check the property names and value types against the feature type's attributes."
    )
    return f"The WFS at {wfs_url} rejected the query: {service_text(exc).rstrip('.')}. {hint}"
