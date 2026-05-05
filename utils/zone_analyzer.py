# -*- coding: utf-8 -*-
"""
Zone Analyzer v5.0 — Micro-Zone Intelligence
(Tambon-Level Population & Real Estate Prices)
"""

import sys
import json
import os
import math
import time
import requests
import pandas as pd
from shapely.geometry import shape, Point

# Enforce UTF-8 for terminal output (fixes Mojibake on Windows CMD)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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
            # ระบบแกะชื่อแบบ Multi-layer (ป้องกันเคสในมหาลัย หรือพื้นที่กว้าง)
            tambon = (addr.get("suburb") or 
                      addr.get("neighbourhood") or 
                      addr.get("municipality") or 
                      addr.get("village") or 
                      addr.get("town") or 
                      addr.get("city_district") or "")
            
            tambon = tambon.replace("ตำบล", "").replace("แขวง", "").replace("เทศบาลนคร", "").replace("เทศบาลเมือง", "").replace("เทศบาลตำบล", "").strip()
            
            # ถ้ายังว่าง ให้ลองแกะจากชื่อเขต (County/District)
            district = addr.get("city") or addr.get("county") or addr.get("state_district") or ""
            district = district.replace("อำเภอ", "").replace("เขต", "").strip()
            
            # ป้องกันชื่อซ้ำกันระหว่างตำบลกับอำเภอ
            if tambon == district:
                tambon = addr.get("suburb") or addr.get("neighbourhood") or "ในเมือง"
            
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
    print(f"Zone Analyzer v5.2 — High-Precision Micro-Zone (Geocoded)")
    print(f"{'='*65}")

    # --- 1. โหลดข้อมูลเสริมทั้งหมด ---
    
    # โหลด Geocode Cache
    geocode_cache_path = "data/raw/geocode_cache.json"
    geocode_cache = {}
    if os.path.exists(geocode_cache_path):
        with open(geocode_cache_path, "r", encoding="utf-8") as f:
            geocode_cache = json.load(f)

    # โหลด Road Data (เสาหลักที่ 2)
    road_data = []
    if road_path and os.path.exists(road_path):
        with open(road_path, "r", encoding="utf-8") as f:
            road_data = json.load(f)

    # โหลด Flood Data (GeoJSON Parsing with Shapely)
    flood_geoms = []
    if flood_path and os.path.exists(flood_path):
        with open(flood_path, "r", encoding="utf-8") as f:
            fd = json.load(f)
            for feat in fd.get("features", []):
                try:
                    geom = shape(feat["geometry"])
                    flood_geoms.append({
                        "geom": geom, 
                        "risk": feat.get("properties", {}).get("risk", "High")
                    })
                except Exception:
                    pass


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

    # Weather Data
    weather_index = {}
    if weather_path and os.path.exists(weather_path):
        with open(weather_path, "r", encoding="utf-8") as f:
            weather_index = json.load(f)

    # --- 2. ประมวลผล Landmarks ---
    with open(landmarks_raw_path, "r", encoding="utf-8") as f:
        all_pois = json.load(f)

    layer1 = [p for p in all_pois if p.get("layer") == 1]
    zone_profiles = []
    
    for anchor in layer1:
        try:
            a_lat, a_lon = anchor["lat"], anchor["lon"]
            a_province = anchor["province"]
            a_name = str(anchor["name"]).replace('\u200b', '')
            
            # 1. Micro-Geographic Mapping (Reverse Geocode via Nominatim)
            print(f"    Mapping: {a_name} ...", end=" ", flush=True)
            geo_info = reverse_geocode_tambon(a_lat, a_lon, geocode_cache)
            a_tambon = geo_info.get("tambon", "Unknown")
            a_district = geo_info.get("district", "Unknown") if geo_info.get("district") else a_province
            print(f"[{a_tambon}, {a_district}]")

            # Pillar 1: Landmark (Structured & Layered)
            layer1_count, layer2_count, layer3_count = 0, 0, 0
            amenity_summary = {}
            nearby_names = [] 

            for p in all_pois:
                if p.get("osm_id") == anchor.get("osm_id"): continue
                if p["province"] != a_province: continue
                
                dist = haversine_km(a_lat, a_lon, p["lat"], p["lon"])
                if dist <= radius_km:
                    layer = p.get("layer", 3)
                    cat = p.get("category", "อื่นๆ")
                    
                    if layer == 1: 
                        layer1_count += 1
                        nearby_names.append(p.get("name", ""))
                    elif layer == 2: 
                        layer2_count += 1
                        nearby_names.append(p.get("name", ""))
                    else: 
                        layer3_count += 1
                        
                    amenity_summary[cat] = amenity_summary.get(cat, 0) + 1
            
            nearby_names = [n for n in nearby_names if n][:5]
            poi_score = (layer1_count * 50) + (layer2_count * 10) + sum(amenity_summary.values())

            # Pillar 2: Road (Connectivity)
            road_score = 0
            if road_data:
                for road in road_data:
                    if road.get("zone_anchor") == a_name or (road.get("lat") == a_lat and road.get("lon") == a_lon):
                        road_score = road.get("road_complexity_score", 0)
                        break

            # Pillar 3: Area Status (Weather & Flood)
            weather = weather_index.get(a_province, {})
            flood_risk = "Low"
            flood_penalty = 0
            
            # Correct GeoJSON point-in-polygon logic
            if flood_geoms:
                p_zone = Point(a_lon, a_lat)
                for fg in flood_geoms:
                    if fg["geom"].contains(p_zone) or fg["geom"].distance(p_zone) < 0.015: # approx 1.5km
                        risk_level = fg.get("risk", "Medium")
                        if risk_level == "High":
                            flood_risk = "High"
                            flood_penalty = -15
                            break
                        else:
                            flood_risk = "Medium"
                            flood_penalty = -5

            # Pillar 4: Population (Density & Income)
            pop_data = pop_index.get((a_province, a_tambon), pop_index.get((a_province, a_district), {}))
            
            base_inc = 25000 
            est_income = int(base_inc * (0.8 + (poi_score / 300) + (road_score / 15)))

            occ_map = {
                "ออฟฟิศ/ธุรกิจ": amenity_summary.get("ธนาคาร", 0) + amenity_summary.get("ออฟฟิศ", 0),
                "การศึกษา/วิชาการ": amenity_summary.get("มหาวิทยาลัย", 0) + amenity_summary.get("โรงเรียน", 0),
                "ค้าขาย/บริการ": amenity_summary.get("ห้างสรรพสินค้า", 0) + amenity_summary.get("ร้านอาหาร", 0) + amenity_summary.get("ตลาด", 0)
            }
            dominant_occ = max(occ_map, key=occ_map.get) if sum(occ_map.values()) > 0 else "ทั่วไป/รับจ้าง"

            zone_profiles.append({
                "province": a_province, 
                "district": a_district, 
                "tambon": a_tambon, 
                "zone_name": a_name,
                "lat": a_lat, "lon": a_lon,
                # --- PILLAR 1: LANDMARK ---
                "landmark_total_score": poi_score,
                "landmark_layer1_count": layer1_count,
                "landmark_layer2_count": layer2_count,
                "landmark_layer3_count": layer3_count,
                "landmark_nearby_names": ", ".join(nearby_names),
                "landmark_amenity_json": json.dumps(amenity_summary, ensure_ascii=False),
                # --- PILLAR 2: ROAD ---
                "road_connectivity_index": road_score,
                # --- PILLAR 3: AREA STATUS ---
                "area_weather_max_temp": weather.get("max_temp_2023", 40),
                "area_flood_risk_level": flood_risk,
                "area_flood_penalty_score": flood_penalty,
                # --- PILLAR 4: POPULATION ---
                "pop_total_density": pop_data.get("total_population", 0),
                "pop_working_age_ratio": round((pop_data.get("age_working", 0) / pop_data.get("total_population", 1)) * 100, 2) if pop_data else 0,
                "pop_estimated_monthly_income": est_income,
                "pop_dominant_occupation": dominant_occ
            })
        except Exception as e:
            print(f"      [Skip Item] Error analyzing {anchor.get('name')}: {e}")
            import traceback
            traceback.print_exc()
            continue

    df = pd.DataFrame(zone_profiles)
    
    # คำนวณ Strategic Score และ Zone Grade (ปรับจูนความแม่นยำใหม่)
    if not df.empty:
        # สมการถ่วงน้ำหนักใหม่: สมดุลทั้ง 4 เสาหลัก ไม่ให้คอลัมน์ไหนดึงคะแนนเวอร์เกินไป
        # 1. Landmark: ความเจริญ (Max Contribution ~40-60)
        # 2. Road: การคมนาคม (Max Contribution ~30-50)
        # 3. Income: กำลังซื้อ (Max Contribution ~30-50)
        # 4. Pop Density: ขนาดตลาด (Max Contribution ~10-20)
        # 5. Flood Penalty: หักลบความเสี่ยง
        
        df["strategic_score"] = (
            (df["landmark_total_score"] * 0.3) + 
            (df["road_connectivity_index"] * 0.5) + 
            (df["pop_estimated_monthly_income"] / 1000 * 1.2) +
            (df["pop_total_density"] / 1000 * 1.0) +
            df["area_flood_penalty_score"]
        ).round(2)
        
        # จัดเกรดทำเลศักยภาพ (คะแนนเต็มประมาณ 150-200)
        df["zone_grade"] = df["strategic_score"].apply(
            lambda s: "A+" if s >= 120 else ("A" if s >= 85 else ("B" if s >= 50 else "C"))
        )

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    
    # บันทึก Geocode Cache
    with open(geocode_cache_path, "w", encoding="utf-8") as f:
        json.dump(geocode_cache, f, ensure_ascii=False, indent=2)
        
    print(f"\n[Success] Green-Frame Analysis completed. Output: {output_path}")

if __name__ == "__main__":
    analyze_zones("data/raw/landmarks_raw.json", "data/processed/zone_profiles.csv")
