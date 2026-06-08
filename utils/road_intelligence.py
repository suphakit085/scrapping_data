import csv
import json
import math
import os
from collections import defaultdict


ROADS_FIELDNAMES = [
    "province",
    "road_name",
    "road_ref",
    "highway_type",
    "osm_id",
    "lat",
    "lon",
    "length_km",
    "lanes",
    "oneway",
    "surface",
    "is_bridge",
]

ROAD_FEATURE_FIELDNAMES = [
    "osm_id",
    "province",
    "road_display_name",
    "road_ref",
    "highway_type",
    "lat",
    "lon",
    "length_km",
    "lanes",
    "lanes_missing",
    "oneway_status",
    "surface",
    "surface_group",
    "has_road_ref",
    "is_unnamed",
    "is_bridge",
    "is_short_segment",
]

ROAD_SUMMARY_FIELDNAMES = [
    "province",
    "segment_count",
    "total_length_km",
    "motorway_km",
    "trunk_km",
    "primary_km",
    "secondary_km",
    "tertiary_km",
    "named_pct",
    "ref_coverage_pct",
    "lanes_coverage_pct",
    "surface_coverage_pct",
    "oneway_known_pct",
]

ROAD_INTERSECTION_FIELDNAMES = [
    "intersection_id",
    "province",
    "lat",
    "lon",
    "connected_way_count",
    "connected_osm_ids",
    "highway_types",
]

ROAD_DENSITY_FIELDNAMES = [
    "zone_name",
    "province",
    "lat",
    "lon",
    "radius_km",
    "road_segment_count",
    "total_road_length_km",
    "motorway_km",
    "trunk_km",
    "primary_km",
    "secondary_km",
    "tertiary_km",
]

HIGHWAY_TYPES = ["motorway", "trunk", "primary", "secondary", "tertiary"]
PAVED_SURFACES = {"asphalt", "concrete", "paved", "concrete:plates", "cobblestone", "bricks", "wood"}
UNPAVED_SURFACES = {"unpaved", "gravel", "dirt", "ground", "compacted"}


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, fieldnames, rows):
    _ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _load_json_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _is_blank(value):
    return str(value or "").strip() in {"", "None", "null"}


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_float(value, digits=3):
    return f"{float(value):.{digits}f}"


def _is_unnamed(road_name):
    return str(road_name or "").strip().startswith("unnamed:")


def road_display_name(row):
    road_name = str(row.get("road_name") or "").strip()
    road_ref = str(row.get("road_ref") or "").strip()
    osm_id = str(row.get("osm_id") or "").strip()

    if road_name and not _is_unnamed(road_name):
        return road_name
    if road_ref:
        return f"Road {road_ref}"
    return road_name or f"unnamed:{osm_id}"


def oneway_status(value):
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "-1"}:
        return "one_way"
    if normalized == "no":
        return "two_way"
    return "unknown"


def surface_group(value):
    normalized = str(value or "").strip().lower()
    if normalized in PAVED_SURFACES:
        return "paved"
    if normalized in UNPAVED_SURFACES:
        return "unpaved"
    return "unknown"


def validate_roads_rows(rows):
    if not rows:
        raise ValueError("roads.csv has no rows")

    missing_headers = [field for field in ROADS_FIELDNAMES if field not in rows[0]]
    if missing_headers:
        raise ValueError(f"roads.csv missing required headers: {', '.join(missing_headers)}")

    seen_osm_ids = set()
    duplicates = set()
    for index, row in enumerate(rows, start=2):
        osm_id = str(row.get("osm_id") or "").strip()
        if not osm_id:
            raise ValueError(f"roads.csv row {index} has blank osm_id")
        if osm_id in seen_osm_ids:
            duplicates.add(osm_id)
        seen_osm_ids.add(osm_id)

        for field in ("lat", "lon", "length_km"):
            try:
                float(row.get(field))
            except (TypeError, ValueError):
                raise ValueError(f"roads.csv row {index} has invalid {field}: {row.get(field)}") from None

    if duplicates:
        sample = ", ".join(sorted(duplicates)[:5])
        raise ValueError(f"roads.csv has duplicate osm_id values: {sample}")


