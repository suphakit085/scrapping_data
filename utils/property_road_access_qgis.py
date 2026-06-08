import csv
import json
import os


DEFAULT_ISSUE_STATUSES = {
    "no_nearby_local_road",
    "no_major_reachable",
    "invalid_coordinates",
}

POINT_PROPERTY_FIELDS = [
    "property_id",
    "chanod_no",
    "province",
    "snap_distance_m",
    "nearest_local_road_osm_id",
    "nearest_local_road_display_name",
    "major_road_osm_id",
    "major_road_display_name",
    "major_highway_type",
    "distance_home_to_soi_mouth_m",
    "routing_status",
    "confidence",
]


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_statuses(value):
    if value is None:
        return set(DEFAULT_ISSUE_STATUSES)
    if isinstance(value, str):
        return {status.strip() for status in value.split(",") if status.strip()}
    return {str(status).strip() for status in value if str(status).strip()}


def _feature_for_row(row):
    lat = _to_float(row.get("home_lat"))
    lon = _to_float(row.get("home_lon"))
    if lat is None or lon is None:
        return None
    return {
        "type": "Feature",
        "properties": {
            field: row.get(field, "")
            for field in POINT_PROPERTY_FIELDS
        },
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
    }


def export_property_points_geojson(
    csv_path,
    output_path,
    statuses=None,
    limit=None,
):
    statuses = _parse_statuses(statuses)
    _ensure_parent_dir(output_path)

    count = 0
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.DictReader(input_file)
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write('{"type":"FeatureCollection","features":[\n')
            first = True
            for row in reader:
                if statuses and row.get("routing_status") not in statuses:
                    continue
                feature = _feature_for_row(row)
                if not feature:
                    continue
                if not first:
                    output_file.write(",\n")
                json.dump(feature, output_file, ensure_ascii=False, separators=(",", ":"))
                first = False
                count += 1
                if limit is not None and count >= limit:
                    break
            output_file.write("\n]}\n")

    return {
        "output_path": output_path,
        "features": count,
        "statuses": sorted(statuses),
    }
