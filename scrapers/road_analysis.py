import csv
import json
import math
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone

import requests
from shapely.geometry import LineString, Point, box, shape

from utils.geo_boundaries import TARGET_PROVINCES, normalize_province_name, repo_path


DEFAULT_OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.vi-di.fr/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
HEADERS = {
    "User-Agent": "RealEstateBIProject/1.0 (contact: researcher@example.com)",
    "Accept": "application/json",
    "Accept-Language": "en",
}

ROAD_HIGHWAY_TYPES = [
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "service",
]

ROAD_HIGHWAY_GROUPS = {
    "major": ["motorway", "trunk", "primary", "secondary", "tertiary"],
    "local": ["residential", "unclassified", "service"],
}

_PROVINCE_GEOMETRY_CACHE = None
DEFAULT_LOCAL_TILE_DEGREES = 0.25
DEFAULT_TILE_MAX_SPLIT_DEPTH = 2
RAW_TOPOLOGY_MIN_COVERAGE_PCT = 95.0
RAW_REQUIRED_FIELDS = [
    "province",
    "osm_id",
    "osm_type",
    "road_name",
    "road_ref",
    "highway_type",
    "extraction_group",
    "lat",
    "lon",
    "length_km",
    "node_ids",
    "geometry",
    "tags",
    "source",
    "osm_url",
    "fetched_at",
]
RAW_REQUIRED_NONEMPTY_FIELDS = set(RAW_REQUIRED_FIELDS) - {"road_ref"}
RAW_REQUIRED_NONEMPTY_COLLECTION_FIELDS = {"node_ids", "geometry", "tags"}


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _load_json_list(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_json(path, records):
    path = os.path.abspath(os.path.normpath(path))
    _ensure_parent_dir(path)
    temp_path = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    last_error = None
    for attempt in range(10):
        try:
            os.replace(temp_path, path)
            return True
        except (OSError, PermissionError) as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))

    fallback_path = f"{path}.pending-{uuid.uuid4().hex}.json"
    try:
        os.replace(temp_path, fallback_path)
    except OSError:
        fallback_path = temp_path

    print(
        "[Warning] Could not replace JSON file because Windows denied access. "
        f"Latest snapshot left at {fallback_path}. Error: {last_error}"
    )
    return False


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def _estimate_way_length_km(geometry):
    if not geometry or len(geometry) < 2:
        return 0.0

    total = 0.0
    prev = geometry[0]
    for point in geometry[1:]:
        total += _haversine_km(
            float(prev["lat"]),
            float(prev["lon"]),
            float(point["lat"]),
            float(point["lon"]),
        )
        prev = point
    return round(total, 3)


def _centroid_from_geometry(geometry, center=None):
    if center and center.get("lat") is not None and center.get("lon") is not None:
        return round(float(center["lat"]), 7), round(float(center["lon"]), 7)
    if not geometry:
        return None, None
    lat = sum(float(p["lat"]) for p in geometry) / len(geometry)
    lon = sum(float(p["lon"]) for p in geometry) / len(geometry)
    return round(lat, 7), round(lon, 7)


def _safe_filename(value):
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return cleaned or "unknown"


def _temp_cache_path(temp_dir, province, group_name):
    return os.path.join(temp_dir, f"{_safe_filename(province)}_{group_name}.json")


def _overpass_urls():
    env_urls = os.environ.get("OVERPASS_URLS") or os.environ.get("OVERPASS_URL")
    if env_urls:
        urls = []
        for url in env_urls.split(","):
            cleaned = re.sub(r"\s+", "", url)
            if cleaned:
                urls.append(cleaned)
        return urls
    return DEFAULT_OVERPASS_URLS