def build_road_feature_row(row):
    road_ref = str(row.get("road_ref") or "").strip()
    lanes = str(row.get("lanes") or "").strip()
    surface = str(row.get("surface") or "").strip()
    length_km = _to_float(row.get("length_km"))

    return {
        "osm_id": row.get("osm_id", ""),
        "province": row.get("province", ""),
        "road_display_name": road_display_name(row),
        "road_ref": road_ref,
        "highway_type": row.get("highway_type", ""),
        "lat": row.get("lat", ""),
        "lon": row.get("lon", ""),
        "length_km": row.get("length_km", ""),
        "lanes": lanes,
        "lanes_missing": _is_blank(lanes),
        "oneway_status": oneway_status(row.get("oneway")),
        "surface": surface,
        "surface_group": surface_group(surface),
        "has_road_ref": bool(road_ref),
        "is_unnamed": _is_unnamed(row.get("road_name")),
        "is_bridge": row.get("is_bridge", ""),
        "is_short_segment": length_km < 0.05,
    }


def build_road_features(rows):
    validate_roads_rows(rows)
    return [build_road_feature_row(row) for row in rows]


def build_summary_by_province(feature_rows):
    by_province = defaultdict(list)
    for row in feature_rows:
        by_province[row.get("province", "")].append(row)

    summaries = []
    for province in sorted(by_province):
        rows = by_province[province]
        segment_count = len(rows)
        total_length = sum(_to_float(row.get("length_km")) for row in rows)

        summary = {
            "province": province,
            "segment_count": segment_count,
            "total_length_km": _format_float(total_length),
            "motorway_km": "",
            "trunk_km": "",
            "primary_km": "",
            "secondary_km": "",
            "tertiary_km": "",
            "named_pct": _format_float(
                100 * sum(str(row.get("is_unnamed")) != "True" for row in rows) / segment_count,
                1,
            ),
            "ref_coverage_pct": _format_float(
                100 * sum(str(row.get("has_road_ref")) == "True" for row in rows) / segment_count,
                1,
            ),
            "lanes_coverage_pct": _format_float(
                100 * sum(str(row.get("lanes_missing")) != "True" for row in rows) / segment_count,
                1,
            ),
            "surface_coverage_pct": _format_float(
                100 * sum(str(row.get("surface_group")) != "unknown" for row in rows) / segment_count,
                1,
            ),
            "oneway_known_pct": _format_float(
                100 * sum(str(row.get("oneway_status")) != "unknown" for row in rows) / segment_count,
                1,
            ),
        }

        for highway_type in HIGHWAY_TYPES:
            length = sum(
                _to_float(row.get("length_km"))
                for row in rows
                if row.get("highway_type") == highway_type
            )
            summary[f"{highway_type}_km"] = _format_float(length)

        summaries.append(summary)

    return summaries


def build_road_intersections(raw_records):
    node_index = {}
    for record in raw_records:
        node_ids = record.get("node_ids") or []
        geometry = record.get("geometry") or []
        if not node_ids or len(node_ids) != len(geometry):
            continue

        for node_id, point in zip(node_ids, geometry):
            node_key = str(node_id)
            if node_key not in node_index:
                node_index[node_key] = {
                    "lat": point.get("lat", ""),
                    "lon": point.get("lon", ""),
                    "province": record.get("province", ""),
                    "osm_ids": set(),
                    "highway_types": set(),
                }
            node_index[node_key]["osm_ids"].add(str(record.get("osm_id", "")))
            node_index[node_key]["highway_types"].add(str(record.get("highway_type", "")))

    intersections = []
    for node_id, data in node_index.items():
        osm_ids = sorted(osm_id for osm_id in data["osm_ids"] if osm_id)
        if len(osm_ids) < 3:
            continue
        intersections.append(
            {
                "intersection_id": f"osm_node:{node_id}",
                "province": data["province"],
                "lat": data["lat"],
                "lon": data["lon"],
                "connected_way_count": len(osm_ids),
                "connected_osm_ids": "|".join(osm_ids),
                "highway_types": "|".join(sorted(data["highway_types"])),
            }
        )

    return sorted(intersections, key=lambda row: (row["province"], row["intersection_id"]))


