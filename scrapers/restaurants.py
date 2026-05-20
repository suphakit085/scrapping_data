import os
import json
import time
import re
import requests
import math
import concurrent.futures
import glob
import shutil
from playwright.sync_api import sync_playwright

from utils.geo_boundaries import (
    load_admin3_centroids,
    load_target_boundaries,
    point_in_province,
    province_slug_to_adm1,
    build_spatial_index,
    reverse_geocode,
    prompt_admin_areas,
    parse_osm_timestamp_year,
    parse_review_relative_year,
    ce_to_be,
    prompt_gmaps_review_filter,
    prompt_osm_last_edit_filter,
    prompt_osm_created_filter,
)


# ============================================================
# Constants & Configuration
# ============================================================

PROVINCE_DATA = [
    {"name": "ขอนแก่น",        "slug": "khon-kaen",           "relation_id": 18934428},
    {"name": "อุบลราชธานี",     "slug": "ubon-ratchathani",    "relation_id": 18931767},
    {"name": "ประจวบคีรีขันธ์", "slug": "prachuap-khiri-khan", "relation_id": 18936307},
    {"name": "อุดรธานี",        "slug": "udon-thani",          "relation_id": 18929325},
    {"name": "ระยอง",           "slug": "rayong",              "relation_id": 18955763},
    {"name": "ชลบุรี",          "slug": "chonburi",            "relation_id": 18997107},
    {"name": "สุรินทร์",        "slug": "surin",               "relation_id": 18975352},
    {"name": "บุรีรัมย์",       "slug": "buriram",             "relation_id": 17817575},
    {"name": "พิษณุโลก",        "slug": "phitsanulok",         "relation_id": 18994043},
    {"name": "เชียงราย",        "slug": "chiang-rai",          "relation_id": 19051912},
]

GEOJSON_SEARCH_KEYWORDS = [
    "ร้านอาหาร", 
    "คาเฟ่", 
    "ร้านกาแฟ",
    "ร้านก๋วยเตี๋ยว", 
    "ร้านอาหารตามสั่ง",
    "ร้านส้มตำ",
    "หมูกระทะ"
]
# OSM / Overpass API Helpers
# ============================================================

def run_overpass_query(query: str) -> list:
    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    for mirror in mirrors:
        try:
            r = requests.post(mirror, data={"data": query},
                             headers={"User-Agent": "BI-Pipeline-Restaurant/1.0"},
                             timeout=60)
            if r.status_code == 200 and r.text.strip():
                return r.json().get("elements", [])
        except Exception as e:
            print(f"    Mirror {mirror} failed: {e}")
            continue
    print("    All Overpass mirrors failed.")
    return []

def get_coords(element: dict) -> tuple:
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    elif "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    return None, None

def scrape_osm_restaurants(
    province_data: dict,
    spatial_tree, spatial_polygons, spatial_properties,
    osm_last_edit_filter: bool = False, osm_last_edit_min_ce: int = None,
    osm_created_filter: bool = False, osm_created_min_ce: int = None,
) -> list:
    """ดึงร้านอาหาร, คาเฟ่, ศูนย์อาหาร จาก OpenStreetMap"""
    thai_name = province_data["name"]
    slug = province_data["slug"]
    area_id = province_data["relation_id"] + 3600000000

    query = f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      nwr["amenity"="restaurant"](area.searchArea);
      nwr["amenity"="cafe"](area.searchArea);
      nwr["amenity"="food_court"](area.searchArea);
    );
    out center meta tags;
    """
    
    print(f"  -> Pulling from OSM...", end=" ")
    elements = run_overpass_query(query)
    
    pois = []
    for el in elements:
        tags = el.get("tags", {})
        lat, lon = get_coords(el)
        if lat is None:
            continue
            
        name = tags.get("name", tags.get("name:th", tags.get("name:en", "")))
        if not name:
            continue
            
        # กรองร้านที่ปิดกิจการแล้วจาก OSM
        if tags.get("disused:amenity") or tags.get("abandoned"):
            continue
        lower_name = name.lower()
        if any(bw in lower_name for bw in ["ปิดถาวร", "ปิดกิจการ", "closed", "ปิดแล้ว", "ย้าย"]):
            continue

        # ── OSM Freshness Filters ──────────────────────────────────
        osm_ts = el.get("timestamp", "")
        osm_version = el.get("version", None)
        last_edit_year_ce = parse_osm_timestamp_year(osm_ts)
        last_edit_year_be = ce_to_be(last_edit_year_ce) if last_edit_year_ce else None
        created_year_ce = last_edit_year_ce if osm_version == 1 else None
        created_year_be = ce_to_be(created_year_ce) if created_year_ce else None

        # Feature 3: กรองตาม last_edit
        if osm_last_edit_filter and osm_last_edit_min_ce:
            if not last_edit_year_ce:
                continue
            if last_edit_year_ce < osm_last_edit_min_ce:
                continue

        # Feature 4: กรองตาม created year (proxy: version=1)
        if osm_created_filter and osm_created_min_ce:
            if osm_version != 1 or not created_year_ce:
                continue
            if created_year_ce < osm_created_min_ce:
                continue
        # ──────────────────────────────────────────────────────────

        category = "ร้านอาหาร"
        district, sub_district = reverse_geocode(lat, lon, spatial_tree, spatial_polygons, spatial_properties)

        pois.append({
            "province": thai_name,
            "province_en": slug,
            "district": district,
            "sub_district": sub_district,
            "name": name,
            "name_en": tags.get("name:en", ""),
            "category": category,
            "layer": 3,
            "layer_name": "สิ่งอำนวยความสะดวก",
            "lat": lat,
            "lon": lon,
            "osm_type": el.get("type"),
            "osm_id": el.get("id"),
            "osm_timestamp": osm_ts,
            "osm_last_edit_year_ce": last_edit_year_ce,
            "osm_last_edit_year_be": last_edit_year_be,
            "osm_created_year_ce": created_year_ce,
            "osm_created_year_be": created_year_be,
            "osm_version": osm_version,
            "source": "OpenStreetMap / Overpass API",
        })
        
    print(f"{len(pois)} restaurants found.")
    return pois


# ============================================================
# Google Maps Helpers
# ============================================================

def is_in_thailand_bounds(lat, lon):
    return (5.0 <= lat <= 20.5) and (97.0 <= lon <= 106.0)

def extract_lat_lon_from_url(url: str):
    if not url: return None, None
    match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match: return float(match.group(1)), float(match.group(2))
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match: return float(match.group(1)), float(match.group(2))
    return None, None

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in KM between two points"""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return 6371 * 2 * math.asin(math.sqrt(a))


