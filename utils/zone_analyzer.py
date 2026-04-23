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


def analyze_zones(landmarks_raw_path, output_path, radius_km=2.0):
    """
    สร้าง Zone Profile โดยใช้ Layer 1 POIs เป็นจุดศูนย์กลาง
    และวิเคราะห์ POI รอบๆ ในรัศมีที่กำหนด
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

    # แยก POI ตาม Layer
    layer1 = [p for p in all_pois if p.get("layer") == 1 and p.get("lat")]
    layer2 = [p for p in all_pois if p.get("layer") == 2 and p.get("lat")]
    layer3 = [p for p in all_pois if p.get("layer") == 3 and p.get("lat")]

    print(f"  Layer 1 (Zone Anchors): {len(layer1)}")
    print(f"  Layer 2 (Iconic):       {len(layer2)}")
    print(f"  Layer 3 (Daily life):   {len(layer3)}")

    zone_profiles = []

    for anchor in layer1:
        a_lat = anchor["lat"]
        a_lon = anchor["lon"]
        a_province = anchor["province"]

        # --- หา POI ใกล้เคียงจาก Layer 2 ---
        nearby_iconic = []
        for poi in layer2:
            if poi["province"] != a_province:
                continue
            dist = haversine_km(a_lat, a_lon, poi["lat"], poi["lon"])
            if dist <= radius_km:
                nearby_iconic.append({
                    "name": poi["name"],
                    "category": poi["category"],
                    "distance_km": round(dist, 2)
                })

        # --- หา POI ใกล้เคียงจาก Layer 3 (นับจำนวนตามประเภท) ---
        nearby_daily = {}
        for poi in layer3:
            if poi["province"] != a_province:
                continue
            dist = haversine_km(a_lat, a_lon, poi["lat"], poi["lon"])
            if dist <= radius_km:
                cat = poi["category"]
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
            # Total score (simple density metric)
            "total_layer2_nearby":  len(nearby_iconic),
            "total_layer3_nearby":  sum(nearby_daily.values()),
            "livability_score":     len(nearby_iconic) + sum(nearby_daily.values()),
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
            print(f"    📍 {row['zone_anchor']} ({row['anchor_category']})")
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
