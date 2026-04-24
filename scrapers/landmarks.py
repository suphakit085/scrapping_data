import requests
import json
import os
import time

OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"

def run_overpass_query(query: str) -> list:
    """Run an Overpass QL query and return list of elements."""
    for mirror in [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]:
        try:
            r = requests.get(mirror, params={"data": query},
                             headers={"User-Agent": "BI-Pipeline/1.0"},
                             timeout=60)
            if r.status_code == 200 and r.text.strip():
                return r.json().get("elements", [])
        except Exception as e:
            print(f"    Mirror {mirror} failed: {e}")
            continue
    print("    All Overpass mirrors failed.")
    return []

def get_coords(element: dict) -> tuple:
    """Extract lat/lon from a node or centroid of way/relation."""
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    elif "center" in element:
        return element["center"]["lat"], element["center"]["lon"]
    return None, None


# ============================================================
# Layer Definitions (Overpass Tag Queries)
# ============================================================
# Layer 1: สถานที่สำคัญหลัก — มีผลต่อเศรษฐกิจ สุขภาพ ขนส่ง และการศึกษาระดับสูง
#           เหล่านี้คือ "Anchor" ที่ใช้สร้าง Zone Center
# Layer 2: จุดสังเกต / อัตลักษณ์พื้นที่ — เป็นเอกลักษณ์ มีชื่อเสียง รู้จักในท้องถิ่น
# Layer 3: สถานที่สำคัญระดับรอง — ปัจจัย 4 รายวัน (ใช้คำนวณ Livability Score)
# ============================================================

def build_layer1_query(area_id: int) -> str:
    """
    Layer 1: สถานที่สำคัญหลัก
    - เศรษฐกิจ: ห้างสรรพสินค้า, ตลาดกลางขนาดใหญ่, นิคมอุตสาหกรรม
    - สุขภาพ: โรงพยาบาลขนาดใหญ่ (รัฐ/เอกชน ระดับศูนย์)
    - ขนส่ง: สนามบิน, สถานีรถไฟ, สถานีขนส่งผู้โดยสาร
    - การศึกษา: มหาวิทยาลัย, วิทยาลัยเทคนิค
    - ราชการ: ศาลากลาง, ที่ว่าการอำเภอ
    """
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Economic: Shopping Malls & Department Stores
      nwr["shop"="mall"](area.searchArea);
      nwr["shop"="department_store"](area.searchArea);
      // Economic: Large Hypermarkets (Lotus, BigC, Makro, HomePro)
      nwr["shop"="supermarket"]["brand"~"Lotus|Big C|Makro|HomePro|Tesco",i](area.searchArea);
      nwr["shop"="wholesale"](area.searchArea);
      nwr["shop"="doityourself"](area.searchArea);
      // Economic: Large Markets / OTOP
      nwr["amenity"="marketplace"]["market_type"="large"](area.searchArea);
      // Economic: Industrial Estate / SEZ
      nwr["landuse"="industrial"]["industrial"="port"](area.searchArea);
      // Health: Hospitals
      nwr["amenity"="hospital"](area.searchArea);
      // Transport: Airports, Train, Bus Terminals
      nwr["aeroway"="aerodrome"](area.searchArea);
      nwr["aeroway"="terminal"](area.searchArea);
      nwr["railway"="station"](area.searchArea);
      nwr["amenity"="bus_station"](area.searchArea);
      // Education: Universities & Technical Colleges
      nwr["amenity"="university"](area.searchArea);
      nwr["amenity"="college"](area.searchArea);
      // Government: Provincial Hall, District Office
      nwr["amenity"="townhall"](area.searchArea);
      nwr["building"="government"](area.searchArea);
      nwr["office"="government"](area.searchArea);
    );
    out center tags;
    """

def build_layer2_query(area_id: int) -> str:
    """
    Layer 2: จุดสังเกต / อัตลักษณ์พื้นที่
    - เอกลักษณ์ไทย: ประตูเมือง, ศาลหลักเมือง, อนุสาวรีย์ดัง, วัดสำคัญ
    - สันทนาการ: บึงขนาดใหญ่, สวนสาธารณะหลักของเมือง, สนามกีฬา
    - ท่องเที่ยว: สถานที่ท่องเที่ยวที่รู้จักระดับจังหวัด
    """
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Identity: City Gates, City Pillars, Shrines
      nwr["historic"="city_gate"](area.searchArea);
      nwr["historic"="wayside_shrine"](area.searchArea);
      nwr["amenity"="place_of_worship"]["religion"="buddhist"]["wikipedia"](area.searchArea);
      // Identity: Monuments & Memorials
      nwr["historic"="monument"](area.searchArea);
      nwr["historic"="memorial"](area.searchArea);
      nwr["historic"="castle"](area.searchArea);
      nwr["historic"="ruins"](area.searchArea);
      // Recreation: Major parks, lakes, stadiums
      nwr["leisure"="park"](area.searchArea);
      nwr["natural"="water"]["water"="lake"](area.searchArea);
      nwr["leisure"="stadium"](area.searchArea);
      nwr["leisure"="sports_centre"](area.searchArea);
      // Tourism: Known attractions
      nwr["tourism"="attraction"](area.searchArea);
      nwr["tourism"="museum"](area.searchArea);
      nwr["tourism"="zoo"](area.searchArea);
      nwr["tourism"="theme_park"](area.searchArea);
    );
    out center tags;
    """

