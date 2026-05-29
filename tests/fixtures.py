"""Minimal OGC capabilities/response fixtures for hermetic unit tests.

These are deliberately tiny but structurally valid enough for owslib to parse.

SPDX-License-Identifier: AGPL-3.0-or-later
"""

# A minimal but valid WMS 1.3.0 GetCapabilities document with one layer.
WMS_CAPABILITIES_130 = """<?xml version="1.0" encoding="UTF-8"?>
<WMS_Capabilities version="1.3.0"
    xmlns="http://www.opengis.net/wms"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <Service>
    <Name>WMS</Name>
    <Title>Test WMS</Title>
    <OnlineResource xlink:href="http://example.test/wms"/>
  </Service>
  <Capability>
    <Request>
      <GetCapabilities>
        <Format>text/xml</Format>
        <DCPType><HTTP><Get>
          <OnlineResource xlink:href="http://example.test/wms?"/>
        </Get></HTTP></DCPType>
      </GetCapabilities>
      <GetMap>
        <Format>image/png</Format>
        <DCPType><HTTP><Get>
          <OnlineResource xlink:href="http://example.test/wms?"/>
        </Get></HTTP></DCPType>
      </GetMap>
    </Request>
    <Layer>
      <Title>Root</Title>
      <CRS>EPSG:4326</CRS>
      <Layer queryable="1">
        <Name>test:roads</Name>
        <Title>Roads</Title>
        <Abstract>Test road network.</Abstract>
        <CRS>EPSG:4326</CRS>
        <CRS>EPSG:3857</CRS>
        <EX_GeographicBoundingBox>
          <westBoundLongitude>10.0</westBoundLongitude>
          <eastBoundLongitude>11.0</eastBoundLongitude>
          <southBoundLatitude>50.0</southBoundLatitude>
          <northBoundLatitude>51.0</northBoundLatitude>
        </EX_GeographicBoundingBox>
      </Layer>
    </Layer>
  </Capability>
</WMS_Capabilities>
"""

# A minimal but valid WFS 2.0.0 GetCapabilities document with one feature type.
WFS_CAPABILITIES_200 = """<?xml version="1.0" encoding="UTF-8"?>
<wfs:WFS_Capabilities version="2.0.0"
    xmlns:wfs="http://www.opengis.net/wfs/2.0"
    xmlns:ows="http://www.opengis.net/ows/1.1"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <ows:OperationsMetadata>
    <ows:Operation name="GetFeature">
      <ows:DCP><ows:HTTP>
        <ows:Get xlink:href="http://example.test/wfs?"/>
      </ows:HTTP></ows:DCP>
    </ows:Operation>
  </ows:OperationsMetadata>
  <wfs:FeatureTypeList>
    <wfs:FeatureType>
      <wfs:Name>test:buildings</wfs:Name>
      <wfs:Title>Buildings</wfs:Title>
      <wfs:DefaultCRS>urn:ogc:def:crs:EPSG::4326</wfs:DefaultCRS>
      <ows:WGS84BoundingBox>
        <ows:LowerCorner>10.0 50.0</ows:LowerCorner>
        <ows:UpperCorner>11.0 51.0</ows:UpperCorner>
      </ows:WGS84BoundingBox>
    </wfs:FeatureType>
  </wfs:FeatureTypeList>
</wfs:WFS_Capabilities>
"""

# A tiny GeoJSON FeatureCollection the WFS GetFeature mock returns.
WFS_GEOJSON_RESPONSE = """{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {"type": "Point", "coordinates": [10.5, 50.5]},
      "properties": {"name": "Town Hall"}
    }
  ]
}
"""

# 1x1 transparent PNG (smallest valid PNG), as raw bytes.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
    b"\xc0\xf0\x1f\x00\x05\x05\x02\x00\xa7\x06\x9f\xc4\x00\x00\x00\x00IEND\xaeB`\x82"
)
