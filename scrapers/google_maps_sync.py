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
import json
import os
import re
import time


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


def extract_lat_lon_from_url(url: str):
    """ดึง lat/lon จาก URL ของ Google Maps"""
    # Pattern: @16.4322,102.8236,
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    # Pattern: !3d16.4322!4d102.8236
    match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


def scrape_google_maps_pois(province_name: str, search_query: str, page, max_results=15):
    """ค้นหา POI ใน Google Maps และดึงข้อมูลจาก Search Results Panel"""
    results = []

    try:
        full_query = f"{search_query} {province_name}"
        search_url = f"https://www.google.com/maps/search/{full_query.replace(' ', '+')}"

        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        # รอให้ผลการค้นหาโหลด
        try:
            page.wait_for_selector('div[role="feed"], div.Nv2PK', timeout=10000)
        except:
            return results

        # เลื่อนหน้าเพื่อโหลดผลลัพธ์เพิ่ม
        feed = page.query_selector('div[role="feed"]')
        if feed:
            for _ in range(3):
                feed.evaluate("el => el.scrollTop += 500")
                page.wait_for_timeout(800)

        # ดึงรายการ POI จาก Search Results
        items = page.query_selector_all('div.Nv2PK, a[href*="maps/place"]')

        for item in items[:max_results]:
            try:
                # ชื่อสถานที่
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
                    current_url = page.url
                    lat, lon = extract_lat_lon_from_url(current_url)
                except:
                    lat, lon = None, None

                if lat and lon:
                    results.append({
                        "name": name,
                        "lat": lat,
                        "lon": lon,
                    })

                # กลับไปหน้า Search
                page.go_back()
                page.wait_for_timeout(1000)

            except Exception:
                continue

    except Exception as e:
        print(f"    Error searching '{search_query}' in {province_name}: {e}")

    return results


def scrape_google_maps_sync(osm_raw_path: str, output_path: str):
    """
    Main function: ค้นหา POI จาก Google Maps แล้วรวมกับข้อมูล OSM ที่มีอยู่
    """
    print("=" * 55)
    print("Google Maps Sync (Hybrid Enrichment)")
    print("=" * 55)

    # โหลดข้อมูล OSM เดิมเพื่อใช้ Dedup
    osm_pois = []
    if os.path.exists(osm_raw_path):
        with open(osm_raw_path, "r", encoding="utf-8") as f:
            osm_pois = json.load(f)
        print(f"  Loaded {len(osm_pois)} existing OSM POIs")

    new_pois = []

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
            print(f"\n[{thai_name}]")

            for target in SEARCH_TARGETS:
                query = target["query"]
                category = target["category"]
                layer = target["layer"]

                print(f"  Searching '{query}'...", end=" ", flush=True)
                pois = scrape_google_maps_pois(thai_name, query, page)

                # Dedup: Layer 1 ใช้ radius 300m (anchor ใหญ่ อาจมีพิกัดต่างกันนิดหน่อย)
                #        Layer 2/3 ใช้ radius 100m
                dedup_radius_km = 0.3 if layer == 1 else 0.1
                added = 0
                for poi in pois:
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
                        new_pois.append({
                            "province":    thai_name,
                            "province_en": slug,
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

                print(f"{len(pois)} found, {added} new added.")
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
