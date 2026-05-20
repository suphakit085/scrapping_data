"""
Google Maps Discovery + Sync Scraper
หน้าที่ 2 อย่าง:
  1. SYNC  — เสริมข้อมูล OSM ที่มีอยู่ด้วยพิกัดจาก Google Maps (ข้อมูลอัปเดตกว่า)
  2. DISCOVERY — ค้นหา POI ใหม่ที่ OSM ยังไม่มี เช่น ห้างเปิดใหม่, โครงการก่อสร้าง

ครอบคลุมทั้ง 3 Layer:
  Layer 1: สถานที่สำคัญหลัก (ห้าง, รพ., มหาวิทยาลัย, ขนส่ง, ราชการ)
  Layer 2: จุดอัตลักษณ์พื้นที่ (ประตูเมือง, บึง, วัดดัง, สนามกีฬา)
  Layer 3: สิ่งอำนวยความสะดวก (7-11, ตลาด, คลินิก, ร้านยา)
"""

from playwright.sync_api import sync_playwright
from shapely.geometry import Point, shape
from shapely.prepared import prep
import json
import os
import re
import time

from utils.geo_boundaries import (
    build_spatial_index,
    reverse_geocode,
    prompt_admin_areas,
)


# =============================================================
# SEARCH_TARGETS — POI ที่จะให้บอทค้นหาจาก Google Maps
# แบ่งตาม Layer เพื่อให้ครอบคลุม 3 ระดับตามที่หัวหน้ากำหนด
# =============================================================
SEARCH_TARGETS = [
    # ---- Layer 1: สถานที่สำคัญหลัก (Anchor) ----
    # Discovery: ห้างใหม่ที่ OSM อาจยังไม่มี
    {"query": "เซ็นทรัล",            "category": "ห้างสรรพสินค้า",     "layer": 1},
    {"query": "Central",             "category": "ห้างสรรพสินค้า",     "layer": 1},
    {"query": "ห้างสรรพสินค้า",     "category": "ห้างสรรพสินค้า",     "layer": 1},
    {"query": "Community Mall",      "category": "ห้างสรรพสินค้า",     "layer": 1},
    {"query": "โลตัส",               "category": "ไฮเปอร์มาร์เก็ต",   "layer": 1},
    {"query": "Big C",               "category": "ไฮเปอร์มาร์เก็ต",   "layer": 1},
    {"query": "Makro",               "category": "ไฮเปอร์มาร์เก็ต",   "layer": 1},
    {"query": "HomePro",             "category": "ไฮเปอร์มาร์เก็ต",   "layer": 1},
    {"query": "โรงพยาบาล",           "category": "โรงพยาบาล",          "layer": 1},
    {"query": "มหาวิทยาลัย",         "category": "มหาวิทยาลัย",        "layer": 1},
    {"query": "สถานีขนส่ง",          "category": "สถานีขนส่ง",         "layer": 1},
    {"query": "สนามบิน",             "category": "สนามบิน",            "layer": 1},

    # ---- Layer 2: จุดอัตลักษณ์พื้นที่ ----
    {"query": "ประตูเมือง",          "category": "ประตูเมือง",          "layer": 2},
    {"query": "ศาลหลักเมือง",        "category": "ศาลเจ้า/ศาลหลักเมือง", "layer": 2},
    {"query": "บึง",                 "category": "บึง/ทะเลสาบ",        "layer": 2},
    {"query": "อนุสาวรีย์",          "category": "อนุสาวรีย์/อนุสรณ์",  "layer": 2},
    {"query": "สนามกีฬา",           "category": "สนามกีฬา",           "layer": 2},
    {"query": "สวนสาธารณะ",         "category": "สวนสาธารณะ",         "layer": 2},
    {"query": "พิพิธภัณฑ์",          "category": "พิพิธภัณฑ์",          "layer": 2},

    # ---- Layer 3: สิ่งอำนวยความสะดวก ----
    {"query": "7-Eleven",            "category": "ร้านสะดวกซื้อ",      "layer": 3},
    {"query": "CJ More",             "category": "ร้านสะดวกซื้อ",      "layer": 3},
    {"query": "ตลาดสด",             "category": "ตลาด",               "layer": 3},
    {"query": "ตลาดนัด",            "category": "ตลาด",               "layer": 3},
    {"query": "คลินิก",             "category": "คลินิก",             "layer": 3},
    {"query": "ร้านขายยา",          "category": "ร้านขายยา",          "layer": 3},
    {"query": "โรงเรียน",            "category": "โรงเรียน",           "layer": 3},
]