def _haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


def _load_zone_anchors(zone_profiles_path, landmarks_path):
    zone_rows = _read_csv(zone_profiles_path)
    if zone_rows:
        return [
            {
                "zone_name": row.get("zone_name") or row.get("name") or "",
                "province": row.get("province") or row.get("province_en") or "",
                "lat": row.get("lat", ""),
                "lon": row.get("lon", ""),
            }
            for row in zone_rows
            if not _is_blank(row.get("lat")) and not _is_blank(row.get("lon"))
        ]

    landmark_rows = _read_csv(landmarks_path)
    return [
        {
            "zone_name": row.get("name") or row.get("name_en") or "",
            "province": row.get("province_en") or row.get("province") or "",
            "lat": row.get("lat", ""),
            "lon": row.get("lon", ""),
        }
        for row in landmark_rows
        if str(row.get("layer") or "").strip() == "1"
        and not _is_blank(row.get("lat"))
        and not _is_blank(row.get("lon"))
    ]


def build_road_density_by_zone(feature_rows, zone_anchors, radius_km=2.0):
    density_rows = []
    road_points = [
        {
            **row,
            "_lat": _to_float(row.get("lat")),
            "_lon": _to_float(row.get("lon")),
            "_length_km": _to_float(row.get("length_km")),
        }
        for row in feature_rows
    ]

    for anchor in zone_anchors:
        anchor_lat = _to_float(anchor.get("lat"))
        anchor_lon = _to_float(anchor.get("lon"))
        province = str(anchor.get("province") or "")
        nearby = []

        for road in road_points:
            if province and road.get("province") != province:
                continue
            if _haversine_km(anchor_lat, anchor_lon, road["_lat"], road["_lon"]) <= radius_km:
                nearby.append(road)

        row = {
            "zone_name": anchor.get("zone_name", ""),
            "province": province,
            "lat": anchor.get("lat", ""),
            "lon": anchor.get("lon", ""),
            "radius_km": _format_float(radius_km, 1),
            "road_segment_count": len(nearby),
            "total_road_length_km": _format_float(sum(r["_length_km"] for r in nearby)),
        }
        for highway_type in HIGHWAY_TYPES:
            row[f"{highway_type}_km"] = _format_float(
                sum(r["_length_km"] for r in nearby if r.get("highway_type") == highway_type)
            )
        density_rows.append(row)

    return density_rows


def build_road_intelligence_outputs(
    roads_path="data/processed/roads.csv",
    raw_roads_path="data/raw/roads_raw.json",
    features_path="data/processed/roads_features.csv",
    summary_path="data/processed/roads_summary_by_province.csv",
    intersections_path="data/processed/road_intersections.csv",
    density_path="data/processed/road_density_by_zone.csv",
    zone_profiles_path="data/processed/zone_profiles.csv",
    landmarks_path="data/processed/landmarks_clean.csv",
    radius_km=2.0,
):
    roads = _read_csv(roads_path)
    features = build_road_features(roads)
    summaries = build_summary_by_province(features)
    intersections = build_road_intersections(_load_json_list(raw_roads_path))
    zone_anchors = _load_zone_anchors(zone_profiles_path, landmarks_path)
    density_rows = build_road_density_by_zone(features, zone_anchors, radius_km=radius_km)

    _write_csv(features_path, ROAD_FEATURE_FIELDNAMES, features)
    _write_csv(summary_path, ROAD_SUMMARY_FIELDNAMES, summaries)
    _write_csv(intersections_path, ROAD_INTERSECTION_FIELDNAMES, intersections)
    _write_csv(density_path, ROAD_DENSITY_FIELDNAMES, density_rows)

    return {
        "features": len(features),
        "summaries": len(summaries),
        "intersections": len(intersections),
        "density_rows": len(density_rows),
    }


if __name__ == "__main__":
    result = build_road_intelligence_outputs()
    print(
        "[Success] Road intelligence outputs generated: "
        f"{result['features']} features, "
        f"{result['summaries']} province summaries, "
        f"{result['intersections']} intersections, "
        f"{result['density_rows']} zone density rows"
    )
