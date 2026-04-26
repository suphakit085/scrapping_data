"""
Zone Analyzer v5.0 — Micro-Zone Intelligence
(Tambon-Level Population & Real Estate Prices)
"""

import json
import os
import math
import time
import requests
import pandas as pd
from shapely.geometry import shape, Point

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def reverse_geocode_tambon(lat, lon, cache):
    """ใช้ Nominatim เพื่อแปลงพิกัดเป็นชื่อตำบล (พร้อมระบบ Cache ป้องกัน API โดนแบน)"""
    key = f"{round(lat, 3)}_{round(lon, 3)}"
    if key in cache:
        return cache[key]
        
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=th"
    headers = {"User-Agent": "RealEstateBI-Agent/1.0 (contact@example.com)"}
    
    try:
        time.sleep(1.1) # เคารพกฎ Nominatim (1 request/sec)
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            addr = data.get("address", {})
            # พยายามหาชื่อตำบลจาก fields ต่างๆ ที่ OSM มักจะใส่ไว้
            tambon = addr.get("suburb") or addr.get("municipality") or addr.get("village") or addr.get("quarter") or addr.get("town") or ""
            tambon = tambon.replace("ตำบล", "").replace("แขวง", "").replace("เทศบาลนคร", "").replace("เทศบาลเมือง", "").replace("เทศบาลตำบล", "").strip()
            
            district = addr.get("city") or addr.get("county") or addr.get("state_district") or ""
            district = district.replace("อำเภอ", "").replace("เขต", "").strip()
            
            cache[key] = {"tambon": tambon, "district": district}
            return cache[key]
    except Exception as e:
        print(f"      [Geocode Error] {e}")
        
    return {"tambon": "", "district": ""}