CLOSED_LABELS = [
    "permanently closed", "temporarily closed",
    "closed permanently", "closed temporarily",
    "ปิดถาวร", "ปิดชั่วคราว",
]


def get_gmaps_latest_review_year(page) -> int | None:
    """Scrape the latest review relative-time text from the current Google Maps place page.
    Returns CE year or None.
    """
    try:
        # คลิกแท็บ Reviews
        review_btn = page.query_selector('[data-tab-index="1"], button[jsaction*="pane.rating.moreReviews"]')
        if review_btn:
            review_btn.click()
            page.wait_for_timeout(1500)

        # ดึง relative time ของ review แรก
        time_els = page.query_selector_all('span[class*="rsqaWe"], .DU9Pgb span, span[data-expandable-section] span')
        for el in time_els:
            text = el.inner_text().strip()
            if text:
                yr = parse_review_relative_year(text)
                if yr:
                    return yr
    except Exception:
        pass
    return None

def scrape_gmaps_restaurants_by_geojson_areas(
    province_data: dict,
    existing_osm_pois: list,
    page,
    admin3_by_province: dict,
    province_boundaries: dict,
    spatial_tree,
    spatial_polygons,
    spatial_properties,
    gmaps_review_filter: bool = False,
    gmaps_review_min_ce: int = None,
) -> list:
    """Search Google Maps from GeoJSON admin3 centroids and validate results by province polygon."""
    thai_name = province_data["name"]
    slug = province_data["slug"]
    province_en = province_slug_to_adm1(slug)

    search_areas = admin3_by_province.get(province_en, [])
    if not search_areas:
        search_areas = [{"admin3": province_en, "lat": None, "lon": None}]

    print(f"  -> Loaded {len(search_areas)} GeoJSON admin3 search areas.")
    new_pois = []

    for i, area in enumerate(search_areas):
        area_name = area.get("admin3") or area.get("admin3_th") or province_en
        area_lat = area.get("lat")
        area_lon = area.get("lon")
        print(f"    [{i+1}/{len(search_areas)}] {area_name}:", end=" ", flush=True)

        area_added = 0
        outside_skipped = 0

        for keyword in GEOJSON_SEARCH_KEYWORDS:
            if area_lat is not None and area_lon is not None:
                search_query = f"{keyword} near {area_lat},{area_lon}"
            else:
                search_query = f"{keyword} {province_en}"

            try:
                search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(2000)

                try:
                    page.wait_for_selector('div[role="feed"], div.Nv2PK', timeout=8000)
                    feed = page.query_selector('div[role="feed"]')
                    if feed:
                        for _ in range(6):
                            feed.evaluate("el => el.scrollTop += 2000")
                            page.wait_for_timeout(800)
                except Exception:
                    pass

                items = page.query_selector_all('div.Nv2PK, a[href*="maps/place"]')

                for item in items:
                    try:
                        card_text = item.inner_text().lower()
                        # Feature 1: กรองร้านปิดถาวร/ชั่วคราว จาก card text
                        if any(bw in card_text for bw in CLOSED_LABELS):
                            continue

                        name_el = item.query_selector('div.qBF1Pd, .fontHeadlineSmall, [aria-label]')
                        name = name_el.inner_text().strip() if name_el else (item.get_attribute("aria-label") or "").strip()
                        if not name or len(name) < 2:
                            continue

                        tag_name = item.evaluate("el => el.tagName").lower()
                        if tag_name == "a":
                            url = item.get_attribute("href")
                        else:
                            link_el = item.query_selector("a")
                            url = link_el.get_attribute("href") if link_el else ""

                        lat, lon = extract_lat_lon_from_url(url)

                        if not lat or not lon:
                            item.click()
                            page.wait_for_timeout(1000)
                            lat, lon = extract_lat_lon_from_url(page.url)
                            page.go_back()
                            page.wait_for_timeout(800)

                        if not lat or not lon:
                            continue
                        if not point_in_province(lat, lon, province_en, province_boundaries):
                            outside_skipped += 1
                            continue

                        is_duplicate = False
                        for existing in existing_osm_pois + new_pois:
                            if calculate_distance(lat, lon, existing["lat"], existing["lon"]) < 0.04:
                                is_duplicate = True
                                break

                        if is_duplicate:
                            continue

                        # Feature 2: Scrape review date ถ้าเปิด filter
                        gmaps_last_review_year_ce = None
                        if CLOSED_LABELS or gmaps_review_filter:
                            # ต้องคลิกเข้าไปหน้าร้านก่อน
                            try:
                                item.click()
                                page.wait_for_timeout(1500)
                                # ตรวจสถานะปิดอีกครั้งจาก detail page
                                page_content = page.content().lower()
                                if any(bw in page_content for bw in CLOSED_LABELS):
                                    page.go_back()
                                    page.wait_for_timeout(800)
                                    continue
                                if gmaps_review_filter:
                                    gmaps_last_review_year_ce = get_gmaps_latest_review_year(page)
                                page.go_back()
                                page.wait_for_timeout(800)
                            except Exception:
                                try: page.go_back()
                                except: pass
                        if gmaps_review_filter and gmaps_review_min_ce:
                            if not gmaps_last_review_year_ce:
                                continue
                            if gmaps_last_review_year_ce < gmaps_review_min_ce:
                                continue

                        gmaps_last_review_year_be = ce_to_be(gmaps_last_review_year_ce) if gmaps_last_review_year_ce else None

                        # Reverse Geocode
                        district, sub_district = reverse_geocode(lat, lon, spatial_tree, spatial_polygons, spatial_properties)

                        new_pois.append({
                            "province": thai_name,
                            "province_en": province_en,
                            "district": district,
                            "sub_district": sub_district,
                            "name": name,
                            "name_en": "",
                            "category": "ร้านอาหาร",
                            "layer": 3,
                            "layer_name": "สิ่งอำนวยความสะดวก",
                            "lat": lat,
                            "lon": lon,
                            "osm_type": "google_maps",
                            "osm_id": None,
                            "gmaps_last_review_year_ce": gmaps_last_review_year_ce,
                            "gmaps_last_review_year_be": gmaps_last_review_year_be,
                            "source": "Google Maps",
                        })
                        area_added += 1

                    except Exception:
                        continue

            except Exception:
                continue

        outside_msg = f", {outside_skipped} outside skipped" if outside_skipped else ""
        print(f"+{area_added} added{outside_msg}.")

    return new_pois


