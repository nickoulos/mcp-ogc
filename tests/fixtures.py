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

# A minimal WMTS 1.0.0 GetCapabilities document: one layer linked to three tile
# matrix sets. TopLeftCorner follows each CRS's own axis order, as the WMTS spec
# requires: EPSG:3006 and EPSG:4326 are northing-first, EPSG:3857 easting-first.
WMTS_CAPABILITIES_100 = """<?xml version="1.0" encoding="UTF-8"?>
<Capabilities version="1.0.0"
    xmlns="http://www.opengis.net/wmts/1.0"
    xmlns:ows="http://www.opengis.net/ows/1.1"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <ows:ServiceIdentification>
    <ows:Title>Test WMTS</ows:Title>
    <ows:ServiceType>OGC WMTS</ows:ServiceType>
    <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
  </ows:ServiceIdentification>
  <ows:OperationsMetadata>
    <ows:Operation name="GetCapabilities">
      <ows:DCP><ows:HTTP><ows:Get xlink:href="http://example.test/wmts?">
        <ows:Constraint name="GetEncoding"><ows:AllowedValues>
          <ows:Value>KVP</ows:Value>
        </ows:AllowedValues></ows:Constraint>
      </ows:Get></ows:HTTP></ows:DCP>
    </ows:Operation>
    <ows:Operation name="GetTile">
      <ows:DCP><ows:HTTP><ows:Get xlink:href="http://example.test/wmts?">
        <ows:Constraint name="GetEncoding"><ows:AllowedValues>
          <ows:Value>KVP</ows:Value>
        </ows:AllowedValues></ows:Constraint>
      </ows:Get></ows:HTTP></ows:DCP>
    </ows:Operation>
  </ows:OperationsMetadata>
  <Contents>
    <Layer>
      <ows:Title>Basemap</ows:Title>
      <ows:Abstract>Test basemap.</ows:Abstract>
      <ows:WGS84BoundingBox>
        <ows:LowerCorner>10.0 50.0</ows:LowerCorner>
        <ows:UpperCorner>11.0 51.0</ows:UpperCorner>
      </ows:WGS84BoundingBox>
      <ows:Identifier>test:basemap</ows:Identifier>
      <Style isDefault="false"><ows:Identifier>night</ows:Identifier></Style>
      <Style isDefault="true"><ows:Identifier>default</ows:Identifier></Style>
      <Format>image/jpeg</Format>
      <Format>image/png</Format>
      <TileMatrixSetLink><TileMatrixSet>WebMercatorQuad</TileMatrixSet></TileMatrixSetLink>
      <TileMatrixSetLink><TileMatrixSet>sweref99tm</TileMatrixSet></TileMatrixSetLink>
      <TileMatrixSetLink><TileMatrixSet>wgs84</TileMatrixSet></TileMatrixSetLink>
    </Layer>
    <TileMatrixSet>
      <ows:Identifier>WebMercatorQuad</ows:Identifier>
      <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
      <TileMatrix>
        <ows:Identifier>0</ows:Identifier>
        <ScaleDenominator>559082264.0287178</ScaleDenominator>
        <TopLeftCorner>-20037508.3427892 20037508.3427892</TopLeftCorner>
        <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
        <MatrixWidth>1</MatrixWidth><MatrixHeight>1</MatrixHeight>
      </TileMatrix>
      <TileMatrix>
        <ows:Identifier>1</ows:Identifier>
        <ScaleDenominator>279541132.0143589</ScaleDenominator>
        <TopLeftCorner>-20037508.3427892 20037508.3427892</TopLeftCorner>
        <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
        <MatrixWidth>2</MatrixWidth><MatrixHeight>2</MatrixHeight>
      </TileMatrix>
    </TileMatrixSet>
    <TileMatrixSet>
      <ows:Identifier>sweref99tm</ows:Identifier>
      <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3006</ows:SupportedCRS>
      <TileMatrix>
        <ows:Identifier>0</ows:Identifier>
        <!-- 4096 m per pixel: 4096 / 0.00028 -->
        <ScaleDenominator>14628571.428571429</ScaleDenominator>
        <TopLeftCorner>8500000 -1200000</TopLeftCorner>
        <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
        <MatrixWidth>5</MatrixWidth><MatrixHeight>4</MatrixHeight>
      </TileMatrix>
    </TileMatrixSet>
    <TileMatrixSet>
      <ows:Identifier>wgs84</ows:Identifier>
      <ows:SupportedCRS>urn:ogc:def:crs:EPSG::4326</ows:SupportedCRS>
      <TileMatrix>
        <ows:Identifier>0</ows:Identifier>
        <!-- 0.703125 degrees per pixel, so one 256 px tile spans 180 degrees -->
        <ScaleDenominator>279541132.0143589</ScaleDenominator>
        <TopLeftCorner>90 -180</TopLeftCorner>
        <TileWidth>256</TileWidth><TileHeight>256</TileHeight>
        <MatrixWidth>2</MatrixWidth><MatrixHeight>1</MatrixHeight>
      </TileMatrix>
    </TileMatrixSet>
  </Contents>
</Capabilities>
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
