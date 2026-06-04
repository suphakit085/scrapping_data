import concurrent.futures
import json
import os
import shutil
import threading
import time

import requests
from playwright.sync_api import sync_playwright

from scrapers.google_maps_sync import scrape_google_maps_pois
from utils.data_diff import find_new_and_merge, haversine_distance_m, name_is_similar
from utils.geo_boundaries import (
    build_spatial_index,
    ce_to_be,
    load_admin3_centroids,
    load_target_boundaries,
    normalize_province_name,
    point_in_province,
    prompt_admin_areas,
    prompt_parallel_workers,
    province_slug_to_adm1,
    reverse_geocode,
    parse_osm_timestamp_year,
)


overpass_lock = threading.Lock()


PROVINCE_DATA = [
    {"name": "\u0e02\u0e2d\u0e19\u0e41\u0e01\u0e48\u0e19", "slug": "khon-kaen", "relation_id": 18934428},
    {"name": "\u0e2d\u0e38\u0e1a\u0e25\u0e23\u0e32\u0e0a\u0e18\u0e32\u0e19\u0e35", "slug": "ubon-ratchathani", "relation_id": 18931767},
    {"name": "\u0e1b\u0e23\u0e30\u0e08\u0e27\u0e1a\u0e04\u0e35\u0e23\u0e35\u0e02\u0e31\u0e19\u0e18\u0e4c", "slug": "prachuap-khiri-khan", "relation_id": 18936307},
    {"name": "\u0e2d\u0e38\u0e14\u0e23\u0e18\u0e32\u0e19\u0e35", "slug": "udon-thani", "relation_id": 18929325},
    {"name": "\u0e23\u0e30\u0e22\u0e2d\u0e07", "slug": "rayong", "relation_id": 18955763},
    {"name": "\u0e0a\u0e25\u0e1a\u0e38\u0e23\u0e35", "slug": "chonburi", "relation_id": 18997107},
    {"name": "\u0e2a\u0e38\u0e23\u0e34\u0e19\u0e17\u0e23\u0e4c", "slug": "surin", "relation_id": 18975352},
    {"name": "\u0e1a\u0e38\u0e23\u0e35\u0e23\u0e31\u0e21\u0e22\u0e4c", "slug": "buriram", "relation_id": 17817575},
    {"name": "\u0e1e\u0e34\u0e29\u0e13\u0e38\u0e42\u0e25\u0e01", "slug": "phitsanulok", "relation_id": 18994043},
    {"name": "\u0e40\u0e0a\u0e35\u0e22\u0e07\u0e23\u0e32\u0e22", "slug": "chiang-rai", "relation_id": 19051912},
]


LAYER_NAME = "\u0e2a\u0e34\u0e48\u0e07\u0e2d\u0e33\u0e19\u0e27\u0e22\u0e04\u0e27\u0e32\u0e21\u0e2a\u0e30\u0e14\u0e27\u0e01"

CATEGORY_LAUNDRY = "\u0e23\u0e49\u0e32\u0e19\u0e0b\u0e31\u0e01\u0e1c\u0e49\u0e32"
CATEGORY_BARBER = "\u0e23\u0e49\u0e32\u0e19\u0e15\u0e31\u0e14\u0e1c\u0e21"
CATEGORY_AUTO_REPAIR = "\u0e23\u0e49\u0e32\u0e19\u0e0b\u0e48\u0e2d\u0e21\u0e23\u0e16"
CATEGORY_FITNESS = "\u0e1f\u0e34\u0e15\u0e40\u0e19\u0e2a"