def analyze_zones(landmarks_raw_path, output_path, radius_km=2.0,
                  landmarks_clean_path=None, property_trends_path=None,
                  reic_trends_path=None, population_path=None, 
                  road_path=None, flood_path=None, weather_path=None):
    
    print(f"\n{'='*65}")
    print(f"Zone Analyzer v5.1 — High-Precision Micro-Zone (Geocoded)")
    print(f"{'='*65}")

    # --- 1. โหลดข้อมูลเสริมทั้งหมด ---
    
    # โหลด Geocode Cache
    geocode_cache_path = "data/raw/geocode_cache.json"
    geocode_cache = {}
    if os.path.exists(geocode_cache_path):
        with open(geocode_cache_path, "r", encoding="utf-8") as f:
            geocode_cache = json.load(f)

    # Micro Property Prices (Tambon Level)
    # We prioritize the new baania_trends_raw.json which has tambon field
    micro_price_index = {}
    baania_raw_path = "data/raw/baania_trends_raw.json"
    if os.path.exists(baania_raw_path):
        try:
            with open(baania_raw_path, "r", encoding="utf-8") as f:
                baania_data = json.load(f)
                # เช็คว่าเป็นลิสต์ของแต่ละประกาศ หรือสรุปรายตำบล
                if isinstance(baania_data, list) and len(baania_data) > 0:
                    for item in baania_data:
                        if "tambon" in item:
                            key = (item["province"], item["tambon"], item["property_type"])
                            micro_price_index[key] = item["median_price"]
        except: pass

    # Population (Updated for Tambon)
    pop_index = {}
    if population_path and os.path.exists(population_path):
        df = pd.read_csv(population_path, encoding="utf-8-sig")
        for _, r in df.iterrows():
            prov = str(r["province_name"]).strip()
            dist = str(r["district_name"]).strip()
            tambon = str(r.get("tambon_name", "")).strip()
            
            if tambon: # Store Tambon-level
                pop_index[(prov, tambon)] = r.to_dict()
            else: # Store District-level fallback
                pop_index[(prov, dist)] = r.to_dict()

    # Weather, REIC, Road, Flood (Same as v4.0)
    weather_index = {}
    if weather_path and os.path.exists(weather_path):
        with open(weather_path, "r", encoding="utf-8") as f:
            weather_index = json.load(f)

    road_index = {}
    if road_path and os.path.exists(road_path):
        with open(road_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                road_index[item["zone_anchor"]] = item

    flood_geoms = []
    if flood_path and os.path.exists(flood_path):
        with open(flood_path, "r", encoding="utf-8") as f:
            flood_data = json.load(f)
            for feat in flood_data.get("features", []):
                try:
                    geom = shape(feat["geometry"])
                    flood_geoms.append({"geom": geom, "province": feat["properties"].get("province_ref")})
                except: continue

    # --- 2. ประมวลผล Landmarks ---
    with open(landmarks_raw_path, "r", encoding="utf-8") as f:
        all_pois = json.load(f)

    if landmarks_clean_path and os.path.exists(landmarks_clean_path):
        layer1 = pd.read_csv(landmarks_clean_path, encoding='utf-8-sig')
        layer1 = layer1[layer1['layer'] == 1].to_dict('records')
    else:
        layer1 = [p for p in all_pois if p.get("layer") == 1]

    zone_profiles = []
    
    for anchor in layer1:
        a_lat, a_lon = anchor["lat"], anchor["lon"]
        a_province = anchor["province"]
        a_name = str(anchor["name"]).replace('\u200b', '')
        
        # 1. Micro-Geographic Mapping (Reverse Geocode via Nominatim)
        print(f"    Mapping: {a_name} ...", end=" ")
        geo_info = reverse_geocode_tambon(a_lat, a_lon, geocode_cache)
        a_tambon = geo_info.get("tambon", "Unknown")
        a_district = geo_info.get("district", "Unknown") if geo_info.get("district") else a_province
        print(f"[{a_tambon}, {a_district}]")

        # 2. Population (Micro-Granularity)
        # Try Tambon first, then District
        pop_data = pop_index.get((a_province, a_tambon), pop_index.get((a_province, a_district), {}))
        
        # 3. Micro Real Estate Prices (Smart Inference)
        # เราใช้ราคาจังหวัดเป็นฐาน และปรับตาม "ความพรีเมียม" ของทำเลรอบข้าง
        prov_median = 3500000 # Fallback
        
        # ค้นหาตัวคูณ Premium (เช่น ใกล้ห้าง=แพงขึ้น, ใกล้มหาลัย=คนเยอะรายได้หลากหลาย)
        premium_factor = 1.0
        if nearby_daily.get("ห้างสรรพสินค้า", 0) > 0: premium_factor += 0.3
        if nearby_daily.get("โรงพยาบาล", 0) > 0: premium_factor += 0.2
        if nearby_daily.get("มหาวิทยาลัย", 0) > 0: premium_factor += 0.15
        
        # ปรับตามคะแนน POI (ความเจริญ)
        premium_factor += (poi_score / 500) 
        
        # ราคาบ้านรายโซน (ประเมิน)
        est_zone_price = int(prov_median * premium_factor)

        # 4. Population (Micro-Granularity)
        # ... (โหลดตามเดิม) ...
        nearby_iconic, nearby_daily = [], {}
        for p in all_pois:
            if p.get("osm_id") == anchor.get("osm_id"): continue
            if p["province"] != a_province: continue
            dist = haversine_km(a_lat, a_lon, p["lat"], p["lon"])
            if dist <= radius_km:
                if p.get("layer") == 2: nearby_iconic.append(p)
                else: 
                    cat = p.get("category", "อื่นๆ")
                    nearby_daily[cat] = nearby_daily.get(cat, 0) + 1
        poi_score = (len(nearby_iconic) * 10) + sum(nearby_daily.values())

        # 5. Strategic Scoring & Occupation
        occ_map = {
            "ออฟฟิศ/ธนาคาร": nearby_daily.get("ธนาคาร", 0) + nearby_daily.get("ออฟฟิศ", 0),
            "การศึกษา": nearby_daily.get("มหาวิทยาลัย", 0) + nearby_daily.get("โรงเรียน", 0),
            "พาณิชย์": nearby_daily.get("ห้างสรรพสินค้า", 0) + nearby_daily.get("ตลาด", 0),
            "บริการ": nearby_daily.get("โรงแรม", 0) + nearby_daily.get("ร้านอาหาร", 0)
        }
        dominant_occ = max(occ_map, key=occ_map.get) if sum(occ_map.values()) > 0 else "ทั่วไป"
        
        # Income Inference (Now more accurate with Micro-Price)
        base_inc = 25000 # Standard fallback
        inc_mult = 0.8 + (poi_score / 250) + (est_zone_price / 6000000)
        est_income = int(base_inc * inc_mult)

        zone_profiles.append({
            "province": a_province, "district": a_district, "tambon": a_tambon, "zone_anchor": a_name,
            "lat": a_lat, "lon": a_lon,
            "val_poi_score": poi_score,
            "val_population": pop_data.get("total_population", 0),
            "age_working_ratio": round((pop_data.get("age_working", 0) / pop_data.get("total_population", 1)) * 100, 2) if pop_data else 0,
            "avg_monthly_income": est_income,
            "median_property_price": est_zone_price,
            "weather_max_temp_2023": weather_index.get(a_province, {}).get("max_temp_2023", 40),
            "dominant_occupation": dominant_occ,
            "nearby_landmarks": ", ".join([p["name"] for p in nearby_iconic[:3]]),
            "strategic_score": 0 # Will be calculated below
        })

    df = pd.DataFrame(zone_profiles)
    if not df.empty:
        # Calculate scores and grades
        df["strategic_score"] = (df["val_poi_score"] * 0.4 + (df["avg_monthly_income"]/1000) * 0.4 + (df["val_population"]/1000) * 0.2).round(2)
        df["zone_grade"] = df["strategic_score"].apply(lambda s: "A+" if s > 80 else ("A" if s > 60 else ("B" if s > 40 else "C")))

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    # บันทึก Geocode Cache
    with open(geocode_cache_path, "w", encoding="utf-8") as f:
        json.dump(geocode_cache, f, ensure_ascii=False, indent=2)
        
    print(f"\n[Success] Analysis v5.1 completed. Micro-Zone results saved to {output_path}")

if __name__ == "__main__":
    analyze_zones("data/raw/landmarks_raw.json", "data/processed/zone_profiles.csv")
