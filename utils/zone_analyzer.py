"""
Zone Analyzer — สร้างโปรไฟล์โซนจากข้อมูล Landmarks
ใช้ Layer 1 POIs เป็นจุดศูนย์กลาง แล้ววิเคราะห์ว่ารอบๆ มีอะไรบ้าง
เพื่อประเมินมูลค่าทำเลอสังหาริมทรัพย์
"""

import json
import os
import math
import pandas as pd


def haversine_km(lat1, lon1, lat2, lon2):
    """คำนวณระยะทางระหว่างจุดสองจุดบนโลก (กม.)"""
    R = 6371  # รัศมีโลก (กม.)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def analyze_zones(landmarks_raw_path, output_path, radius_km=2.0, landmarks_clean_path=None):
    """
    สร้าง Zone Profile โดยใช้ Layer 1 POIs เป็นจุดศูนย์กลาง
    และวิเคราะห์ POI รอบๆ ในรัศมีที่กำหนด

    landmarks_raw_path   — ไฟล์ดิบสำหรับ Search Pool (POI รอบๆ)
    landmarks_clean_path — ไฟล์ที่ผ่านการ Dedup แล้ว สำหรับ Layer 1 Anchors
                           ถ้าไม่ระบุจะใช้ไฟล์ดิบแทน (เหมือนเดิม)
    """
    print(f"\n{'='*55}")
    print(f"Zone Analyzer — Radius: {radius_km} km")
    print(f"{'='*55}")

    if not os.path.exists(landmarks_raw_path):
        print(f"Error: {landmarks_raw_path} not found.")
        return

    with open(landmarks_raw_path, "r", encoding="utf-8") as f:
        all_pois = json.load(f)

    if not all_pois:
        print("No landmarks data to analyze.")
        return

    # --- โหลด Anchors จากไฟล์ Clean (ถ้ามี) เพื่อป้องกัน Anchor ซ้ำ ---
    if landmarks_clean_path and os.path.exists(landmarks_clean_path):
        import pandas as pd
        clean_df = pd.read_csv(landmarks_clean_path, encoding='utf-8-sig')
        layer1 = clean_df[clean_df['layer'] == 1].to_dict('records')
        print(f"  [OK] Using deduplicated anchors from: {landmarks_clean_path}")
    else:
        layer1 = [p for p in all_pois if p.get("layer") == 1 and p.get("lat")]
        print(f"  [WARN] No clean file -- using raw Layer 1 (may have duplicates)")

    # Search pool ยังคงใช้ไฟล์ดิบเพื่อให้ได้ POI รอบๆ ครบที่สุด
    search_pool = [p for p in all_pois if p.get("lat")]

    print(f"  Zone Anchors (Layer 1): {len(layer1)}")
    print(f"  Total POIs for search:  {len(search_pool)}")

    zone_profiles = []

    for anchor in layer1:
        a_lat = anchor["lat"]
        a_lon = anchor["lon"]
        a_province = anchor["province"]
        a_id = anchor.get("osm_id")

        # --- หา POI ใกล้เคียง ---
        nearby_iconic = []
        nearby_daily = {}
        
        for poi in search_pool:
            # ข้ามถ้าเป็นตัวมันเอง
            if poi.get("osm_id") == a_id and poi["name"] == anchor["name"]:
                continue
            if poi["province"] != a_province:
                continue
                
            dist = haversine_km(a_lat, a_lon, poi["lat"], poi["lon"])
            if dist <= radius_km:
                layer = poi.get("layer")
                cat = poi.get("category", "อื่นๆ")
                
                if layer == 2:
                    nearby_iconic.append({
                        "name": poi["name"],
                        "category": cat,
                        "distance_km": round(dist, 2)
                    })
                else:
                    # รวม Layer 1 อื่นๆ (เช่น รพ. ใกล้ห้าง) และ Layer 3 เข้าด้วยกัน
                    nearby_daily[cat] = nearby_daily.get(cat, 0) + 1

        # --- สร้าง Zone Profile ---
        # สรุป Layer 2 เป็นข้อความ
        iconic_text = "; ".join(
            [f"{p['name']} ({p['category']}, {p['distance_km']}km)"
             for p in sorted(nearby_iconic, key=lambda x: x["distance_km"])[:10]]
        ) or "ไม่มี"

        # สรุป Layer 3 เป็นข้อความ
        daily_text = "; ".join(
            [f"{cat} {count} แห่ง" for cat, count in
             sorted(nearby_daily.items(), key=lambda x: -x[1])]
        ) or "ไม่มี"

        # --- คำนวณ Livability Score แบบ Weighted & Capped ---
        # 1. Iconic Points (Layer 2): ให้ค่าความสำคัญสูง
        score_iconic = len(nearby_iconic) * 5

        # 2. Daily Life (Layer 3): ถ่วงน้ำหนักตามประเภทและจำกัดจำนวน (Capping)
        # ความสะดวกสบาย: ร้านสะดวกซื้อ (max 5 แห่ง), ตลาด (max 2 แห่ง)
        s_convenience = min(nearby_daily.get("ร้านสะดวกซื้อ", 0), 5) * 2
        s_market = min(nearby_daily.get("ตลาด", 0), 2) * 5
        
        # สุขภาพและอาชีพ: คลินิก/โรงพยาบาล (max 3), ร้านขายยา (max 3), โรงเรียน (max 2)
        s_health = min(nearby_daily.get("คลินิก", 0) + nearby_daily.get("โรงพยาบาล", 0), 3) * 5
        s_pharmacy = min(nearby_daily.get("ร้านขายยา", 0), 3) * 2
        s_education = min(nearby_daily.get("โรงเรียน", 0) + nearby_daily.get("โรงเรียนอนุบาล", 0), 2) * 5
        
        # บริการอื่นๆ: ธนาคาร/ATM (max 5), ปั๊มน้ำมัน (max 2)
        s_finance = min(nearby_daily.get("ธนาคาร", 0) + nearby_daily.get("ตู้ATM", 0), 5) * 1
        s_gas = min(nearby_daily.get("ปั๊มน้ำมัน", 0), 2) * 2
        
        # ไลฟ์สไตล์: สวนสาธารณะ, ห้างสรรพสินค้า/ซูเปอร์มาร์เก็ต (max 2)
        s_lifestyle = (min(nearby_daily.get("สวนสาธารณะ", 0), 2) * 4 + 
                       min(nearby_daily.get("ซูเปอร์มาร์เก็ต", 0) + nearby_daily.get("ห้างสรรพสินค้า", 0), 2) * 4)

        livability_score = (score_iconic + s_convenience + s_market + s_health + 
                           s_pharmacy + s_education + s_finance + s_gas + s_lifestyle)

        zone_profiles.append({
            "province":         a_province,
            "zone_anchor":      anchor["name"],
            "anchor_category":  anchor["category"],
            "lat":              a_lat,
            "lon":              a_lon,
            "radius_km":        radius_km,
            # Layer 2 Summary
            "nearby_iconic_count":  len(nearby_iconic),
            "nearby_iconic_list":   iconic_text,
            # Layer 3 Summary
            "convenience_stores":   nearby_daily.get("ร้านสะดวกซื้อ", 0),
            "markets":              nearby_daily.get("ตลาด", 0),
            "pharmacies":           nearby_daily.get("ร้านขายยา", 0),
            "clinics":              nearby_daily.get("คลินิก", 0),
            "schools":              nearby_daily.get("โรงเรียน", 0),
            "banks":                nearby_daily.get("ธนาคาร", 0),
            "gas_stations":         nearby_daily.get("ปั๊มน้ำมัน", 0),
            "daily_life_summary":   daily_text,
            # Total stats & final score
            "total_layer2_nearby":  len(nearby_iconic),
            "total_layer3_nearby":  sum(nearby_daily.values()),
            "livability_score":     round(livability_score, 2),
        })

    # Save CSV
    df = pd.DataFrame(zone_profiles)
    df = df.sort_values(["province", "livability_score"], ascending=[True, False])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    # Print Summary
    print(f"\n--- Zone Profiles ---")
    for province in df["province"].unique():
        subset = df[df["province"] == province]
        print(f"\n  [{province}]")
        for _, row in subset.head(5).iterrows():
            print(f"    >> {row['zone_anchor']} ({row['anchor_category']})")
            print(f"       Iconic nearby: {row['nearby_iconic_count']} | "
                  f"Daily-life: {row['total_layer3_nearby']} | "
                  f"Score: {row['livability_score']}")

    print(f"\n{'='*55}")
    print(f"Saved {len(zone_profiles)} zone profiles to {output_path}")
    print(f"{'='*55}")


if __name__ == "__main__":
    analyze_zones("../data/raw/landmarks_raw.json",
                  "../data/processed/zone_profiles.csv",
                  radius_km=2.0)