def _selected_road_groups(groups=None):
    raw_groups = groups
    if raw_groups is None:
        env_groups = os.environ.get("ROAD_GROUPS")
        if env_groups:
            raw_groups = [g.strip() for g in env_groups.split(",")]

    if raw_groups is None:
        return ROAD_HIGHWAY_GROUPS

    if isinstance(raw_groups, str):
        raw_groups = [g.strip() for g in raw_groups.split(",")]

    selected = {}
    invalid = []
    for group_name in raw_groups:
        normalized = str(group_name).strip().lower()
        if not normalized:
            continue
        if normalized not in ROAD_HIGHWAY_GROUPS:
            invalid.append(group_name)
            continue
        selected[normalized] = ROAD_HIGHWAY_GROUPS[normalized]

    if invalid:
        raise ValueError(f"Invalid ROAD_GROUPS value(s): {', '.join(invalid)}")
    if not selected:
        raise ValueError("No road groups selected")

    return selected


def _selected_provinces(provinces=None):
    raw_provinces = provinces
    if raw_provinces is None:
        env_provinces = os.environ.get("ROAD_PROVINCES")
        if env_provinces:
            raw_provinces = [p.strip() for p in env_provinces.split(",")]

    if raw_provinces is None:
        return sorted(TARGET_PROVINCES)

    if isinstance(raw_provinces, str):
        raw_provinces = [p.strip() for p in raw_provinces.split(",")]

    target_set = {normalize_province_name(p) for p in TARGET_PROVINCES}
    selected = []
    invalid = []
    seen = set()
    for province in raw_provinces:
        normalized = normalize_province_name(province)
        if not normalized:
            continue
        if normalized not in target_set:
            invalid.append(str(province))
            continue
        if normalized not in seen:
            selected.append(normalized)
            seen.add(normalized)

    if invalid:
        raise ValueError(f"Invalid ROAD_PROVINCES value(s): {', '.join(invalid)}")
    if not selected:
        raise ValueError("No target provinces selected")

    return sorted(selected)