# ============================================================
# Main Execution
# ============================================================

def scrape_province_task(
    province: dict, admin3_by_province: dict, province_boundaries: dict,
    temp_dir: str, spatial_tree, spatial_polygons, spatial_properties,
    osm_last_edit_filter: bool = False, osm_last_edit_min_ce: int = None,
    osm_created_filter: bool = False, osm_created_min_ce: int = None,
    gmaps_review_filter: bool = False, gmaps_review_min_ce: int = None,
):
    """ฟังก์ชันย่อยสำหรับรัน 1 จังหวัด (ถูกเรียกใช้ในโหมด Parallel)"""
    thai_name = province['name']
    slug = province['slug']
    temp_file_path = os.path.join(temp_dir, f"restaurants_{slug}.json")
    
    # 🌟 Resume Logic: ข้ามถ้ารันเสร็จแล้ว
    if os.path.exists(temp_file_path):
        print(f"\n📍 [SKIP] พบข้อมูลของ {thai_name} แล้ว โหลดจากไฟล์เดิม (Resume)")
        return temp_file_path
        
    print(f"\n📍 เริ่มต้นดึงข้อมูล: {thai_name}")
    
    try:
        # 1. OSM Phase
        osm_pois = scrape_osm_restaurants(
            province, spatial_tree, spatial_polygons, spatial_properties,
            osm_last_edit_filter=osm_last_edit_filter, osm_last_edit_min_ce=osm_last_edit_min_ce,
            osm_created_filter=osm_created_filter, osm_created_min_ce=osm_created_min_ce,
        )

        # 2. Google Maps Phase
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--lang=th-TH,th"])
            context = browser.new_context(locale="th-TH", viewport={"width": 1280, "height": 800})
            page = context.new_page()

            gmaps_pois = scrape_gmaps_restaurants_by_geojson_areas(
                province, osm_pois, page,
                admin3_by_province, province_boundaries,
                spatial_tree, spatial_polygons, spatial_properties,
                gmaps_review_filter=gmaps_review_filter, gmaps_review_min_ce=gmaps_review_min_ce,
            )
            browser.close()
            
        # Combine
        province_total = osm_pois + gmaps_pois
        print(f"  => [✅ สำเร็จ] {thai_name}: รวมได้ {len(province_total)} ร้าน")
        
        # Save to temp file
        temp_file_path = os.path.join(temp_dir, f"restaurants_{slug}.json")
        with open(temp_file_path, "w", encoding="utf-8") as f:
            json.dump(province_total, f, ensure_ascii=False, indent=2)
            
        return temp_file_path
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดกับจังหวัด {thai_name}: {e}")
        return None

