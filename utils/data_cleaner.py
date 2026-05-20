import pandas as pd
import json
import os

def clean_bank_loans(raw_file_path, processed_file_path):
    if not os.path.exists(raw_file_path):
        print(f"Error: Raw file {raw_file_path} not found.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')
    print(f"Cleaned bank data saved to {processed_file_path}")

def clean_landmarks(raw_file_paths, processed_file_path, restaurants_output_path=None):
    """
    Cleans and standardizes POI/Landmarks data.
    - Phase 1:   Exact Dedup (name + lat + lon)
    - Phase 1.5: Anchor Dedup Layer 1 รัศมี 500 เมตร (ป้องกัน node/way/relation ซ้ำ)
    - Phase 2:   Fuzzy Dedup รัศมี 300 เมตร (ชื่อคล้ายกัน ข้ามแหล่ง OSM/Google)
    - Phase 3:   ลบ POI ที่ไม่มีชื่อ
    """
    import math

    if isinstance(raw_file_paths, str):
        raw_file_paths = [raw_file_paths]

    all_data = []
    for path in raw_file_paths:
        if not os.path.exists(path):
            print(f"Warning: Raw file {path} not found. Skipping.")
            continue
        with open(path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if data:
                    all_data.extend(data)
            except json.JSONDecodeError:
                print(f"Warning: Error decoding JSON from {path}")

    if not all_data:
        print("Warning: No landmarks data to clean.")
        return

    df = pd.DataFrame(all_data)
    before_total = len(df)

    # ========== Helper Functions (ใช้ร่วมกันทุก Phase) ==========
    def _haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    def _normalize_name(name):
        if not name:
            return ""
        n = str(name).strip().lower()
        for noise in ["สาขา", "branch", "(", ")", "-", "–", ".", ","]:
            n = n.replace(noise, " ")
            
        # ตัดคำทั่วไปออกเพื่อเน้นเทียบชื่อเฉพาะ
        words = n.split()
        stop_words = {"ร้านอาหาร", "ร้าน", "คาเฟ่", "cafe", "restaurant", "food", "court"}
        words = [w for w in words if w not in stop_words]
        
        return " ".join(words)

    def _name_is_similar(name_a, name_b):
        a = _normalize_name(name_a)
        b = _normalize_name(name_b)
        if not a or not b:
            return False
        if a == b or a in b or b in a:
            return True
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        return len(words_a & words_b) / len(words_a | words_b) >= 0.5

    def _dedup_group(group_df, radius_m, prefer_osm=True):
        """Generic dedup loop — คืน set ของ index ที่ควรลบ"""
        drop = set()
        indices = group_df.index.tolist()
        for i in range(len(indices)):
            if indices[i] in drop:
                continue
            ra = group_df.loc[indices[i]]
            for j in range(i + 1, len(indices)):
                if indices[j] in drop:
                    continue
                rb = group_df.loc[indices[j]]
                if _haversine_m(ra['lat'], ra['lon'], rb['lat'], rb['lon']) > radius_m:
                    continue
                if _name_is_similar(ra['name'], rb['name']):
                    if prefer_osm:
                        src_a = ra.get('source', '')
                        src_b = rb.get('source', '')
                        if src_b == 'Google Maps' and src_a != 'Google Maps':
                            drop.add(indices[j])
                        elif src_a == 'Google Maps' and src_b != 'Google Maps':
                            drop.add(indices[i]); break
                        else:
                            drop.add(indices[j])
                    else:
                        # Layer 1: เก็บตัวที่ layer ต่ำกว่า (สำคัญกว่า)
                        if ra.get('layer', 1) <= rb.get('layer', 1):
                            drop.add(indices[j])
                        else:
                            drop.add(indices[i]); break
        return drop

    def _dedup_by_layer(df_to_clean):
        """แยก Dedup ตาม Layer เพราะความหนาแน่นต่างกัน"""
        to_drop = set()
        
        # แบ่งกลุ่มตาม Layer
        for layer_val in [1, 2, 3]:
            layer_df = df_to_clean[df_to_clean['layer'] == layer_val]
            if layer_df.empty: continue
            
            for keys, group in layer_df.groupby(['province', 'category']):
                category_name = keys[1]
                large_area_categories = ["โรงเรียน", "มหาวิทยาลัย", "วิทยาลัย", "สวนสาธารณะ", "บึง/ทะเลสาบ", "สนามกีฬา", "สนามบิน", "โรงพยาบาล"]
                
                # กำหนดรัศมีพิเศษสำหรับสถานที่ที่มีพื้นที่กว้าง (400m)
                if category_name in large_area_categories:
                    radius = 400
                elif layer_val == 1:
                    radius = 300
                elif layer_val == 2:
                    radius = 100
                else:
                    # Layer 3 ร้านอาหาร/สะดวกซื้อ ลดรัศมีเหลือ 40m เพื่อป้องกันการลบร้านใกล้เคียง
                    radius = 40

                to_drop |= _dedup_group(group, radius_m=radius, prefer_osm=(layer_val != 1))
        
        return to_drop

    # ========== Phase 1: Exact Dedup ==========
    df = df.drop_duplicates(subset=['name', 'lat', 'lon'], keep='first')
    exact_removed = before_total - len(df)

    # ========== Phase 2: Layer-Aware Dedup ==========
    # แทนที่ Phase 1.5 และ 2 เดิมด้วยระบบใหม่ที่แยกความละเอียดตาม Layer
    removed_indices = _dedup_by_layer(df)
    df = df.drop(index=removed_indices)
    fuzzy_removed = len(removed_indices)

    # ========== Phase 3: Remove unnamed ==========
    df = df[df['name'].astype(str).str.strip() != '']

    # ========== Phase 4: Keyword Blacklisting ==========
    blacklist_words = ["บ้านฉัน", "test", "ทดสอบ", "ปิดแล้ว", "เจ๊ง", "dummy", "ปิดกิจการ", "ปิดถาวร", "closed", "ย้ายร้าน", "permanently closed"]
    
    def is_garbage(name):
        n = str(name).lower()
        if len(n) < 2:
            return True
        for bw in blacklist_words:
            if bw in n:
                return True
        return False
        
    garbage_mask = df['name'].apply(is_garbage)
    garbage_removed = garbage_mask.sum()
    df = df[~garbage_mask]

    # ========== Summary ==========
    total_removed = before_total - len(df)
    print(f"  Dedup Summary (Layer-Aware):")
    print(f"    Exact match removed: {exact_removed}")
    print(f"    Fuzzy/Proximity removed: {fuzzy_removed}")
    print(f"    Garbage keywords removed: {garbage_removed}")
    print(f"    Total removed: {total_removed} ({before_total} -> {len(df)})")

    # Standardize province names
    province_mapping = {
        "ขอนแก่น": "Khon Kaen", "อุบลราชธานี": "Ubon Ratchathani",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan", "อุดรธานี": "Udon Thani",
        "ระยอง": "Rayong", "ชลบุรี": "Chonburi", "สุรินทร์": "Surin",
        "บุรีรัมย์": "Buriram", "พิษณุโลก": "Phitsanulok", "เชียงราย": "Chiang Rai"
    }
    if 'province' in df.columns:
        df['province_en'] = df['province'].map(province_mapping).fillna(
            df.get('province_en', df['province']))

    df = df.sort_values(['province', 'layer', 'category', 'name']).reset_index(drop=True)

    output_cols = [
        'province', 'province_en', 'district', 'sub_district',
        'name', 'name_en', 'category', 'layer', 'layer_name',
        'lat', 'lon', 'source',
        'osm_timestamp', 'osm_last_edit_year_ce', 'osm_last_edit_year_be',
        'osm_created_year_ce', 'osm_created_year_be', 'osm_version',
        'gmaps_last_review_year_ce', 'gmaps_last_review_year_be',
    ]
    df = df[[c for c in output_cols if c in df.columns]]

    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')

    if restaurants_output_path:
        restaurants_df = df[df['category'] == 'ร้านอาหาร']
        os.makedirs(os.path.dirname(restaurants_output_path), exist_ok=True)
        restaurants_df.to_csv(restaurants_output_path, index=False, encoding='utf-8-sig')
        print(f"  Restaurants subset saved to: {restaurants_output_path} ({len(restaurants_df)} POIs)")

    print(f"  Landmarks summary:")
    for layer in sorted(df['layer'].unique()):
        count = len(df[df['layer'] == layer])
        lname = (df[df['layer'] == layer]['layer_name'].iloc[0]
                 if 'layer_name' in df.columns else f"Layer {layer}")
        print(f"    Layer {layer} ({lname}): {count} POIs")
    print(f"  Total: {len(df)} POIs saved to {processed_file_path}")


if __name__ == "__main__":
    pass