PROVINCES = [
    {"name": "ขอนแก่น",        "slug": "khon-kaen"},
    {"name": "อุบลราชธานี",     "slug": "ubon-ratchathani"},
    {"name": "ประจวบคีรีขันธ์", "slug": "prachuap-khiri-khan"},
    {"name": "อุดรธานี",        "slug": "udon-thani"},
    {"name": "ระยอง",           "slug": "rayong"},
    {"name": "ชลบุรี",          "slug": "chonburi"},
    {"name": "สุรินทร์",        "slug": "surin"},
    {"name": "บุรีรัมย์",       "slug": "buriram"},
    {"name": "พิษณุโลก",        "slug": "phitsanulok"},
    {"name": "เชียงราย",        "slug": "chiang-rai"},
]


CLOSED_LABELS = [
    "permanently closed",
    "temporarily closed",
    "closed permanently",
    "closed temporarily",
    "ปิดถาวร",
    "ปิดชั่วคราว",
]


def is_closed_google_maps_text(text):
    lowered = (text or "").lower()
    return any(label in lowered for label in CLOSED_LABELS)


TARGET_BOUNDARY_PATH = "data/raw/target_admin_boundaries.geojson"

PROVINCE_SLUG_TO_ADM1 = {
    "khon-kaen": "Khon Kaen",
    "ubon-ratchathani": "Ubon Ratchathani",
    "prachuap-khiri-khan": "Prachuap Khiri Khan",
    "udon-thani": "Udon Thani",
    "rayong": "Rayong",
    "chonburi": "Chon Buri",
    "surin": "Surin",
    "buriram": "Buri Ram",
    "phitsanulok": "Phitsanulok",
    "chiang-rai": "Chiang Rai",
}

PROVINCE_ALIASES = {
    "chonburi": "Chon Buri",
    "chon buri": "Chon Buri",
    "buriram": "Buri Ram",
    "buri ram": "Buri Ram",
    "prachuapkhirikhan": "Prachuap Khiri Khan",
    "prachuap khiri khan": "Prachuap Khiri Khan",
}


def _repo_path(relative_path: str) -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    return os.path.join(repo_root, relative_path)


def normalize_province_name(name):
    if not name:
        return ""

    cleaned = str(name).strip()
    key = re.sub(r"[^a-z0-9]+", " ", cleaned.lower()).strip()
    compact_key = key.replace(" ", "")

    if key in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[key]
    if compact_key in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[compact_key]

    for canonical in PROVINCE_SLUG_TO_ADM1.values():
        canonical_key = re.sub(r"[^a-z0-9]+", " ", canonical.lower()).strip()
        if key == canonical_key or compact_key == canonical_key.replace(" ", ""):
            return canonical

    return cleaned


