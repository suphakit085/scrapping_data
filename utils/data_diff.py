import math
import re
import os
import json

def haversine_distance_m(lat1, lon1, lat2, lon2):
    """คำนวณระยะทางระหว่างพิกัดสองจุด (เมตร)"""
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))

def normalize_poi_name(name):
    if not name:
        return ""
    n = str(name).strip().lower()
    # Normalize common province space variations
    n = n.replace("khon kaen", "khonkaen")
    n = n.replace("chon buri", "chonburi")
    n = n.replace("buri ram", "buriram")
    n = n.replace("prachuap khiri khan", "prachuapkhirikhan")
    n = n.replace("udon thani", "udonthani")
    n = n.replace("ubon ratchathani", "ubonratchathani")
    n = n.replace("chiang rai", "chiangrai")
    for noise in ["สาขา", "branch", "(", ")", "-", "–", ".", ","]:
        n = n.replace(noise, " ")
    return " ".join(n.split())

def name_is_similar(name_a, name_b):
    a = normalize_poi_name(name_a)
    b = normalize_poi_name(name_b)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return False
    # ตรวจสอบสัดส่วนคำที่ซ้ำกัน (Jaccard Similarity >= 0.5)
    return len(words_a & words_b) / len(words_a | words_b) >= 0.5

def find_new_and_merge(existing_list, new_scraped_list, category_radius_mapping=None):
    """
    เปรียบเทียบข้อมูลเดิมและข้อมูลที่ได้มาใหม่
    - คืนค่า (merged_list, new_pois_found)
    """
    if existing_list is None:
        existing_list = []
    if new_scraped_list is None:
        new_scraped_list = []
        
    if category_radius_mapping is None:
        category_radius_mapping = {
            "โรงเรียน": 400, "มหาวิทยาลัย": 400, "วิทยาลัย": 400, 
            "สวนสาธารณะ": 400, "บึง/ทะเลสาบ": 400, "สนามกีฬา": 400,
            "สนามบิน": 400, "โรงพยาบาล": 400
        }
        
    merged = list(existing_list)
    new_found = []
    
    # จัดกลุ่มข้อมูลเดิมตามจังหวัดเพื่อความเร็วในการค้นหาแบบทวีคูณ
    existing_by_province = {}
    for poi in existing_list:
        prov = str(poi.get("province", "unknown")).strip()
        existing_by_province.setdefault(prov, []).append(poi)
        
    for new_poi in new_scraped_list:
        lat = new_poi.get("lat")
        lon = new_poi.get("lon")
        name = new_poi.get("name", "")
        prov = str(new_poi.get("province", "unknown")).strip()
        
        if lat is None or lon is None or not name:
            continue
            
        # ตรวจสอบกับสถานที่ที่มีอยู่แล้วในจังหวัดนั้นๆ
        is_existing = False
        candidates = existing_by_province.get(prov, [])
        
        # ค้นหาระยะทางและชื่อที่คล้ายกัน
        for est in candidates:
            cat = est.get("category", "")
            radius = category_radius_mapping.get(cat, 150) # รัศมีเริ่มต้น 150 เมตร
            
            # ถ้าระยะทางใกล้กันและชื่อคล้ายกัน ให้ถือเป็นที่เดียวกัน
            if haversine_distance_m(lat, lon, est.get("lat"), est.get("lon")) <= radius:
                if name_is_similar(name, est.get("name", "")):
                    is_existing = True
                    break
                    
        if not is_existing:
            new_found.append(new_poi)
            merged.append(new_poi)
            # เพิ่มลงกลุ่มสำหรับการเปรียบเทียบคู่ถัดไปในลูป
            existing_by_province.setdefault(prov, []).append(new_poi)
            
    return merged, new_found
