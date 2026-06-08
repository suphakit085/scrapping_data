import csv
import json
import math
import os
import time
import uuid
from collections import Counter

import requests


GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

GOOGLE_ROAD_FIELDNAMES = [
    "google_road_name",
    "google_formatted_address",
    "google_place_id",
    "google_api_status",
    "google_error_message",
    "google_match_status",
    "road_display_name",
]

USELESS_ROUTE_NAMES = {
    "",
    "unnamed road",
    "\u0e16\u0e19\u0e19\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d",
    "\u0e16\u0e19\u0e19\u0e17\u0e35\u0e48\u0e44\u0e21\u0e48\u0e21\u0e35\u0e0a\u0e37\u0e48\u0e2d",
}


def _ensure_parent_dir(path):
    parent = os.path.dirname(os.path.abspath(os.path.normpath(path)))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _read_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path, fieldnames, rows):
    _ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _load_json_dict(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _is_useless_route_name(value):
    return str(value or "").strip().lower() in USELESS_ROUTE_NAMES


def normalize_google_route_result(result):
    normalized = dict(result or {})
    if (
        str(normalized.get("google_match_status") or "").strip() == "matched"
        and _is_useless_route_name(normalized.get("google_road_name"))
    ):
        normalized.update(
            {
                "google_road_name": "",
                "google_match_status": "no_route",
                "road_display_name": "",
            }
        )
    return normalized


def normalize_google_route_cache(cache):
    normalized_count = 0
    for key, value in list(cache.items()):
        if not isinstance(value, dict):
            continue
        normalized = normalize_google_route_result(value)
        if normalized != value:
            cache[key] = normalized
            normalized_count += 1
    return normalized_count


def _save_json(path, data):
    path = os.path.abspath(os.path.normpath(path))
    _ensure_parent_dir(path)
    temp_path = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    last_error = None
    for attempt in range(10):
        try:
            os.replace(temp_path, path)
            return True
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.2 * (attempt + 1))

    fallback_path = f"{path}.pending-{uuid.uuid4().hex}.json"
    try:
        os.replace(temp_path, fallback_path)
    except PermissionError:
        fallback_path = temp_path

    print(
        "[Warning] Could not replace cache file because Windows denied access. "
        f"Latest cache snapshot left at {fallback_path}. Error: {last_error}"
    )
    return False


def _load_raw_roads_by_osm_id(path):
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return {}
    return {str(row.get("osm_id")): row for row in data if row.get("osm_id") is not None}


def _to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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


