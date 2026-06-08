<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34" styleCategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="routing_status" symbollevels="0" enableorderby="0" forceraster="0">
    <categories>
      <category value="routed" label="routed" symbol="0" render="true"/>
      <category value="already_on_major" label="already_on_major" symbol="1" render="true"/>
      <category value="no_nearby_local_road" label="no_nearby_local_road" symbol="2" render="true"/>
      <category value="no_major_reachable" label="no_major_reachable" symbol="3" render="true"/>
      <category value="invalid_coordinates" label="invalid_coordinates" symbol="4" render="true"/>
    </categories>
    <symbols>
      <symbol type="line" name="0" alpha="0.75" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,166,81,255"/>
            <Option name="line_width" type="QString" value="0.35"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="line" name="1" alpha="0.75" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,114,188,255"/>
            <Option name="line_width" type="QString" value="0.45"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="line" name="2" alpha="0.9" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="220,38,38,255"/>
            <Option name="line_style" type="QString" value="dash"/>
            <Option name="line_width" type="QString" value="0.5"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="line" name="3" alpha="0.9" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="245,130,32,255"/>
            <Option name="line_style" type="QString" value="dash"/>
            <Option name="line_width" type="QString" value="0.5"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="line" name="4" alpha="0.95" clip_to_extent="1">
        <layer class="SimpleLine" enabled="1" locked="0" pass="0">
          <Option type="Map">
            <Option name="line_color" type="QString" value="0,0,0,255"/>
            <Option name="line_width" type="QString" value="0.6"/>
            <Option name="line_width_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
</qgis>
