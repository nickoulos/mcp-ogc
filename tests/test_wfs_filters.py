"""Tests for WFS attribute filtering: structured `filters` (OGC FES 2.0) and
GeoServer's `cql_filter` vendor parameter, plus exception-report handling.

Hermetic — HTTP mocked with `responses`.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from mcp_ogc.errors import OGCError
from mcp_ogc.tools.wfs import query_wfs_features
from tests.fixtures import WFS_CAPABILITIES_200, WFS_GEOJSON_RESPONSE

WFS_URL = "http://example.test/wfs"
WFS_URL_RE = re.compile(r"^http://example\.test/wfs")
FES = "{http://www.opengis.net/fes/2.0}"
GML = "{http://www.opengis.net/gml/3.2}"

EXCEPTION_REPORT = """<?xml version="1.0" encoding="UTF-8"?>
<ows:ExceptionReport xmlns:ows="http://www.opengis.net/ows/1.1" version="2.0.0">
  <ows:Exception exceptionCode="InvalidParameterValue" locator="FILTER">
    <ows:ExceptionText>Illegal property name: typ</ows:ExceptionText>
  </ows:Exception>
</ows:ExceptionReport>
"""


def _register(getfeature_body=WFS_GEOJSON_RESPONSE, status=200, content_type="application/json"):
    responses.add(
        responses.GET, WFS_URL_RE, body=WFS_CAPABILITIES_200,
        content_type="text/xml", status=200,
    )
    responses.add(
        responses.GET, WFS_URL_RE, body=getfeature_body,
        content_type=content_type, status=status,
    )


def _getfeature_params() -> dict[str, str]:
    query = parse_qs(urlparse(responses.calls[-1].request.url).query)
    return {k.lower(): v[0] for k, v in query.items()}


def _sent_filter() -> ET.Element:
    root = ET.fromstring(_getfeature_params()["filter"])
    assert root.tag == f"{FES}Filter"
    return root


# --- structured filters -> FES 2.0 --------------------------------------------


@responses.activate
def test_single_equality_filter_is_sent_as_fes():
    _register()

    result = query_wfs_features(
        WFS_URL, type_name="test:buildings",
        filters=[{"property": "type", "op": "=", "value": "school"}],
    )

    assert result["type"] == "FeatureCollection"
    (condition,) = list(_sent_filter())
    assert condition.tag == f"{FES}PropertyIsEqualTo"
    assert condition.find(f"{FES}ValueReference").text == "type"
    assert condition.find(f"{FES}Literal").text == "school"


@responses.activate
def test_getfeature_request_keeps_type_count_and_json_output():
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings", max_features=7,
        filters=[{"property": "type", "value": "school"}],
    )

    params = _getfeature_params()
    assert params["request"] == "GetFeature"
    assert params["typenames"] == "test:buildings"
    assert params["count"] == "7"
    assert params["outputformat"] == "application/json"


@responses.activate
@pytest.mark.parametrize(
    ("op", "tag"),
    [
        ("=", "PropertyIsEqualTo"),
        ("!=", "PropertyIsNotEqualTo"),
        ("<", "PropertyIsLessThan"),
        ("<=", "PropertyIsLessThanOrEqualTo"),
        (">", "PropertyIsGreaterThan"),
        (">=", "PropertyIsGreaterThanOrEqualTo"),
    ],
)
def test_comparison_operators_map_to_fes(op, tag):
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings",
        filters=[{"property": "floors", "op": op, "value": 3}],
    )

    (condition,) = list(_sent_filter())
    assert condition.tag == f"{FES}{tag}"
    assert condition.find(f"{FES}Literal").text == "3"


@responses.activate
def test_like_filter_uses_percent_wildcard():
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings",
        filters=[{"property": "name", "op": "like", "value": "Town%"}],
    )

    (condition,) = list(_sent_filter())
    assert condition.tag == f"{FES}PropertyIsLike"
    assert condition.get("wildCard") == "%"
    assert condition.get("singleChar") == "_"
    assert condition.get("escapeChar") == "\\"
    assert condition.find(f"{FES}Literal").text == "Town%"


@responses.activate
def test_is_null_filter_needs_no_value():
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings",
        filters=[{"property": "demolished", "op": "is_null"}],
    )

    (condition,) = list(_sent_filter())
    assert condition.tag == f"{FES}PropertyIsNull"
    assert condition.find(f"{FES}ValueReference").text == "demolished"


@responses.activate
def test_multiple_filters_are_anded():
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings",
        filters=[
            {"property": "type", "value": "school"},
            {"property": "floors", "op": ">", "value": 2},
        ],
    )

    (combined,) = list(_sent_filter())
    assert combined.tag == f"{FES}And"
    assert [c.tag for c in combined] == [
        f"{FES}PropertyIsEqualTo", f"{FES}PropertyIsGreaterThan",
    ]


@responses.activate
def test_bbox_with_filters_goes_into_the_fes_filter_northing_first():
    # Default CRS of test:buildings is urn:ogc:def:crs:EPSG::4326, which is lat/lon:
    # bbox is passed easting-first (like everywhere else) and swapped on the wire.
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings", bbox=(10.0, 50.0, 11.0, 51.0),
        filters=[{"property": "type", "value": "school"}],
    )

    params = _getfeature_params()
    assert "bbox" not in params  # WFS forbids BBOX together with FILTER
    (combined,) = list(_sent_filter())
    assert combined.tag == f"{FES}And"
    bbox = combined.find(f"{FES}BBOX")
    envelope = bbox.find(f"{GML}Envelope")
    assert envelope.get("srsName") == "urn:ogc:def:crs:EPSG::4326"
    assert envelope.find(f"{GML}lowerCorner").text == "50.0 10.0"
    assert envelope.find(f"{GML}upperCorner").text == "51.0 11.0"


@responses.activate
def test_bbox_without_filters_still_uses_plain_bbox_param():
    _register()

    query_wfs_features(WFS_URL, type_name="test:buildings", bbox=(10.0, 50.0, 11.0, 51.0))

    params = _getfeature_params()
    assert "filter" not in params
    assert params["bbox"].startswith("50.0,10.0,51.0,11.0")


@pytest.mark.parametrize(
    "bad",
    [
        {"property": "type", "op": "~", "value": "x"},
        {"property": "type", "op": "="},
        {"op": "=", "value": "x"},
    ],
)
@responses.activate
def test_invalid_filter_is_a_clear_error(bad):
    _register()

    with pytest.raises(OGCError) as exc:
        query_wfs_features(WFS_URL, type_name="test:buildings", filters=[bad])

    assert "filter" in str(exc.value).lower()


# --- cql_filter (GeoServer vendor parameter) ----------------------------------


@responses.activate
def test_cql_filter_is_passed_through_verbatim():
    _register()

    query_wfs_features(
        WFS_URL, type_name="test:buildings", cql_filter="type = 'school' AND floors > 2",
    )

    params = _getfeature_params()
    assert params["cql_filter"] == "type = 'school' AND floors > 2"
    assert "filter" not in params


@responses.activate
def test_cql_filter_and_filters_are_mutually_exclusive():
    _register()

    with pytest.raises(OGCError) as exc:
        query_wfs_features(
            WFS_URL, type_name="test:buildings", cql_filter="type = 'school'",
            filters=[{"property": "type", "value": "school"}],
        )

    assert "cql_filter" in str(exc.value)


@responses.activate
def test_cql_filter_with_bbox_explains_how_to_combine():
    _register()

    with pytest.raises(OGCError) as exc:
        query_wfs_features(
            WFS_URL, type_name="test:buildings", cql_filter="type = 'school'",
            bbox=(10.0, 50.0, 11.0, 51.0),
        )

    msg = str(exc.value)
    assert "BBOX(" in msg
    # Without an explicit CRS, GeoServer reads CQL BBOX in the layer's native axis
    # order (lat/lon for EPSG:4326); verified live, so the advice must include one.
    assert "'EPSG:" in msg
    assert "geometry_name" in msg


# --- server-side rejections ---------------------------------------------------


@responses.activate
def test_exception_report_becomes_clear_error_with_server_text():
    _register(EXCEPTION_REPORT, content_type="text/xml")

    with pytest.raises(OGCError) as exc:
        query_wfs_features(
            WFS_URL, type_name="test:buildings",
            filters=[{"property": "typ", "value": "school"}],
        )

    assert "Illegal property name: typ" in str(exc.value)


@responses.activate
def test_exception_report_with_http_400_is_handled_too():
    # WFS 2.0 servers (e.g. GeoServer) answer a bad query with HTTP 400 + report.
    _register(EXCEPTION_REPORT, status=400, content_type="text/xml")

    with pytest.raises(OGCError) as exc:
        query_wfs_features(
            WFS_URL, type_name="test:buildings",
            filters=[{"property": "typ", "value": "school"}],
        )

    msg = str(exc.value)
    assert "Illegal property name: typ" in msg
    assert "<ows:" not in msg  # server text, not raw XML
    assert "MCP_OGC_AUTH" not in msg  # a bad filter is not an auth problem


@responses.activate
def test_rejected_cql_suggests_structured_filters():
    _register(EXCEPTION_REPORT, status=400, content_type="text/xml")

    with pytest.raises(OGCError) as exc:
        query_wfs_features(WFS_URL, type_name="test:buildings", cql_filter="typ = 'x'")

    assert "filters" in str(exc.value)


@responses.activate
def test_exception_report_without_filters_is_a_clear_error():
    _register(EXCEPTION_REPORT, content_type="text/xml")

    with pytest.raises(OGCError) as exc:
        query_wfs_features(WFS_URL, type_name="test:buildings")

    assert "Illegal property name: typ" in str(exc.value)


@responses.activate
def test_non_json_non_report_response_is_a_clear_error():
    _register("<html>maintenance</html>", content_type="text/html")

    with pytest.raises(OGCError) as exc:
        query_wfs_features(WFS_URL, type_name="test:buildings")

    assert "GeoJSON" in str(exc.value)


@responses.activate
def test_filtered_request_still_sends_credentials_to_the_same_host(monkeypatch):
    monkeypatch.setenv(
        "MCP_OGC_AUTH", json.dumps({"secure.example.test": {"token": "s3cret"}})
    )
    secure_re = re.compile(r"^https://secure\.example\.test/wfs")
    responses.add(
        responses.GET, secure_re, content_type="text/xml", status=200,
        body=WFS_CAPABILITIES_200.replace(
            "http://example.test/wfs?", "https://secure.example.test/wfs?"
        ),
    )
    responses.add(
        responses.GET, secure_re, body=WFS_GEOJSON_RESPONSE,
        content_type="application/json", status=200,
    )

    query_wfs_features(
        "https://secure.example.test/wfs", type_name="test:buildings",
        filters=[{"property": "type", "value": "school"}],
    )

    assert responses.calls[-1].request.headers["Authorization"] == "Bearer s3cret"