GOOGLE_TARGETS = [
    {"query": CATEGORY_LAUNDRY, "category": CATEGORY_LAUNDRY},
    {"query": "\u0e40\u0e04\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e0b\u0e31\u0e01\u0e1c\u0e49\u0e32\u0e2b\u0e22\u0e2d\u0e14\u0e40\u0e2b\u0e23\u0e35\u0e22\u0e0d", "category": CATEGORY_LAUNDRY},
    {"query": "laundromat", "category": CATEGORY_LAUNDRY},
    {"query": CATEGORY_BARBER, "category": CATEGORY_BARBER},
    {"query": "barber shop", "category": CATEGORY_BARBER},
    {"query": CATEGORY_AUTO_REPAIR, "category": CATEGORY_AUTO_REPAIR},
    {"query": "\u0e2d\u0e39\u0e48\u0e0b\u0e48\u0e2d\u0e21\u0e23\u0e16", "category": CATEGORY_AUTO_REPAIR},
    {"query": "\u0e23\u0e49\u0e32\u0e19\u0e0b\u0e48\u0e2d\u0e21\u0e21\u0e2d\u0e40\u0e15\u0e2d\u0e23\u0e4c\u0e44\u0e0b\u0e04\u0e4c", "category": CATEGORY_AUTO_REPAIR},
    {"query": "\u0e23\u0e49\u0e32\u0e19\u0e1b\u0e30\u0e22\u0e32\u0e07", "category": CATEGORY_AUTO_REPAIR},
    {"query": "\u0e23\u0e49\u0e32\u0e19\u0e40\u0e1b\u0e25\u0e35\u0e48\u0e22\u0e19\u0e22\u0e32\u0e07", "category": CATEGORY_AUTO_REPAIR},
    {"query": CATEGORY_FITNESS, "category": CATEGORY_FITNESS},
    {"query": "\u0e22\u0e34\u0e21", "category": CATEGORY_FITNESS},
    {"query": "fitness", "category": CATEGORY_FITNESS},
    {"query": "gym", "category": CATEGORY_FITNESS},
]


AMENITY_DEDUP_RADIUS_M = {
    CATEGORY_LAUNDRY: 70,
    CATEGORY_BARBER: 70,
    CATEGORY_AUTO_REPAIR: 90,
    CATEGORY_FITNESS: 90,
}


ALLOWED_CATEGORIES = set(AMENITY_DEDUP_RADIUS_M)


CLOSED_NAME_KEYWORDS = [
    "\u0e1b\u0e34\u0e14\u0e16\u0e32\u0e27\u0e23",
    "\u0e1b\u0e34\u0e14\u0e01\u0e34\u0e08\u0e01\u0e32\u0e23",
    "\u0e1b\u0e34\u0e14\u0e41\u0e25\u0e49\u0e27",
    "\u0e22\u0e49\u0e32\u0e22",
    "closed",
    "permanently closed",
]


def run_overpass_query(query: str) -> list:
    with overpass_lock:
        time.sleep(2)
        mirrors = [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ]
        for mirror in mirrors:
            try:
                response = requests.post(
                    mirror,
                    data={"data": query},
                    headers={"User-Agent": "BI-Pipeline-Amenities/1.0"},
                    timeout=60,
                )
                if response.status_code == 200 and response.text.strip():
                    return response.json().get("elements", [])
            except Exception as e:
                print(f"    Mirror {mirror} failed: {e}")
        print("    All Overpass mirrors failed.")
        return []


def get_coords(element: dict) -> tuple:
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    if "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    return None, None


