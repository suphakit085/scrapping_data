<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="routing_status" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="no_nearby_local_road" label="no_nearby_local_road" symbol="0" render="true"/>
      <category value="no_major_reachable" label="no_major_reachable" symbol="1" render="true"/>
      <category value="invalid_coordinates" label="invalid_coordinates" symbol="2" render="true"/>
      <category value="routed" label="routed" symbol="3" render="true"/>
      <category value="already_on_major" label="already_on_major" symbol="4" render="true"/>
    </categories>
    <symbols>
      <symbol type="marker" name="0" alpha="0.9" clip_to_extent="1">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="220,38,38,255"/>
            <Option name="outline_color" type="QString" value="255,255,255,255"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="size" type="QString" value="1.8"/>
            <Option name="name" type="QString" value="circle"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="1" alpha="0.9" clip_to_extent="1">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="245,130,32,255"/>
            <Option name="outline_color" type="QString" value="255,255,255,255"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="size" type="QString" value="1.8"/>
            <Option name="name" type="QString" value="circle"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="2" alpha="0.95" clip_to_extent="1">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="0,0,0,255"/>
            <Option name="outline_color" type="QString" value="255,255,255,255"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="size" type="QString" value="2.0"/>
            <Option name="name" type="QString" value="circle"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="3" alpha="0.5" clip_to_extent="1">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="0,166,81,255"/>
            <Option name="outline_color" type="QString" value="255,255,255,0"/>
            <Option name="size" type="QString" value="1.0"/>
            <Option name="name" type="QString" value="circle"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="4" alpha="0.5" clip_to_extent="1">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="color" type="QString" value="0,114,188,255"/>
            <Option name="outline_color" type="QString" value="255,255,255,0"/>
            <Option name="size" type="QString" value="1.0"/>
            <Option name="name" type="QString" value="circle"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