def build_layer3_query(area_id: int) -> str:
    """
    Layer 3: สถานที่สำคัญระดับรอง (ปัจจัย 4 รายวัน)
    - ร้านสะดวกซื้อ: 7-11, CJ, FamilyMart
    - ซูเปอร์มาร์เก็ตทั่วไป (ขนาดเล็ก)
    - ร้านขายยา, คลินิก, ศูนย์แพทย์
    - ตลาดสด, ตลาดนัด
    - โรงเรียนระดับประถม/มัธยม, อนุบาล
    - ธนาคาร, ตู้ ATM
    - ปั๊มน้ำมัน
    """
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Convenience Stores (7-11, CJ, FamilyMart)
      nwr["shop"="convenience"](area.searchArea);
      // Supermarkets (general, smaller scale)
      nwr["shop"="supermarket"](area.searchArea);
      // Health: Pharmacies, Clinics, Medical Centers
      nwr["amenity"="pharmacy"](area.searchArea);
      nwr["amenity"="clinic"](area.searchArea);
      nwr["amenity"="doctors"](area.searchArea);
      nwr["healthcare"="centre"](area.searchArea);
      // Markets: Fresh markets, night markets
      nwr["amenity"="marketplace"](area.searchArea);
      nwr["shop"="market"](area.searchArea);
      // Schools: Primary, Secondary, Kindergarten
      nwr["amenity"="school"](area.searchArea);
      nwr["amenity"="kindergarten"](area.searchArea);
      // Finance: Banks, ATMs
      nwr["amenity"="bank"](area.searchArea);
      nwr["amenity"="atm"](area.searchArea);
      // Transport: Gas stations
      nwr["amenity"="fuel"](area.searchArea);
    );
    out center tags;
    """


# ============================================================
# Category Classifier
# ============================================================

# Sub-classifier ช่วยแยกประเภทที่ละเอียดขึ้น เช่น แยก Lotus/BigC ออกจาก supermarket ทั่วไป
LARGE_HYPERMARKET_BRANDS = {
    "lotus", "lotus's", "big c", "bigc", "makro", "homepro",
    "tesco", "tesco lotus", "global house", "thai watsadu"
}

ICONIC_TEMPLE_NAMES = {
    "พระธาตุ", "หลวงพ่อ", "วัดหลวง", "วัดพระ", "พระวิหาร"
}

def classify_poi(tags: dict, layer: int) -> str:
    """Map OSM tags to human-readable Thai category."""

    name = (tags.get("name", "") or "").lower()
    brand = (tags.get("brand", "") or "").lower()
    check_brand = name or brand

    # --- Layer 1 ---
    if layer == 1:
        shop = tags.get("shop", "")
        if shop in ("mall", "department_store"):
            return "ห้างสรรพสินค้า"
        if shop == "supermarket":
            # ถ้าเป็น brand ใหญ่จัดเป็น Hypermarket
            if any(b in check_brand for b in LARGE_HYPERMARKET_BRANDS):
                return "ไฮเปอร์มาร์เก็ต"
            return "ซูเปอร์มาร์เก็ต"
        if shop in ("wholesale", "doityourself"):
            return "ไฮเปอร์มาร์เก็ต"
        if tags.get("amenity") == "hospital":
            return "โรงพยาบาล"
        if tags.get("aeroway") in ("aerodrome", "terminal"):
            return "สนามบิน"
        if tags.get("railway") == "station":
            return "สถานีรถไฟ"
        if tags.get("amenity") == "bus_station":
            return "สถานีขนส่ง"
        if tags.get("amenity") == "university":
            return "มหาวิทยาลัย"
        if tags.get("amenity") == "college":
            return "วิทยาลัย"
        if tags.get("amenity") == "townhall":
            return "ศาลากลาง/ที่ว่าการ"
        if tags.get("building") == "government" or tags.get("office") == "government":
            return "หน่วยงานรัฐ"
        if tags.get("landuse") == "industrial":
            return "นิคมอุตสาหกรรม"

    # --- Layer 2 ---
    if layer == 2:
        historic = tags.get("historic", "")
        if historic == "city_gate":
            return "ประตูเมือง"
        if historic in ("monument", "memorial"):
            return "อนุสาวรีย์/อนุสรณ์"
        if historic in ("castle", "ruins"):
            return "โบราณสถาน"
        if historic == "wayside_shrine":
            return "ศาลเจ้า/ศาลหลักเมือง"
        if tags.get("amenity") == "place_of_worship":
            # วัดที่มี Wikipedia = วัดสำคัญ
            if tags.get("wikipedia") or any(k in name for k in ["พระธาตุ", "หลวงพ่อ", "วัดหลวง", "วัดพระ"]):
                return "วัดสำคัญ"
            return "วัด/ศาสนสถาน"
        leisure = tags.get("leisure", "")
        if leisure == "park":
            return "สวนสาธารณะ"
        if leisure == "stadium":
            return "สนามกีฬา"
        if leisure == "sports_centre":
            return "ศูนย์กีฬา"
        if tags.get("natural") == "water":
            return "บึง/ทะเลสาบ"
        tourism = tags.get("tourism", "")
        if tourism == "attraction":
            return "สถานที่ท่องเที่ยว"
        if tourism == "museum":
            return "พิพิธภัณฑ์"
        if tourism == "zoo":
            return "สวนสัตว์"
        if tourism == "theme_park":
            return "สวนสนุก"

    # --- Layer 3 ---
    if layer == 3:
        shop = tags.get("shop", "")
        if shop == "convenience":
            return "ร้านสะดวกซื้อ"
        if shop == "supermarket":
            if any(b in check_brand for b in LARGE_HYPERMARKET_BRANDS):
                return "ไฮเปอร์มาร์เก็ต"
            return "ซูเปอร์มาร์เก็ต"
        amenity = tags.get("amenity", "")
        if amenity == "pharmacy":
            return "ร้านขายยา"
        if amenity in ("clinic", "doctors"):
            return "คลินิก"
        if tags.get("healthcare") == "centre":
            return "ศูนย์การแพทย์"
        if amenity == "marketplace" or shop == "market":
            return "ตลาด"
        if amenity == "school":
            return "โรงเรียน"
        if amenity == "kindergarten":
            return "โรงเรียนอนุบาล"
        if amenity == "bank":
            return "ธนาคาร"
        if amenity == "atm":
            return "ตู้ATM"
        if amenity == "fuel":
            return "ปั๊มน้ำมัน"

    return f"สถานที่ระดับ {layer}"


# ============================================================
# Main Scraper
# ============================================================

# Verified Relation IDs from OpenStreetMap (admin_level=6, Amphoe Mueang)
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

LAYER_BUILDERS = [
    (1, "สถานที่สำคัญหลัก",    build_layer1_query),
    (2, "จุดอัตลักษณ์พื้นที่",  build_layer2_query),
    (3, "สิ่งอำนวยความสะดวก",  build_layer3_query),
]

def scrape_landmarks(output_path: str):
    print("=" * 50)
    print("Starting Landmarks Scraper (Overpass API)")
    print("=" * 50)

    all_pois = []

    for province in PROVINCE_DATA:
        thai_name = province["name"]
        slug      = province["slug"]
        rel_id    = province["relation_id"]
        area_id   = rel_id + 3600000000  # Overpass area ID = relation ID + 3.6B

        print(f"\n[{thai_name}]")

        for layer_num, layer_name, query_builder in LAYER_BUILDERS:
            print(f"  Layer {layer_num} ({layer_name})...", end=" ")

            query    = query_builder(area_id)
            elements = run_overpass_query(query)
            count    = 0

            for el in elements:
                tags = el.get("tags", {})
                lat, lon = get_coords(el)
                if lat is None:
                    continue

                name    = tags.get("name", tags.get("name:th", tags.get("name:en", "")))
                name_en = tags.get("name:en", "")

                # Skip unnamed POIs for Layer 1 & 2 (ต้องมีชื่อ)
                if not name and layer_num < 3:
                    continue

                category = classify_poi(tags, layer_num)

                all_pois.append({
                    "province":    thai_name,
                    "province_en": slug,
                    "name":        name,
                    "name_en":     name_en,
                    "category":    category,
                    "layer":       layer_num,
                    "layer_name":  layer_name,
                    "lat":         lat,
                    "lon":         lon,
                    "osm_type":    el.get("type"),
                    "osm_id":      el.get("id"),
                    "source":      "OpenStreetMap / Overpass API"
                })
                count += 1

            print(f"{count} POIs found.")
            time.sleep(1.5)  # Polite delay

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_pois, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"Done! Total POIs: {len(all_pois)}")
    print(f"Saved to: {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    scrape_landmarks("../data/raw/landmarks_raw.json")