def _load_province_geometries():
    global _PROVINCE_GEOMETRY_CACHE
    if _PROVINCE_GEOMETRY_CACHE is not None:
        return _PROVINCE_GEOMETRY_CACHE

    boundary_path = repo_path("data/raw/target_admin_boundaries.geojson")
    with open(boundary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    geometries = {}
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        province = normalize_province_name(
            props.get("adm1_name_normalized") or props.get("adm1_name")
        )
        if province:
            geometries[province] = shape(feature["geometry"])

    _PROVINCE_GEOMETRY_CACHE = geometries
    return geometries


def _province_geometry(province):
    province = normalize_province_name(province)
    geom = _load_province_geometries().get(province)
    if geom is None:
        raise ValueError(f"Missing target boundary geometry for province: {province}")
    return geom


def _build_bbox_road_query(highway_types, bbox):
    highway_regex = "|".join(re.escape(t) for t in highway_types)
    min_lon, min_lat, max_lon, max_lat = bbox
    return f"""
    [out:json][timeout:180];
    (
      way["highway"~"^({highway_regex})$"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    out body geom;
    """


def _build_province_road_query(province, highway_types):
    return _build_bbox_road_query(highway_types, _province_geometry(province).bounds)


def _local_tile_degrees():
    raw = os.environ.get("ROAD_LOCAL_TILE_DEGREES")
    if not raw:
        return DEFAULT_LOCAL_TILE_DEGREES
    try:
        value = float(raw)
        return value if value > 0 else DEFAULT_LOCAL_TILE_DEGREES
    except ValueError:
        return DEFAULT_LOCAL_TILE_DEGREES


def _tile_max_split_depth():
    raw = os.environ.get("ROAD_TILE_MAX_SPLIT_DEPTH")
    if not raw:
        return DEFAULT_TILE_MAX_SPLIT_DEPTH
    try:
        value = int(raw)
        return value if value >= 0 else DEFAULT_TILE_MAX_SPLIT_DEPTH
    except ValueError:
        return DEFAULT_TILE_MAX_SPLIT_DEPTH


def _province_tiles(province, tile_degrees=None):
    geom = _province_geometry(province)
    min_lon, min_lat, max_lon, max_lat = geom.bounds
    step = tile_degrees or _local_tile_degrees()
    tiles = []

    lat = min_lat
    while lat < max_lat:
        next_lat = min(lat + step, max_lat)
        lon = min_lon
        while lon < max_lon:
            next_lon = min(lon + step, max_lon)
            tile_bbox = (lon, lat, next_lon, next_lat)
            if geom.intersects(box(*tile_bbox)):
                tiles.append(tile_bbox)
            lon = next_lon
        lat = next_lat

    return tiles


def _split_bbox(bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    mid_lon = (min_lon + max_lon) / 2
    mid_lat = (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]


def _request_overpass(query, retries=3, timeout=220):
    last_error = None
    urls = _overpass_urls()
    for attempt in range(1, retries + 1):
        for url in urls:
            try:
                response = requests.get(
                    url,
                    params={"data": query},
                    headers=HEADERS,
                    timeout=(15, timeout),
                )
                if response.status_code == 200:
                    return response.json()
                last_error = f"{url} HTTP {response.status_code}: {response.text[:200]}"
            except Exception as exc:
                last_error = f"{url}: {exc}"

        if attempt < retries:
            wait_seconds = 5 * attempt
            print(
                f"    [Retry] Overpass request failed ({last_error}); "
                f"waiting {wait_seconds}s"
            )
            time.sleep(wait_seconds)

    raise RuntimeError(last_error or "Overpass request failed")


def _road_geometry_intersects_province(element, province):
    geom = _province_geometry(province)
    points = [
        (float(p["lon"]), float(p["lat"]))
        for p in element.get("geometry") or []
        if p.get("lat") is not None and p.get("lon") is not None
    ]

    if len(points) >= 2:
        return geom.intersects(LineString(points))
    if len(points) == 1:
        return geom.contains(Point(points[0])) or geom.intersects(Point(points[0]))

    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        point = Point(float(center["lon"]), float(center["lat"]))
        return geom.contains(point) or geom.intersects(point)

    return False


def _normalize_road_record(element, province, extraction_group):
    tags = element.get("tags") or {}
    geometry = element.get("geometry") or []
    lat, lon = _centroid_from_geometry(geometry, element.get("center"))
    osm_id = element.get("id")
    name = str(tags.get("name") or "").strip()
    is_named = bool(name)
    road_name = name if is_named else f"unnamed:{osm_id}"

    return {
        "province": normalize_province_name(province),
        "road_name": road_name,
        "is_named": is_named,
        "highway_type": tags.get("highway", ""),
        "road_ref": tags.get("ref", ""),
        "int_ref": tags.get("int_ref", ""),
        "lanes": tags.get("lanes", ""),
        "oneway": tags.get("oneway", ""),
        "bridge": tags.get("bridge", ""),
        "tunnel": tags.get("tunnel", ""),
        "surface": tags.get("surface", ""),
        "maxspeed": tags.get("maxspeed", ""),
        "access": tags.get("access", ""),
        "osm_id": osm_id,
        "osm_type": element.get("type", "way"),
        "lat": lat,
        "lon": lon,
        "length_km": _estimate_way_length_km(geometry),
        "node_ids": element.get("nodes", []),
        "geometry": geometry,
        "source": "OpenStreetMap / Overpass API",
        "osm_url": f"https://www.openstreetmap.org/way/{osm_id}" if osm_id else "",
        "extraction_group": extraction_group,
        "fetched_at": _utc_now_iso(),
        "tags": tags,
    }


def _fetch_province_group(
    province,
    group_name,
    highway_types,
    temp_dir=None,
    require_topology=False,
):
    query = _build_province_road_query(province, highway_types)
    try:
        data = _request_overpass(query)
    except Exception:
        if temp_dir:
            print("tiling group...", end=" ", flush=True)
            return _fetch_split_group_with_cache(
                province,
                group_name,
                highway_types,
                temp_dir,
                require_topology=require_topology,
            )

        if len(highway_types) == 1:
            raise

        print("splitting group...", end=" ", flush=True)
        merged_records = []
        for highway_type in highway_types:
            data = _request_overpass(
                _build_province_road_query(province, [highway_type])
            )
            ways = [e for e in data.get("elements", []) if e.get("type") == "way"]
            merged_records.extend(
                _normalize_road_record(e, province, f"{group_name}:{highway_type}")
                for e in ways
                if (e.get("tags") or {}).get("highway") == highway_type
                and _road_geometry_intersects_province(e, province)
            )
            time.sleep(1.0)
        return merged_records

    ways = [e for e in data.get("elements", []) if e.get("type") == "way"]
    return [
        _normalize_road_record(e, province, group_name)
        for e in ways
        if (e.get("tags") or {}).get("highway") in highway_types
        and _road_geometry_intersects_province(e, province)
    ]


def _dedupe_road_records(records):
    deduped = []
    seen = set()
    for record in records:
        osm_id = record.get("osm_id")
        if osm_id in seen:
            continue
        seen.add(osm_id)
        deduped.append(record)
    return deduped


def _fetch_highway_type_by_tiles(
    province,
    group_name,
    highway_type,
    temp_dir,
    require_topology=False,
):
    records = []
    tiles = _province_tiles(province)
    total_tiles = len(tiles)

    for index, bbox in enumerate(tiles, start=1):
        tile_group_name = f"{group_name}_{highway_type}_tile_{index:03d}"
        tile_records = _fetch_tile_with_cache(
            province,
            group_name,
            highway_type,
            bbox,
            temp_dir,
            tile_group_name,
            depth=0,
            require_topology=require_topology,
        )

        records.extend(tile_records)
        if index % 20 == 0 or index == total_tiles:
            print(f"{index}/{total_tiles}", end=" ", flush=True)

    return _dedupe_road_records(records)


def _fetch_tile_with_cache(
    province,
    group_name,
    highway_type,
    bbox,
    temp_dir,
    tile_group_name,
    depth=0,
    require_topology=False,
):
    tile_path = _temp_cache_path(temp_dir, province, tile_group_name)
    failed_path = tile_path.replace(".json", ".failed.json")
    if os.path.exists(tile_path):
        cached_records = _load_json_list(tile_path)
        if not require_topology or _cache_has_raw_contract(cached_records):
            print(".", end="", flush=True)
            return cached_records

    try:
        query = _build_bbox_road_query([highway_type], bbox)
        data = _request_overpass(query)
        ways = [e for e in data.get("elements", []) if e.get("type") == "way"]
        tile_records = [
            _normalize_road_record(e, province, f"{group_name}:{highway_type}")
            for e in ways
            if (e.get("tags") or {}).get("highway") == highway_type
            and _road_geometry_intersects_province(e, province)
        ]
        _save_json(tile_path, tile_records)
        if os.path.exists(failed_path):
            os.remove(failed_path)
        print(".", end="", flush=True)
        time.sleep(0.4)
        return tile_records
    except Exception as exc:
        if depth < _tile_max_split_depth():
            print("s", end="", flush=True)
            split_records = []
            for sub_index, sub_bbox in enumerate(_split_bbox(bbox), start=1):
                if not _province_geometry(province).intersects(box(*sub_bbox)):
                    continue
                split_records.extend(
                    _fetch_tile_with_cache(
                        province,
                        group_name,
                        highway_type,
                        sub_bbox,
                        temp_dir,
                        f"{tile_group_name}_{sub_index}",
                        depth=depth + 1,
                        require_topology=require_topology,
                    )
                )
            split_records = _dedupe_road_records(split_records)
            if split_records:
                _save_json(tile_path, split_records)
            return split_records

        failure = {
            "province": normalize_province_name(province),
            "highway_type": highway_type,
            "tile": tile_group_name,
            "bbox": bbox,
            "error": str(exc),
        }
        _save_json(failed_path, failure)
        print("!", end="", flush=True)
        return []


def _fetch_split_group_with_cache(
    province,
    group_name,
    highway_types,
    temp_dir,
    require_topology=False,
):
    records = []
    for highway_type in highway_types:
        sub_group_name = f"{group_name}_{highway_type}"
        sub_path = _temp_cache_path(temp_dir, province, sub_group_name)
        if os.path.exists(sub_path) and (
            not require_topology or _cache_has_raw_contract(_load_json_list(sub_path))
        ):
            sub_records = _load_json_list(sub_path)
            print(f"{highway_type}:cached({len(sub_records)})", end=" ", flush=True)
        else:
            print(f"{highway_type}:tiles ", end="", flush=True)
            sub_records = _fetch_highway_type_by_tiles(
                province,
                group_name,
                highway_type,
                temp_dir,
                require_topology=require_topology,
            )
            _save_json(sub_path, sub_records)
            print(f"{len(sub_records)}", end=" ", flush=True)
            time.sleep(1.0)
        records.extend(sub_records)
    return records


def _write_roads_csv(records, output_path):
    _ensure_parent_dir(output_path)
    fieldnames = [
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
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(_road_csv_row(record, fieldnames))


def _tag_value(record, key, default=""):
    tags = record.get("tags") or {}
    value = record.get(key)
    if value not in (None, ""):
        return value
    return tags.get(key, default)


def _is_truthy_osm_value(value):
    return str(value or "").strip().lower() in {"yes", "true", "1"}


def _road_quality_flags(record):
    flags = []
    tags = record.get("tags") or {}
    highway_type = str(record.get("highway_type") or tags.get("highway") or "")
    length_km = float(record.get("length_km") or 0)

    if not record.get("is_named"):
        flags.append("unnamed")
    if not _tag_value(record, "road_ref", tags.get("ref", "")):
        flags.append("no_ref")
    if length_km and length_km < 0.05:
        flags.append("short_segment")
    if highway_type.endswith("_link"):
        flags.append("link")
    if highway_type == "service":
        flags.append("service_road")
    if tags.get("access") in {"private", "no", "destination"}:
        flags.append(f"access_{tags.get('access')}")

    return flags


def _road_quality_confidence(record):
    tags = record.get("tags") or {}
    if _tag_value(record, "road_ref", tags.get("ref", "")):
        return "high"
    if record.get("is_named"):
        return "medium"
    return "low"


def _records_have_topology(records):
    if not records:
        return False
    for record in records:
        node_ids = record.get("node_ids") or []
        geometry = record.get("geometry") or []
        if not node_ids or not geometry or len(node_ids) != len(geometry):
            return False
    return True


def _records_have_raw_contract(records):
    if not _records_have_topology(records):
        return False
    for record in records:
        for field in RAW_REQUIRED_FIELDS:
            if field not in record:
                return False
            if field in RAW_REQUIRED_NONEMPTY_COLLECTION_FIELDS:
                if not record.get(field):
                    return False
            elif field in RAW_REQUIRED_NONEMPTY_FIELDS and str(record.get(field) or "").strip() == "":
                return False
    return True


def _cache_has_raw_contract(records):
    if not records:
        return True
    return _records_have_raw_contract(records)


def _pct(count, total):
    if not total:
        return 0.0
    return round((count / total) * 100, 2)


def _build_roads_raw_quality_report(records, expected_highway_types=None, target_provinces=None):
    expected_highway_types = list(expected_highway_types or [])
    target_provinces = sorted(normalize_province_name(p) for p in (target_provinces or []))
    total = len(records)
    osm_ids = [str(r.get("osm_id") or "").strip() for r in records]
    osm_id_counts = Counter(osm_ids)
    duplicate_osm_ids = sorted(
        osm_id for osm_id, count in osm_id_counts.items() if osm_id and count > 1
    )

    geometry_count = 0
    node_ids_count = 0
    topology_match_count = 0
    topology_mismatch_samples = []
    missing_required_counts = Counter()
    missing_raw_contract_counts = Counter()
    missing_tag_counts = Counter()

    for record in records:
        geometry = record.get("geometry") or []
        node_ids = record.get("node_ids") or []
        if geometry:
            geometry_count += 1
        if node_ids:
            node_ids_count += 1
        if geometry and node_ids and len(geometry) == len(node_ids):
            topology_match_count += 1
        elif len(topology_mismatch_samples) < 10:
            topology_mismatch_samples.append(
                {
                    "osm_id": record.get("osm_id", ""),
                    "geometry_points": len(geometry),
                    "node_ids": len(node_ids),
                }
            )

        for field in ("province", "osm_id", "highway_type"):
            if str(record.get(field) or "").strip() == "":
                missing_required_counts[field] += 1

        for field in RAW_REQUIRED_FIELDS:
            if field not in record:
                missing_raw_contract_counts[field] += 1
                continue
            if field in RAW_REQUIRED_NONEMPTY_COLLECTION_FIELDS:
                if not record.get(field):
                    missing_raw_contract_counts[field] += 1
            elif field in RAW_REQUIRED_NONEMPTY_FIELDS and str(record.get(field) or "").strip() == "":
                missing_raw_contract_counts[field] += 1

        tags = record.get("tags") or {}
        for tag_name in ("name", "ref", "lanes", "oneway", "surface"):
            if str(tags.get(tag_name) or "").strip() == "":
                missing_tag_counts[tag_name] += 1

    province_counts = Counter(str(r.get("province") or "").strip() for r in records)
    highway_counts = Counter(str(r.get("highway_type") or "").strip() for r in records)
    provinces_present = sorted(p for p in province_counts if p)
    highway_types_present = sorted(h for h in highway_counts if h)

    geometry_coverage_pct = _pct(geometry_count, total)
    node_ids_coverage_pct = _pct(node_ids_count, total)
    topology_match_pct = _pct(topology_match_count, total)

    report = {
        "generated_at": _utc_now_iso(),
        "total_records": total,
        "quality_pass": (
            total > 0
            and not duplicate_osm_ids
            and all(count == 0 for count in missing_required_counts.values())
            and all(count == 0 for count in missing_raw_contract_counts.values())
            and geometry_coverage_pct >= RAW_TOPOLOGY_MIN_COVERAGE_PCT
            and node_ids_coverage_pct >= RAW_TOPOLOGY_MIN_COVERAGE_PCT
            and topology_match_pct >= RAW_TOPOLOGY_MIN_COVERAGE_PCT
            and not (set(expected_highway_types) - set(highway_types_present))
            and not (set(provinces_present) - set(target_provinces) if target_provinces else set())
        ),
        "expected_highway_types": expected_highway_types,
        "highway_types_present": highway_types_present,
        "missing_highway_types": sorted(set(expected_highway_types) - set(highway_types_present)),
        "target_provinces": target_provinces,
        "provinces_present": provinces_present,
        "missing_target_provinces": sorted(set(target_provinces) - set(provinces_present)),
        "unexpected_provinces": sorted(set(provinces_present) - set(target_provinces)) if target_provinces else [],
        "counts_by_province": dict(sorted(province_counts.items())),
        "counts_by_highway_type": dict(sorted(highway_counts.items())),
        "duplicate_osm_id_count": len(duplicate_osm_ids),
        "duplicate_osm_id_samples": duplicate_osm_ids[:10],
        "missing_required_counts": dict(sorted(missing_required_counts.items())),
        "missing_raw_contract_counts": dict(sorted(missing_raw_contract_counts.items())),
        "topology": {
            "geometry_count": geometry_count,
            "geometry_coverage_pct": geometry_coverage_pct,
            "node_ids_count": node_ids_count,
            "node_ids_coverage_pct": node_ids_coverage_pct,
            "topology_match_count": topology_match_count,
            "topology_match_pct": topology_match_pct,
            "topology_mismatch_count": total - topology_match_count,
            "topology_mismatch_samples": topology_mismatch_samples,
            "min_required_coverage_pct": RAW_TOPOLOGY_MIN_COVERAGE_PCT,
        },
        "missing_tag_report": {
            tag: {
                "missing_count": missing_tag_counts[tag],
                "missing_pct": _pct(missing_tag_counts[tag], total),
            }
            for tag in ("name", "ref", "lanes", "oneway", "surface")
        },
    }
    return report


def _road_csv_row(record, fieldnames):
    tags = record.get("tags") or {}
    highway_type = record.get("highway_type") or tags.get("highway", "")
    road_ref = _tag_value(record, "road_ref", tags.get("ref", ""))
    bridge = _tag_value(record, "bridge", tags.get("bridge", ""))

    row = {
        "province": record.get("province", ""),
        "road_name": record.get("road_name", ""),
        "road_ref": road_ref,
        "highway_type": highway_type,
        "osm_id": record.get("osm_id", ""),
        "lat": record.get("lat", ""),
        "lon": record.get("lon", ""),
        "length_km": record.get("length_km", ""),
        "lanes": _tag_value(record, "lanes", tags.get("lanes", "")),
        "oneway": _tag_value(record, "oneway", tags.get("oneway", "")),
        "surface": _tag_value(record, "surface", tags.get("surface", "")),
        "is_bridge": _is_truthy_osm_value(bridge),
    }
    return {key: row.get(key, "") for key in fieldnames}


def fetch_province_roads(
    raw_output_path="data/raw/roads_raw.json",
    csv_output_path="data/processed/roads.csv",
    provinces=None,
    groups=None,
    temp_dir="data/raw/temp_roads",
    sleep_seconds=2.0,
    require_topology=None,
    raw_quality_report_path=None,
):
    """
    Fetch province-wide road ways from OpenStreetMap for the target provinces.

    This creates an analysis-friendly road-name dataset and intentionally does
    not overwrite data/raw/road_network.json, which is used for zone scoring.
    """
    provinces = _selected_provinces(provinces)
    selected_groups = _selected_road_groups(groups)
    selected_highway_types = [
        highway_type
        for highway_types in selected_groups.values()
        for highway_type in highway_types
    ]
    if require_topology is None:
        require_topology = str(os.environ.get("ROAD_REQUIRE_TOPOLOGY") or "").strip().lower() in {
            "1",
            "true",
            "yes",
        }
    os.makedirs(temp_dir, exist_ok=True)

    print("--- Fetching Province Road Dataset (OSM) ---")
    print(f"  Target provinces: {len(provinces)}")
    print(f"  Provinces: {', '.join(provinces)}")
    print(f"  Highway types: {', '.join(selected_highway_types)}")
    print(f"  Road groups: {', '.join(selected_groups)}")
    print(f"  Overpass endpoints: {', '.join(_overpass_urls())}")

    for province in provinces:
        province = normalize_province_name(province)
        for group_name, highway_types in selected_groups.items():
            temp_path = _temp_cache_path(temp_dir, province, group_name)
            if os.path.exists(temp_path):
                cached_records = _load_json_list(temp_path)
                if not require_topology or _cache_has_raw_contract(cached_records):
                    print(f"  [Skip] {province} / {group_name} already cached")
                    continue
                print(f"  [Refresh] {province} / {group_name} cache missing raw contract")

            print(f"  [Fetch] {province} / {group_name}...", end=" ", flush=True)
            try:
                if group_name == "local" and len(highway_types) > 1:
                    records = _fetch_split_group_with_cache(
                        province,
                        group_name,
                        highway_types,
                        temp_dir,
                        require_topology=require_topology,
                    )
                else:
                    records = _fetch_province_group(
                        province,
                        group_name,
                        highway_types,
                        temp_dir=temp_dir,
                        require_topology=require_topology,
                    )
                _save_json(temp_path, records)
                print(f"Done ({len(records)} roads)")
            except Exception as exc:
                print(f"Failed: {exc}")
                raise

            time.sleep(sleep_seconds)

    all_records = []
    for province in provinces:
        for group_name in selected_groups:
            temp_path = _temp_cache_path(temp_dir, province, group_name)
            for record in _load_json_list(temp_path):
                all_records.append(record)
    all_records = _dedupe_road_records(all_records)

    all_records.sort(
        key=lambda r: (
            str(r.get("province") or ""),
            str(r.get("highway_type") or ""),
            str(r.get("road_name") or ""),
            int(r.get("osm_id") or 0),
        )
    )

    _save_json(raw_output_path, all_records)
    _write_roads_csv(all_records, csv_output_path)
    if raw_quality_report_path:
        expected_highway_types = [
            highway_type
            for highway_types in selected_groups.values()
            for highway_type in highway_types
        ]
        report = _build_roads_raw_quality_report(
            all_records,
            expected_highway_types=expected_highway_types,
            target_provinces=provinces,
        )
        _save_json(raw_quality_report_path, report)

    named_count = sum(1 for r in all_records if r.get("is_named"))
    print(f"\n[Success] Road raw JSON saved to {raw_output_path}")
    print(f"[Success] Road CSV saved to {csv_output_path}")
    if raw_quality_report_path:
        print(f"[Success] Road raw quality report saved to {raw_quality_report_path}")
    print(f"[Summary] {len(all_records)} roads, {named_count} named, {len(all_records) - named_count} unnamed")
    return all_records


def fetch_road_network(landmarks_path, output_path, radius_km=2.0):
    """
    Fetch road connectivity metrics around Layer 1 landmark anchors.

    This legacy output feeds zone scoring and is separate from the province-wide
    road-name dataset produced by fetch_province_roads().
    """
    if not os.path.exists(landmarks_path):
        print(f"[Error] {landmarks_path} not found.")
        return

    with open(landmarks_path, "r", encoding="utf-8") as f:
        all_landmarks = json.load(f)

    layer1 = [l for l in all_landmarks if l.get("layer") == 1]
    print("--- Fetching Road Connectivity Data (OSM) ---")

    if os.path.exists(output_path):
        try:
            road_data = _load_json_list(output_path)
            done_anchors = {item["zone_anchor"] for item in road_data}
            print(f"  Resuming from existing file. {len(done_anchors)} zones already processed.")
        except Exception:
            road_data = []
            done_anchors = set()
    else:
        road_data = []
        done_anchors = set()

    for item in layer1:
        name = str(item.get("name", "Unknown")).replace("\u200b", "").strip()
        if name in done_anchors:
            continue

        lat, lon = item["lat"], item["lon"]
        print(f"  Analyzing roads for: {name}...", end=" ", flush=True)

        query = f"""
        [out:json][timeout:30];
        (
          way["highway"](around:{radius_km * 1000},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            data = _request_overpass(query, retries=3, timeout=45)
            elements = data.get("elements", [])
            highways = [e for e in elements if e.get("type") == "way"]
            primary_roads = [
                h
                for h in highways
                if h.get("tags", {}).get("highway") in ["primary", "secondary", "trunk"]
            ]
            node_count = len([e for e in elements if e.get("type") == "node"])

            road_data.append(
                {
                    "zone_anchor": name,
                    "lat": lat,
                    "lon": lon,
                    "total_road_segments": len(highways),
                    "primary_road_count": len(primary_roads),
                    "road_node_density": node_count,
                    "road_complexity_score": round((len(highways) * 2) + (len(primary_roads) * 5), 2),
                }
            )
            print(f"Done! ({len(highways)} segments)")

            if len(road_data) % 10 == 0:
                _save_json(output_path, road_data)

            time.sleep(1.2)
        except Exception as exc:
            print(f"Error: {exc}")

    _save_json(output_path, road_data)
    print(f"\n[Success] Road network data saved to {output_path}")


if __name__ == "__main__":
    fetch_road_network("data/raw/landmarks_raw.json", "data/raw/road_network.json")
