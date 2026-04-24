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


def analyze_zones(landmarks_raw_path, output_path, radius_km=2.0,
                  landmarks_clean_path=None, property_trends_path=None):
    """
    สร้าง Zone Profile โดยใช้ Layer 1 POIs เป็นจุดศูนย์กลาง
    และวิเคราะห์ POI รอบๆ ในรัศมีที่กำหนด

    landmarks_raw_path    — ไฟล์ดิบสำหรับ Search Pool (POI รอบๆ)
    landmarks_clean_path  — ไฟล์ที่ผ่านการ Dedup แล้ว สำหรับ Layer 1 Anchors
    property_trends_path  — CSV ราคาอสังหาฯ (Baania + LivingInsider merged)
    """
    print(f"\n{'='*55}")
    print(f"Zone Analyzer — Radius: {radius_km} km")
    print(f"{'='*55}")

    # --- โหลด Property Trends (ราคาอสังหาฯ) ---
    # trends_index[(province_en, property_type)] = median_price
    trends_index = {}
    if property_trends_path and os.path.exists(property_trends_path):
        trends_df = pd.read_csv(property_trends_path, encoding="utf-8-sig")
        for _, r in trends_df.iterrows():
            key = (str(r["province"]).strip(), str(r["property_type"]).strip())
            trends_index[key] = float(r["median_price"])
        print(f"  [OK] Property Trends loaded: {len(trends_index)} records")
    else:
        print(f"  [WARN] No property trends file -- price fields will be empty")

    # Province Thai → English mapping (for trends lookup)
    PROVINCE_EN = {
        "ขอนแก่น": "Khon Kaen", "อุบลราชธานี": "Ubon Ratchathani",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan", "อุดรธานี": "Udon Thani",
        "ระยอง": "Rayong", "ชลบุรี": "Chonburi", "สุรินทร์": "Surin",
        "บุรีรัมย์": "Buriram", "พิษณุโลก": "Phitsanulok", "เชียงราย": "Chiang Rai",
    }

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

        # =========================================================
        # Livability Score — Weighted & Capped
        # =========================================================
        # Layer 2 (จุดอัตลักษณ์): ให้คะแนนสูง เพราะสะท้อน "ชื่อเสียง" ของย่าน
        score_iconic = len(nearby_iconic) * 5

        # --- Layer 3 (สิ่งอำนวยความสะดวก) แยกตามหมวดหมู่ใหม่ ---

        # 1. ซื้อของ / ตลาด
        s_convenience = min(nearby_daily.get("ร้านสะดวกซื้อ", 0), 5) * 2          # 7-11, CJ max 5 แห่ง
        s_hypermarket = min(nearby_daily.get("ไฮเปอร์มาร์เก็ต", 0), 2) * 8       # Lotus/BigC — bonus สูง
        s_supermarket = min(nearby_daily.get("ซูเปอร์มาร์เก็ต", 0), 3) * 3       # ร้านทั่วไป
        s_market      = min(nearby_daily.get("ตลาด", 0), 3) * 4                   # ตลาดสด

        # 2. สุขภาพ
        s_hospital    = min(nearby_daily.get("โรงพยาบาล", 0), 2) * 8             # รพ. ใกล้ = คะแนนสูงมาก
        s_clinic      = min(nearby_daily.get("คลินิก", 0) +
                           nearby_daily.get("ศูนย์การแพทย์", 0), 4) * 3
        s_pharmacy    = min(nearby_daily.get("ร้านขายยา", 0), 4) * 2

        # 3. การศึกษา
        s_education   = min(nearby_daily.get("โรงเรียน", 0) +
                           nearby_daily.get("โรงเรียนอนุบาล", 0), 3) * 4

        # 4. บริการทางการเงิน + พลังงาน
        s_finance     = min(nearby_daily.get("ธนาคาร", 0) +
                           nearby_daily.get("ตู้ATM", 0), 6) * 1
        s_gas         = min(nearby_daily.get("ปั๊มน้ำมัน", 0), 3) * 2

        # 5. สันทนาการ (Layer 3 ที่หลุดมาจาก Layer 2)
        s_lifestyle   = (min(nearby_daily.get("สวนสาธารณะ", 0), 2) * 4 +
                        min(nearby_daily.get("บึง/ทะเลสาบ", 0), 1) * 5)

        livability_score = (
            score_iconic +
            s_convenience + s_hypermarket + s_supermarket + s_market +
            s_hospital + s_clinic + s_pharmacy +
            s_education + s_finance + s_gas + s_lifestyle
        )

        # --- ราคาอสังหาฯ จาก Trends ---
        prov_en = PROVINCE_EN.get(a_province, a_province)
        median_house   = trends_index.get((prov_en, "House"), 0)
        median_condo   = trends_index.get((prov_en, "Condo"), 0)
        median_townhse = trends_index.get((prov_en, "Townhouse"), 0)

        # Price Tier: ใช้ House เป็น baseline (ถ้าไม่มีให้ใช้ Condo)
        ref_price = median_house or median_condo or 0
        if ref_price >= 5_000_000:
            price_tier = "Premium"
        elif ref_price >= 2_500_000:
            price_tier = "Mid-Range"
        elif ref_price > 0:
            price_tier = "Budget"
        else:
            price_tier = "N/A"

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
            # Layer 3 Summary (รายหมวดหมู่)
            "hypermarkets":         nearby_daily.get("ไฮเปอร์มาร์เก็ต", 0),
            "convenience_stores":   nearby_daily.get("ร้านสะดวกซื้อ", 0),
            "markets":              nearby_daily.get("ตลาด", 0),
            "hospitals":            nearby_daily.get("โรงพยาบาล", 0),
            "clinics":              nearby_daily.get("คลินิก", 0),
            "pharmacies":           nearby_daily.get("ร้านขายยา", 0),
            "schools":              nearby_daily.get("โรงเรียน", 0),
            "banks":                nearby_daily.get("ธนาคาร", 0),
            "gas_stations":         nearby_daily.get("ปั๊มน้ำมัน", 0),
            "daily_life_summary":   daily_text,
            # Total stats & final score
            "total_layer2_nearby":  len(nearby_iconic),
            "total_layer3_nearby":  sum(nearby_daily.values()),
            "livability_score":     round(livability_score, 2),
            # Property Trends (Baania + LivingInsider merged)
            "median_house_price":   int(median_house)   if median_house   else "",
            "median_condo_price":   int(median_condo)   if median_condo   else "",
            "median_townhse_price": int(median_townhse) if median_townhse else "",
            "price_tier":           price_tier,
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
