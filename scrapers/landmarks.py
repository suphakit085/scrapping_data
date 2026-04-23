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

def build_layer1_query(area_id: int) -> str:
    """Layer 1: Primary landmarks (economic, health, transport, large education)"""
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Major Shopping Malls & Department Stores
      nwr["shop"="mall"](area.searchArea);
      nwr["shop"="department_store"](area.searchArea);
      // Major Hospitals
      nwr["amenity"="hospital"](area.searchArea);
      // Airports
      nwr["aeroway"="aerodrome"](area.searchArea);
      nwr["aeroway"="terminal"](area.searchArea);
      // Train / Bus Stations
      nwr["railway"="station"](area.searchArea);
      nwr["amenity"="bus_station"](area.searchArea);
      // Universities & Large Colleges
      nwr["amenity"="university"](area.searchArea);
      nwr["amenity"="college"](area.searchArea);
      // Government Buildings
      nwr["building"="government"](area.searchArea);
      nwr["office"="government"](area.searchArea);
    );
    out center tags;
    """

def build_layer2_query(area_id: int) -> str:
    """Layer 2: Iconic local landmarks (unique to each area)"""
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Tourist Attractions & Monuments
      nwr["tourism"="attraction"](area.searchArea);
      nwr["historic"="monument"](area.searchArea);
      nwr["historic"="memorial"](area.searchArea);
      nwr["historic"="castle"](area.searchArea);
      nwr["historic"="ruins"](area.searchArea);
      // City Gates, Pillars (Thai city icons)
      nwr["historic"="city_gate"](area.searchArea);
      nwr["historic"="wayside_shrine"](area.searchArea);
      // Parks & Large Public Spaces
      nwr["leisure"="park"](area.searchArea);
      nwr["leisure"="stadium"](area.searchArea);
      // Temples (important cultural landmarks)
      nwr["amenity"="place_of_worship"]["religion"="buddhist"](area.searchArea);
    );
    out center tags;
    """

def build_layer3_query(area_id: int) -> str:
    """Layer 3: Secondary / daily life landmarks"""
    return f"""
    [out:json][timeout:60];
    area({area_id})->.searchArea;
    (
      // Convenience Stores
      nwr["shop"="convenience"](area.searchArea);
      nwr["shop"="supermarket"](area.searchArea);
      // Pharmacies & Clinics
      nwr["amenity"="pharmacy"](area.searchArea);
      nwr["amenity"="clinic"](area.searchArea);
      nwr["amenity"="doctors"](area.searchArea);
      // Markets
      nwr["amenity"="marketplace"](area.searchArea);
      nwr["shop"="market"](area.searchArea);
      // Schools (secondary level)
      nwr["amenity"="school"](area.searchArea);
      nwr["amenity"="kindergarten"](area.searchArea);
      // Gas Stations & Banks (daily utilities)
      nwr["amenity"="fuel"](area.searchArea);
      nwr["amenity"="bank"](area.searchArea);
      nwr["amenity"="atm"](area.searchArea);
    );
    out center tags;
    """


# ============================================================
# Category Classifier
# ============================================================

def classify_poi(tags: dict, layer: int) -> str:
    """Map OSM tags to human-readable category."""
    tag_to_category = {
        # Layer 1
        "shop:mall": "ห้างสรรพสินค้า",
        "shop:department_store": "ห้างสรรพสินค้า",
        "amenity:hospital": "โรงพยาบาล",
        "aeroway:aerodrome": "สนามบิน",
        "aeroway:terminal": "สนามบิน",
        "railway:station": "สถานีรถไฟ",
        "amenity:bus_station": "สถานีขนส่ง",
        "amenity:university": "มหาวิทยาลัย",
        "amenity:college": "วิทยาลัย",
        "building:government": "หน่วยงานรัฐ",
        "office:government": "หน่วยงานรัฐ",
        # Layer 2
        "tourism:attraction": "สถานที่ท่องเที่ยว",
        "historic:monument": "อนุสาวรีย์/อนุสรณ์",
        "historic:memorial": "อนุสาวรีย์/อนุสรณ์",
        "historic:city_gate": "ประตูเมือง",
        "historic:castle": "โบราณสถาน",
        "historic:ruins": "โบราณสถาน",
        "leisure:park": "สวนสาธารณะ",
        "leisure:stadium": "สนามกีฬา",
        "amenity:place_of_worship": "วัด/ศาสนสถาน",
        # Layer 3
        "shop:convenience": "ร้านสะดวกซื้อ",
        "shop:supermarket": "ซูเปอร์มาร์เก็ต",
        "amenity:pharmacy": "ร้านขายยา",
        "amenity:clinic": "คลินิก",
        "amenity:doctors": "คลินิก",
        "amenity:marketplace": "ตลาด",
        "shop:market": "ตลาด",
        "amenity:school": "โรงเรียน",
        "amenity:kindergarten": "โรงเรียนอนุบาล",
        "amenity:fuel": "ปั๊มน้ำมัน",
        "amenity:bank": "ธนาคาร",
        "amenity:atm": "ตู้ATM",
    }

    for tag_key, category in tag_to_category.items():
        k, v = tag_key.split(":", 1)
        if tags.get(k) == v:
            return category

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
    {"name": "พิษณุโลก",        "slug": "phitsanulok",         "relation_id": 18928096},
    {"name": "เชียงราย",        "slug": "chiang-rai",          "relation_id": 19051912},
]

LAYER_BUILDERS = [
    (1, "Primary",   build_layer1_query),
    (2, "Iconic",    build_layer2_query),
    (3, "Secondary", build_layer3_query),
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

            query   = query_builder(area_id)
            elements = run_overpass_query(query)
            count   = 0

            for el in elements:
                tags = el.get("tags", {})
                lat, lon = get_coords(el)
                if lat is None:
                    continue

                name    = tags.get("name", tags.get("name:th", tags.get("name:en", "")))
                name_en = tags.get("name:en", "")

                # Skip unnamed POIs only for Layer 3
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
            time.sleep(1.5)  # Polite delay between Overpass requests

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