def build_amenities_query(area_id: int) -> str:
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      nwr["shop"~"^(laundry|dry_cleaning|hairdresser|car_repair|motorcycle_repair|tyres|car_parts)$"](area.searchArea);
      nwr["craft"~"^(car_repair|mechanic)$"](area.searchArea);
      nwr["leisure"~"^(fitness_centre|fitness_station)$"](area.searchArea);
      nwr["sport"="fitness"](area.searchArea);
      nwr["amenity"="gym"](area.searchArea);
    );
    out center meta;
    """


def classify_amenity(tags: dict) -> str:
    shop = tags.get("shop", "")
    amenity = tags.get("amenity", "")
    leisure = tags.get("leisure", "")
    sport = tags.get("sport", "")

    if shop in ("laundry", "dry_cleaning") or amenity == "laundry":
        return CATEGORY_LAUNDRY
    if shop == "hairdresser":
        return CATEGORY_BARBER
    if shop in ("car_repair", "motorcycle_repair", "tyres", "car_parts"):
        return CATEGORY_AUTO_REPAIR
    if tags.get("craft") in ("car_repair", "mechanic"):
        return CATEGORY_AUTO_REPAIR
    if leisure in ("fitness_centre", "fitness_station") or sport == "fitness" or amenity == "gym":
        return CATEGORY_FITNESS

    return LAYER_NAME


def nearest_admin3(lat, lon, province_en: str, admin3_by_province: dict) -> tuple:
    if lat is None or lon is None or not admin3_by_province:
        return "", ""

    candidates = admin3_by_province.get(normalize_province_name(province_en), [])
    if not candidates:
        return "", ""

    best = min(
        candidates,
        key=lambda r: haversine_distance_m(lat, lon, r.get("lat"), r.get("lon")),
    )
    return (
        best.get("district_th") or best.get("district") or "",
        best.get("admin3_th") or best.get("admin3") or "",
    )


def resolve_admin_area(
    lat,
    lon,
    province_en: str,
    spatial_tree,
    spatial_polygons,
    spatial_properties,
    admin3_by_province: dict = None,
) -> tuple:
    district, sub_district = reverse_geocode(
        lat, lon, spatial_tree, spatial_polygons, spatial_properties
    )
    if district or sub_district:
        return district, sub_district

    return nearest_admin3(lat, lon, province_en, admin3_by_province or {})


def is_closed_or_inactive(tags: dict, name: str) -> bool:
    inactive_keys = [
        "disused:shop",
        "disused:amenity",
        "abandoned",
        "abandoned:shop",
        "abandoned:amenity",
    ]
    if any(tags.get(k) for k in inactive_keys):
        return True
    if tags.get("shop") in ("vacant", "no"):
        return True
    lowered = (name or "").lower()
    return any(keyword in lowered for keyword in CLOSED_NAME_KEYWORDS)


def make_poi_record(
    *,
    province: dict,
    name: str,
    name_en: str = "",
    category: str,
    lat,
    lon,
    source: str,
    district: str = "",
    sub_district: str = "",
    osm_type=None,
    osm_id=None,
    osm_timestamp: str = "",
    osm_version=None,
) -> dict:
    last_edit_year_ce = parse_osm_timestamp_year(osm_timestamp) if osm_timestamp else None
    created_year_ce = last_edit_year_ce if osm_version == 1 else None

    return {
        "province": province["name"],
        "province_en": province_slug_to_adm1(province["slug"]),
        "district": district,
        "sub_district": sub_district,
        "name": name,
        "name_en": name_en,
        "category": category,
        "layer": 3,
        "layer_name": LAYER_NAME,
        "lat": lat,
        "lon": lon,
        "osm_type": osm_type,
        "osm_id": osm_id,
        "osm_timestamp": osm_timestamp,
        "osm_last_edit_year_ce": last_edit_year_ce,
        "osm_last_edit_year_be": ce_to_be(last_edit_year_ce) if last_edit_year_ce else None,
        "osm_created_year_ce": created_year_ce,
        "osm_created_year_be": ce_to_be(created_year_ce) if created_year_ce else None,
        "osm_version": osm_version,
        "source": source,
    }


def scrape_osm_amenities(
    province: dict,
    spatial_tree,
    spatial_polygons,
    spatial_properties,
    admin3_by_province: dict = None,
) -> list:
    thai_name = province["name"]
    area_id = province["relation_id"] + 3600000000

    print("  -> Pulling amenities from OSM...", end=" ", flush=True)
    elements = run_overpass_query(build_amenities_query(area_id))

    pois = []
    for element in elements:
        tags = element.get("tags", {})
        lat, lon = get_coords(element)
        if lat is None or lon is None:
            continue

        name = (
            tags.get("name")
            or tags.get("name:th")
            or tags.get("name:en")
            or tags.get("brand")
            or tags.get("operator")
            or ""
        )
        name = str(name).strip()
        if not name or is_closed_or_inactive(tags, name):
            continue

        district, sub_district = resolve_admin_area(
            lat,
            lon,
            province_slug_to_adm1(province["slug"]),
            spatial_tree,
            spatial_polygons,
            spatial_properties,
            admin3_by_province,
        )
        category = classify_amenity(tags)
        if category not in ALLOWED_CATEGORIES:
            continue

        pois.append(
            make_poi_record(
                province=province,
                name=name,
                name_en=tags.get("name:en", ""),
                category=category,
                lat=lat,
                lon=lon,
                source="OpenStreetMap / Overpass API",
                district=district,
                sub_district=sub_district,
                osm_type=element.get("type"),
                osm_id=element.get("id"),
                osm_timestamp=element.get("timestamp", ""),
                osm_version=element.get("version", None),
            )
        )

    print(f"{len(pois)} found.")
    return pois


def is_duplicate_amenity(candidate: dict, existing_pois: list) -> bool:
    candidate_lat = candidate.get("lat")
    candidate_lon = candidate.get("lon")
    candidate_name = candidate.get("name", "")
    candidate_category = candidate.get("category", "")
    radius_m = AMENITY_DEDUP_RADIUS_M.get(candidate_category, 70)

    for existing in existing_pois:
        if existing.get("province") != candidate.get("province"):
            continue
        if existing.get("category") != candidate_category:
            continue

        distance_m = haversine_distance_m(
            candidate_lat,
            candidate_lon,
            existing.get("lat"),
            existing.get("lon"),
        )
        if distance_m <= radius_m and name_is_similar(candidate_name, existing.get("name", "")):
            return True

    return False


def scrape_gmaps_amenities(
    province: dict,
    existing_pois: list,
    province_boundaries: dict,
    spatial_tree,
    spatial_polygons,
    spatial_properties,
    admin3_by_province: dict = None,
) -> list:
    thai_name = province["name"]
    province_en = province_slug_to_adm1(province["slug"])
    new_pois = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--lang=th-TH,th"])
        context = browser.new_context(
            locale="th-TH",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            for target in GOOGLE_TARGETS:
                query = target["query"]
                category = target["category"]
                print(f"  [{thai_name}] Google Maps '{query}'...", end=" ", flush=True)

                results = scrape_google_maps_pois(thai_name, query, page, max_results=20)
                added = 0
                outside_skipped = 0

                for result in results:
                    lat = result.get("lat")
                    lon = result.get("lon")
                    name = str(result.get("name", "")).strip()
                    if not name or lat is None or lon is None:
                        continue

                    if not point_in_province(lat, lon, province_en, province_boundaries):
                        outside_skipped += 1
                        continue

                    district, sub_district = resolve_admin_area(
                        lat,
                        lon,
                        province_en,
                        spatial_tree,
                        spatial_polygons,
                        spatial_properties,
                        admin3_by_province,
                    )
                    candidate = make_poi_record(
                        province=province,
                        name=name,
                        category=category,
                        lat=lat,
                        lon=lon,
                        source="Google Maps",
                        district=district,
                        sub_district=sub_district,
                        osm_type="google_maps",
                    )

                    if is_duplicate_amenity(candidate, existing_pois + new_pois):
                        continue

                    new_pois.append(candidate)
                    added += 1

                outside_msg = f", {outside_skipped} outside province skipped" if outside_skipped else ""
                print(f"{len(results)} found, {added} new added{outside_msg}.")
                time.sleep(1.2)
        finally:
            context.close()
            browser.close()

    return new_pois


def scrape_province_task(
    province: dict,
    province_boundaries: dict,
    temp_dir: str,
    spatial_tree,
    spatial_polygons,
    spatial_properties,
    admin3_by_province: dict = None,
) -> str | None:
    thai_name = province["name"]
    slug = province["slug"]
    temp_file_path = os.path.join(temp_dir, f"amenities_{slug}.json")

    if os.path.exists(temp_file_path):
        print(f"\n[SKIP] Found existing amenities temp file for {thai_name} (resume)")
        return temp_file_path

    print(f"\nStarting amenities scrape: {thai_name}")
    try:
        osm_pois = scrape_osm_amenities(
            province,
            spatial_tree,
            spatial_polygons,
            spatial_properties,
            admin3_by_province,
        )
        gmaps_pois = scrape_gmaps_amenities(
            province,
            osm_pois,
            province_boundaries,
            spatial_tree,
            spatial_polygons,
            spatial_properties,
            admin3_by_province,
        )

        province_total = osm_pois + gmaps_pois
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(province_total, f, ensure_ascii=False, indent=2)

        print(f"  => Done {thai_name}: {len(province_total)} amenities")
        return temp_file_path
    except Exception as e:
        print(f"Failed amenities scrape for {thai_name}: {e}")
        return None


def scrape_amenities(
    output_path: str,
    parallel_workers: int = None,
    extract_admin_areas: bool = None,
    selected_provinces: list = None,
):
    if parallel_workers is None:
        parallel_workers = prompt_parallel_workers("Amenities", default_workers=3)

    print("=" * 60)
    print(f"Starting Amenities Scraper (Parallel Workers: {parallel_workers})")
    print("=" * 60)

    if extract_admin_areas is None:
        extract_admin_areas = prompt_admin_areas("Amenities Scraper")

    target_provinces = PROVINCE_DATA
    if selected_provinces:
        target_provinces = [
            p for p in PROVINCE_DATA
            if p["slug"] in selected_provinces or p["name"] in selected_provinces
        ]

    province_boundaries = load_target_boundaries()

    if extract_admin_areas:
        spatial_tree, spatial_polygons, spatial_properties = build_spatial_index()
        admin3_by_province = load_admin3_centroids()
        if not spatial_tree and admin3_by_province:
            print("  -> Falling back to nearest admin3 centroid for district/sub-district.")
    else:
        print("  -> Skipping district and sub-district extraction.")
        spatial_tree, spatial_polygons, spatial_properties = None, [], []
        admin3_by_province = {}

    temp_dir = os.path.join(os.path.dirname(output_path), "temp_amenities")
    os.makedirs(temp_dir, exist_ok=True)

    temp_files = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        futures = [
            executor.submit(
                scrape_province_task,
                province,
                province_boundaries,
                temp_dir,
                spatial_tree,
                spatial_polygons,
                spatial_properties,
                admin3_by_province,
            )
            for province in target_provinces
        ]

        for future in concurrent.futures.as_completed(futures):
            temp_file = future.result()
            if temp_file:
                temp_files.append(temp_file)

    print(f"\nMerging amenities from {len(temp_files)} province temp files...")
    new_amenities = []
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            with open(temp_file, "r", encoding="utf-8") as f:
                new_amenities.extend(
                    poi for poi in json.load(f)
                    if poi.get("category") in ALLOWED_CATEGORIES
                )

    existing_amenities = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_amenities = [
                    poi for poi in json.load(f)
                    if poi.get("category") in ALLOWED_CATEGORIES
                ]
            print(f"  Loaded {len(existing_amenities)} existing amenities from {os.path.basename(output_path)}")
        except Exception:
            existing_amenities = []

    merged_amenities, new_found = find_new_and_merge(
        existing_amenities,
        new_amenities,
        category_radius_mapping=AMENITY_DEDUP_RADIUS_M,
    )

    print("\n============================================================")
    print("[Data Diff Report - Amenities Scraper]")
    print("============================================================")
    print(f"Existing amenities: {len(existing_amenities)}")
    print(f"Scraped amenities this run: {len(new_amenities)}")
    print(f"New amenities added: {len(new_found)}")
    if new_found:
        print("\nExamples:")
        for idx, poi in enumerate(new_found[:10], 1):
            print(f"  [{idx}] ({poi.get('province')}) {poi.get('name')} - {poi.get('category')}")
    print("============================================================")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged_amenities, f, ensure_ascii=False, indent=2)

    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    print(f"\nDone! Total amenities: {len(merged_amenities)}")
    print(f"Saved to: {output_path}")
    return merged_amenities


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    correct_path = os.path.abspath(os.path.join(script_dir, "../data/raw/amenities_raw.json"))
    scrape_amenities(correct_path, parallel_workers=3)