def geometry_midpoint(geometry):
    points = [
        (_to_float(point.get("lat")), _to_float(point.get("lon")))
        for point in geometry or []
        if _to_float(point.get("lat")) is not None and _to_float(point.get("lon")) is not None
    ]
    if not points:
        return None, None
    if len(points) == 1:
        return points[0]

    segment_lengths = []
    total = 0.0
    previous = points[0]
    for point in points[1:]:
        length = _haversine_km(previous[0], previous[1], point[0], point[1])
        segment_lengths.append((previous, point, length))
        total += length
        previous = point

    if total <= 0:
        return points[len(points) // 2]

    target = total / 2
    covered = 0.0
    for start, end, length in segment_lengths:
        if covered + length >= target:
            ratio = (target - covered) / length if length else 0
            return (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
        covered += length

    return points[-1]


def lookup_point_for_row(row, raw_record=None, long_segment_threshold_km=0.2):
    length_km = _to_float(row.get("length_km"), 0.0) or 0.0
    if raw_record and length_km >= long_segment_threshold_km:
        lat, lon = geometry_midpoint(raw_record.get("geometry"))
        if lat is not None and lon is not None:
            return round(lat, 7), round(lon, 7)

    lat = _to_float(row.get("lat"))
    lon = _to_float(row.get("lon"))
    if lat is None or lon is None:
        return None, None
    return round(lat, 7), round(lon, 7)


def is_unnamed_road(row):
    return str(row.get("road_name") or "").strip().startswith("unnamed:")


def base_road_display_name(row, google_road_name=""):
    road_name = str(row.get("road_name") or "").strip()
    road_ref = str(row.get("road_ref") or "").strip()
    osm_id = str(row.get("osm_id") or "").strip()

    if road_name and not road_name.startswith("unnamed:"):
        return road_name
    if google_road_name:
        return google_road_name
    if road_ref:
        return f"Road {road_ref}"
    return road_name or f"unnamed:{osm_id}"


def should_lookup_row(row, include_with_ref=False):
    if not is_unnamed_road(row):
        return False, "skipped_named"
    if str(row.get("road_ref") or "").strip() and not include_with_ref:
        return False, "skipped_has_ref"
    return True, ""


def parse_google_route_result(payload):
    status = str(payload.get("status") or "").strip()
    error_message = str(payload.get("error_message") or "").strip()
    if status == "ZERO_RESULTS":
        return {
            "google_road_name": "",
            "google_formatted_address": "",
            "google_place_id": "",
            "google_api_status": status,
            "google_error_message": "",
            "google_match_status": "no_route",
        }
    if status != "OK":
        return {
            "google_road_name": "",
            "google_formatted_address": "",
            "google_place_id": "",
            "google_api_status": status or "UNKNOWN",
            "google_error_message": error_message,
            "google_match_status": "api_error",
        }

    for result in payload.get("results") or []:
        for component in result.get("address_components") or []:
            if "route" not in (component.get("types") or []):
                continue
            route_name = str(component.get("long_name") or component.get("short_name") or "").strip()
            if _is_useless_route_name(route_name):
                continue
            return normalize_google_route_result(
                {
                    "google_road_name": route_name,
                    "google_formatted_address": result.get("formatted_address", ""),
                    "google_place_id": result.get("place_id", ""),
                    "google_api_status": status,
                    "google_error_message": "",
                    "google_match_status": "matched",
                }
            )

    return {
        "google_road_name": "",
        "google_formatted_address": "",
        "google_place_id": "",
        "google_api_status": status,
        "google_error_message": "",
        "google_match_status": "no_route",
    }


def reverse_geocode_route(
    lat,
    lon,
    api_key,
    session=None,
    language="th",
    timeout=15,
    retries=2,
    retry_sleep_seconds=1.0,
):
    session = session or requests.Session()
    for attempt in range(retries + 1):
        try:
            response = session.get(
                GOOGLE_GEOCODE_URL,
                params={
                    "latlng": f"{lat},{lon}",
                    "key": api_key,
                    "language": language,
                    "region": "th",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            return parse_google_route_result(response.json())
        except Exception as exc:
            if attempt >= retries:
                return {
                    "google_road_name": "",
                    "google_formatted_address": "",
                    "google_place_id": "",
                    "google_api_status": "REQUEST_EXCEPTION",
                    "google_error_message": str(exc),
                    "google_match_status": "api_error",
                }
            if retry_sleep_seconds:
                time.sleep(retry_sleep_seconds)


def enrich_road_row(
    row,
    raw_record,
    cache,
    api_key=None,
    session=None,
    include_with_ref=False,
    dry_run=False,
    language="th",
    request_timeout=15,
    long_segment_threshold_km=0.2,
):
    enriched = dict(row)
    should_lookup, skip_status = should_lookup_row(row, include_with_ref=include_with_ref)
    if not should_lookup:
        enriched.update(
            {
                "google_road_name": "",
                "google_formatted_address": "",
                "google_place_id": "",
                "google_api_status": "",
                "google_error_message": "",
                "google_match_status": skip_status,
                "road_display_name": base_road_display_name(row),
            }
        )
        return enriched, False

    osm_id = str(row.get("osm_id") or "").strip()
    if osm_id in cache and cache[osm_id].get("google_match_status") != "api_error":
        cached = normalize_google_route_result(cache[osm_id])
        google_road_name = cached.get("google_road_name", "")
        enriched.update(
            {
                "google_road_name": google_road_name,
                "google_formatted_address": cached.get("google_formatted_address", ""),
                "google_place_id": cached.get("google_place_id", ""),
                "google_api_status": cached.get("google_api_status", ""),
                "google_error_message": cached.get("google_error_message", ""),
                "google_match_status": cached.get("google_match_status", ""),
                "road_display_name": base_road_display_name(row, google_road_name),
            }
        )
        return enriched, False

    lat, lon = lookup_point_for_row(
        row,
        raw_record=raw_record,
        long_segment_threshold_km=long_segment_threshold_km,
    )
    if lat is None or lon is None:
        result = {
            "google_road_name": "",
            "google_formatted_address": "",
            "google_place_id": "",
            "google_api_status": "",
            "google_error_message": "Missing or invalid lookup point",
            "google_match_status": "api_error",
        }
    elif dry_run:
        result = {
            "google_road_name": "",
            "google_formatted_address": "",
            "google_place_id": "",
            "google_api_status": "DRY_RUN",
            "google_error_message": "",
            "google_match_status": "dry_run",
        }
    else:
        result = reverse_geocode_route(
            lat,
            lon,
            api_key,
            session=session,
            language=language,
            timeout=request_timeout,
            retry_sleep_seconds=0 if dry_run else 1.0,
        )

    result = normalize_google_route_result(result)
    google_road_name = result.get("google_road_name", "")
    enriched.update(
        {
            "google_road_name": google_road_name,
            "google_formatted_address": result.get("google_formatted_address", ""),
            "google_place_id": result.get("google_place_id", ""),
            "google_api_status": result.get("google_api_status", ""),
            "google_error_message": result.get("google_error_message", ""),
            "google_match_status": result.get("google_match_status", ""),
            "road_display_name": base_road_display_name(row, google_road_name),
        }
    )

    if not dry_run and enriched.get("google_match_status") != "api_error":
        cache[osm_id] = {
            **{field: enriched.get(field, "") for field in GOOGLE_ROAD_FIELDNAMES},
            "lookup_lat": lat,
            "lookup_lon": lon,
        }
        return enriched, True

    return enriched, False


def build_google_road_enrichment_outputs(
    roads_path,
    output_path,
    raw_roads_path=None,
    cache_path=None,
    api_key=None,
    include_with_ref=False,
    dry_run=False,
    limit=None,
    sleep_seconds=0.1,
    language="th",
    request_timeout=15,
    long_segment_threshold_km=0.2,
    cache_flush_interval=25,
):
    input_fieldnames, rows = _read_csv(roads_path)
    if not rows:
        raise ValueError(f"No road rows found: {roads_path}")
    if not dry_run and not api_key:
        raise ValueError("GOOGLE_MAPS_API_KEY is required unless dry_run=True")

    output_fieldnames = list(input_fieldnames)
    for field in GOOGLE_ROAD_FIELDNAMES:
        if field not in output_fieldnames:
            output_fieldnames.append(field)

    raw_by_osm_id = _load_raw_roads_by_osm_id(raw_roads_path)
    cache = _load_json_dict(cache_path)
    cache_normalizations = normalize_google_route_cache(cache)
    session = requests.Session()
    enriched_rows = []
    summary = Counter()
    lookup_count = 0
    cache_hits = 0
    cache_updates = 0

    for row in rows:
        should_lookup, skip_status = should_lookup_row(row, include_with_ref=include_with_ref)
        osm_id = str(row.get("osm_id") or "").strip()
        cache_hit = (
            should_lookup
            and osm_id in cache
            and cache[osm_id].get("google_match_status") != "api_error"
        )
        if cache_hit:
            cache_hits += 1

        if should_lookup and not cache_hit and limit is not None and lookup_count >= limit:
            enriched = dict(row)
            enriched.update(
                {
                    "google_road_name": "",
                    "google_formatted_address": "",
                    "google_place_id": "",
                    "google_api_status": "",
                    "google_error_message": "",
                    "google_match_status": "skipped_limit",
                    "road_display_name": base_road_display_name(row),
                }
            )
            enriched_rows.append(enriched)
            summary["skipped_limit"] += 1
            continue

        if should_lookup and not cache_hit:
            lookup_count += 1

        enriched, cache_updated = enrich_road_row(
            row,
            raw_by_osm_id.get(str(row.get("osm_id") or "")),
            cache,
            api_key=api_key,
            session=session,
            include_with_ref=include_with_ref,
            dry_run=dry_run,
            language=language,
            request_timeout=request_timeout,
            long_segment_threshold_km=long_segment_threshold_km,
        )
        status = enriched.get("google_match_status") or skip_status or "unknown"
        summary[status] += 1
        cache_updates += int(cache_updated)
        enriched_rows.append(enriched)

        if cache_path and cache_updates and cache_flush_interval:
            if cache_updates % cache_flush_interval == 0:
                _save_json(cache_path, cache)

        if cache_updated and sleep_seconds:
            time.sleep(sleep_seconds)

    _write_csv(output_path, output_fieldnames, enriched_rows)
    if cache_path and (cache_updates or cache_normalizations):
        _save_json(cache_path, cache)

    return {
        "rows": len(enriched_rows),
        "lookups_selected": lookup_count,
        "cache_hits": cache_hits,
        "cache_updates": cache_updates,
        "cache_normalizations": cache_normalizations,
        "status_counts": dict(sorted(summary.items())),
        "output_path": output_path,
        "cache_path": cache_path or "",
    }
