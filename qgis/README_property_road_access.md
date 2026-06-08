# Property Road Access QGIS View

## Main Route Layer

Open this route layer in QGIS:

```text
C:\ai_web_scrpping\data\processed\property_road_access_khonkaen.geojson
```

Apply style:

```text
C:\ai_web_scrpping\qgis\property_road_access_routes.qml
```

Recommended filter for the first view:

```sql
"routing_status" = 'routed'
```

## Issue Point Layer

The route GeoJSON only contains features that have drawable route geometry. To see rows without route lines, export the issue points:

```powershell
python run_property_road_access_qgis_export.py
```

This writes:

```text
C:\ai_web_scrpping\data\processed\property_road_access_khonkaen_issue_points.geojson
```

Apply style:

```text
C:\ai_web_scrpping\qgis\property_road_access_points.qml
```

## Status Colors

- `routed`: green
- `already_on_major`: blue
- `no_nearby_local_road`: red
- `no_major_reachable`: orange
- `invalid_coordinates`: black

## QGIS Notes

The full route GeoJSON is about 809 MB, so loading can take time. If QGIS feels slow, start with the issue point layer or apply a filter before heavy styling.