def scrape_restaurants(
    output_path: str,
    parallel_workers: int = 4,
    extract_admin_areas: bool = None,
    osm_last_edit_filter: bool = False, osm_last_edit_min_ce: int = None,
    osm_created_filter: bool = False, osm_created_min_ce: int = None,
    gmaps_review_filter: bool = False, gmaps_review_min_ce: int = None,
):
    print("=" * 60)
    print(f"🚀 Starting Dedicated Restaurant Scraper (Parallel Workers: {parallel_workers})")
    print("=" * 60)

    if extract_admin_areas is None:
        extract_admin_areas = prompt_admin_areas("Restaurant Scraper")
    if not any([osm_last_edit_filter, osm_created_filter, gmaps_review_filter]):
        osm_last_edit_filter, osm_last_edit_min_ce = prompt_osm_last_edit_filter()
        osm_created_filter, osm_created_min_ce = prompt_osm_created_filter()
        gmaps_review_filter, gmaps_review_min_ce = prompt_gmaps_review_filter()
        
    print("  Search areas: GeoJSON admin3 centroids")
    province_boundaries = load_target_boundaries()
    admin3_by_province = load_admin3_centroids()
    
    if extract_admin_areas:
        spatial_tree, spatial_polygons, spatial_properties = build_spatial_index()
    else:
        print("  -> Skipping Sub-district and District extraction.")
        spatial_tree, spatial_polygons, spatial_properties = None, [], []
    
    # สร้างโฟลเดอร์ชั่วคราวสำหรับเก็บไฟล์แยกรายจังหวัดเพื่อป้องกัน Race Condition
    temp_dir = os.path.join(os.path.dirname(output_path), "temp_restaurants")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_files = []
    
    # รันแบบขนาน (Parallel) โดยใช้ ThreadPoolExecutor 
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        futures = []
        for province in PROVINCE_DATA:
            futures.append(
                executor.submit(
                    scrape_province_task,
                    province, admin3_by_province, province_boundaries,
                    temp_dir, spatial_tree, spatial_polygons, spatial_properties,
                    osm_last_edit_filter, osm_last_edit_min_ce,
                    osm_created_filter, osm_created_min_ce,
                    gmaps_review_filter, gmaps_review_min_ce,
                )
            )
            
        for future in concurrent.futures.as_completed(futures):
            temp_file = future.result()
            if temp_file:
                temp_files.append(temp_file)

    # ==========================================
    # Merge Phase: รวมไฟล์ทั้งหมดเข้าด้วยกัน
    # ==========================================
    print(f"\n🔄 กำลังรวมไฟล์จากทั้งหมด {len(temp_files)} จังหวัด...")
    all_restaurants = []
    for t_file in temp_files:
        if os.path.exists(t_file):
            with open(t_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                all_restaurants.extend(data)
                
    # Save Final Output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_restaurants, f, ensure_ascii=False, indent=2)

    # Clean up temp directory
    try:
        shutil.rmtree(temp_dir)
    except:
        pass

    print(f"\n{'='*60}")
    print(f"✅ Done! Total Restaurants: {len(all_restaurants)}")
    print(f"💾 Saved to: {output_path}")
    print("=" * 60)

if __name__ == "__main__":
    scrape_restaurants("../data/raw/restaurants_raw.json", parallel_workers=4)