def load_target_boundaries(boundary_path=TARGET_BOUNDARY_PATH):
    abs_path = _repo_path(boundary_path)
    if not os.path.exists(abs_path):
        print(f"  [WARN] Target boundary file not found: {abs_path}")
        print("  [WARN] Run: python utils/preprocess_target_boundaries.py")
        print("  [WARN] Falling back to Thailand bounding-box filtering only.")
        return {}

    with open(abs_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    boundaries = {}
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        province = normalize_province_name(
            props.get("adm1_name_normalized") or props.get("adm1_name")
        )
        if not province:
            continue

        try:
            boundaries.setdefault(province, []).append(prep(shape(feature["geometry"])))
        except Exception as e:
            print(f"  [WARN] Skipping invalid boundary for {province}: {e}")

    print(
        f"  [OK] Loaded province boundaries: "
        f"{len(boundaries)} provinces, {sum(len(v) for v in boundaries.values())} polygons"
    )
    return boundaries


def is_in_thailand_bounds(lat, lon):
    return (5.0 <= lat <= 20.5) and (97.0 <= lon <= 106.0)


def is_point_in_target_province(lat, lon, province_en, province_boundaries):
    if not is_in_thailand_bounds(lat, lon):
        return False

    province_key = normalize_province_name(province_en)
    province_geoms = province_boundaries.get(province_key)
    if not province_geoms:
        return True

    point = Point(lon, lat)
    return any(geom.contains(point) or geom.intersects(point) for geom in province_geoms)


def _load_local_iconic_targets(config_path="data/raw/local_iconic_targets.json"):
    """
    Load province-specific Layer 2 search targets.

    Expected JSON shape:
    {
      "ขอนแก่น": [
        {"query": "ประตูเมืองขอนแก่น", "category": "ประตูเมือง", "layer": 2}
      ]
    }
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    abs_path = os.path.join(repo_root, config_path)

    if not os.path.exists(abs_path):
        print(f"  [INFO] Local iconic config not found: {abs_path}")
        return {}

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        print(f"  [WARN] Failed to load local iconic config: {e}")
        return {}

    normalized = {}
    for province_name, targets in raw.items():
        if not isinstance(targets, list):
            continue

        safe_targets = []
        for t in targets:
            if not isinstance(t, dict):
                continue
            query = str(t.get("query", "")).strip()
            category = str(t.get("category", "จุดอัตลักษณ์พื้นที่")).strip()
            layer = int(t.get("layer", 2))

            if not query:
                continue

            safe_targets.append({
                "query": query,
                "category": category,
                "layer": layer,
            })

        if safe_targets:
            normalized[province_name] = safe_targets

    print(f"  [OK] Loaded local iconic targets for {len(normalized)} provinces")
    return normalized


def extract_lat_lon_from_url(url: str):
    """ดึง lat/lon จาก URL ของ Google Maps"""
    # Pattern 1: !3d16.4322!4d102.8236 (Pin location - Prioritize this)
    match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    # Pattern 2: @16.4322,102.8236, (Viewport center - Fallback)
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


def scrape_google_maps_pois(province_name: str, search_query: str, page, max_results=15):
    """ค้นหา POI ใน Google Maps และดึงข้อมูลจาก Search Results Panel"""
    results = []

    try:
        # ป้องกันคำซ้ำ เช่น "ศาลหลักเมืองขอนแก่น ขอนแก่น"
        if province_name in search_query:
            full_query = search_query
        else:
            full_query = f"{search_query} {province_name}"
            
        search_url = f"https://www.google.com/maps/search/{full_query.replace(' ', '+')}"

        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # 1. ตรวจสอบก่อนว่ามัน Redirect ไปหน้าสถานที่เดียว (Place Page) เลยหรือเปล่า
        current_url = page.url
        if "/maps/place/" in current_url:
            if is_closed_google_maps_text(page.content()):
                print("(Skipped: Closed place)", end=" ")
                return []
            lat, lon = extract_lat_lon_from_url(current_url)
            # ดึงชื่อจากหัวข้อหน้าเว็บ
            name_el = page.query_selector('h1.duvuxb') # Class ปกติของชื่อสถานที่ในหน้า Place
            name = name_el.inner_text().strip() if name_el else search_query
            if lat and lon:
                if is_in_thailand_bounds(lat, lon):
                    print(f"(Direct Match: {name})", end=" ")
                    return [{"name": name, "lat": lat, "lon": lon}]
                else:
                    print(f"(Skipped: Out of bounds - {name})", end=" ")
                    return []

        # 2. ถ้าไม่ Redirect ให้รอหน้ารายการ (Feed) ตามปกติ
        try:
            page.wait_for_selector('div[role="feed"], div.Nv2PK', timeout=8000)
        except:
            return results

        # เลื่อนหน้าเพื่อโหลดผลลัพธ์เพิ่ม
        feed = page.query_selector('div[role="feed"]')
        if feed:
            for _ in range(2):
                feed.evaluate("el => el.scrollTop += 500")
                page.wait_for_timeout(800)

        # ดึงรายการ POI จาก Search Results
        items = page.query_selector_all('div.Nv2PK, a[href*="maps/place"]')

        for item in items[:max_results]:
            try:
                # ชื่อสถานที่
                try:
                    if is_closed_google_maps_text(item.inner_text()):
                        continue
                except Exception:
                    pass

                name_el = item.query_selector('div.qBF1Pd, .fontHeadlineSmall, [aria-label]')
                name = name_el.inner_text().strip() if name_el else ""
                if not name:
                    aria = item.get_attribute("aria-label") or ""
                    name = aria.strip()

                if not name or len(name) < 2:
                    continue

                # คลิกเพื่อดูพิกัดจาก URL
                try:
                    item.click()
                    page.wait_for_timeout(1500)
                    if is_closed_google_maps_text(page.content()):
                        page.go_back()
                        page.wait_for_timeout(1000)
                        continue
                    current_url = page.url
                    lat, lon = extract_lat_lon_from_url(current_url)
                except:
                    lat, lon = None, None

                if lat and lon:
                    if is_in_thailand_bounds(lat, lon):
                        results.append({
                            "name": name,
                            "lat": lat,
                            "lon": lon,
                        })
                    else:
                        print(f"    [Warning] พิกัดอยู่นอกประเทศไทย ข้ามสถานที่: {name}")

                # กลับไปหน้า Search
                page.go_back()
                page.wait_for_timeout(1000)

            except Exception:
                continue

    except Exception as e:
        print(f"    Error searching '{search_query}' in {province_name}: {e}")

    return results


def scrape_google_maps_sync(osm_raw_path: str, output_path: str, extract_admin_areas: bool = None):
    """
    Main function: ค้นหา POI จาก Google Maps แล้วรวมกับข้อมูล OSM ที่มีอยู่
    """
    print("=" * 55)
    print("Google Maps Sync (Hybrid Enrichment)")
    print("=" * 55)

    # Prompt the user via interactive terminal UI if not passed
    if extract_admin_areas is None:
        extract_admin_areas = prompt_admin_areas("Google Maps Sync")

    # โหลดข้อมูล OSM เดิมเพื่อใช้ Dedup
    osm_pois = []
    if os.path.exists(osm_raw_path):
        with open(osm_raw_path, "r", encoding="utf-8") as f:
            osm_pois = json.load(f)
        print(f"  Loaded {len(osm_pois)} existing OSM POIs")

    new_pois = []
    local_iconic_by_province = _load_local_iconic_targets()
    province_boundaries = load_target_boundaries()

    if extract_admin_areas:
        spatial_tree, spatial_polygons, spatial_properties = build_spatial_index()
        # Enrich existing OSM POIs if they don't have district/sub_district
        print("  -> Enriching existing OSM POIs with district and sub-district information...")
        for poi in osm_pois:
            if "district" not in poi or "sub_district" not in poi:
                lat, lon = poi.get("lat"), poi.get("lon")
                if lat and lon:
                    district, sub_district = reverse_geocode(lat, lon, spatial_tree, spatial_polygons, spatial_properties)
                    poi["district"] = district
                    poi["sub_district"] = sub_district
    else:
        print("  -> Skipping Sub-district and District extraction.")
        spatial_tree, spatial_polygons, spatial_properties = None, [], []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--lang=th-TH,th"]
        )
        context = browser.new_context(
            locale="th-TH",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        for province in PROVINCES:
            thai_name = province["name"]
            slug = province["slug"]
            province_en = normalize_province_name(PROVINCE_SLUG_TO_ADM1.get(slug, slug))
            print(f"\n[{thai_name}]")
            if province_boundaries and province_en not in province_boundaries:
                print(f"  [WARN] No boundary found for {province_en}; using country bounds only.")

            targets = list(SEARCH_TARGETS)
            targets.extend(local_iconic_by_province.get(thai_name, []))

            seen_queries = set()
            province_targets = []
            for target in targets:
                key = (
                    target.get("query", "").strip().lower(),
                    target.get("category", "").strip().lower(),
                    int(target.get("layer", 2)),
                )

                if not key[0] or key in seen_queries:
                    continue
                seen_queries.add(key)
                province_targets.append(target)

            for target in province_targets:
                query = target["query"]
                category = target["category"]
                layer = target["layer"]

                print(f"  Searching '{query}'...", end=" ", flush=True)
                pois = scrape_google_maps_pois(thai_name, query, page)

                # Dedup: สถานที่ที่มีพื้นที่กว้างใช้ radius 400m
                large_area_categories = ["โรงเรียน", "มหาวิทยาลัย", "วิทยาลัย", "สวนสาธารณะ", "บึง/ทะเลสาบ", "สนามกีฬา"]
                if category in large_area_categories:
                    dedup_radius_km = 0.4
                else:
                    # Layer 1 ใช้ radius 300m (anchor ใหญ่), Layer 2/3 ใช้ radius 100m
                    dedup_radius_km = 0.3 if layer == 1 else 0.1

                added = 0
                skipped_outside_province = 0
                for poi in pois:
                    if not is_point_in_target_province(
                        poi["lat"], poi["lon"], province_en, province_boundaries
                    ):
                        skipped_outside_province += 1
                        continue

                    is_duplicate = False
                    for existing in osm_pois + new_pois:
                        if existing.get("province") != thai_name:
                            continue
                        ex_lat = existing.get("lat")
                        ex_lon = existing.get("lon")
                        if ex_lat and ex_lon:
                            import math
                            dlat = math.radians(poi["lat"] - ex_lat)
                            dlon = math.radians(poi["lon"] - ex_lon)
                            a = (math.sin(dlat/2)**2 +
                                 math.cos(math.radians(ex_lat)) *
                                 math.cos(math.radians(poi["lat"])) *
                                 math.sin(dlon/2)**2)
                            dist_km = 6371 * 2 * math.asin(math.sqrt(a))
                            if dist_km < dedup_radius_km:
                                is_duplicate = True
                                break

                    if not is_duplicate:
                        # Map layer number to Thai name (consistent with landmarks.py)
                        layer_name_map = {
                            1: "สถานที่สำคัญหลัก",
                            2: "จุดอัตลักษณ์พื้นที่",
                            3: "สิ่งอำนวยความสะดวก",
                        }
                        
                        district, sub_district = reverse_geocode(poi["lat"], poi["lon"], spatial_tree, spatial_polygons, spatial_properties) if extract_admin_areas else ("", "")

                        new_pois.append({
                            "province":    thai_name,
                            "province_en": province_en,
                            "district":    district,
                            "sub_district": sub_district,
                            "name":        poi["name"],
                            "name_en":     "",
                            "category":    category,
                            "layer":       layer,
                            "layer_name":  layer_name_map.get(layer, f"Layer {layer}"),
                            "lat":         poi["lat"],
                            "lon":         poi["lon"],
                            "osm_type":    "google_maps",
                            "osm_id":      None,
                            "source":      "Google Maps"
                        })
                        added += 1

                outside_msg = (
                    f", {skipped_outside_province} outside province skipped"
                    if skipped_outside_province
                    else ""
                )
                print(f"{len(pois)} found, {added} new added{outside_msg}.")
                time.sleep(1.5)

        browser.close()

    # รวมข้อมูล OSM + Google Maps ใหม่
    merged = osm_pois + new_pois

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*55}")
    print(f"  OSM POIs:         {len(osm_pois)}")
    print(f"  Google Maps NEW:  {len(new_pois)}")
    print(f"  Total merged:     {len(merged)}")
    print(f"  Saved to: {output_path}")
    print(f"{'='*55}")


if __name__ == "__main__":
    scrape_google_maps_sync(
        osm_raw_path="../data/raw/landmarks_raw.json",
        output_path="../data/raw/landmarks_raw.json"   # Overwrite เดิมหลัง Enrich
    )
