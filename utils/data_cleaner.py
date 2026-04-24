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

def clean_property_trends(dotproperty_raw, livinginsider_raw, processed_file_path):
    """Merges and cleans property trend data from multiple sources."""
    all_dfs = []
    
    if os.path.exists(dotproperty_raw):
        with open(dotproperty_raw, 'r', encoding='utf-8') as f:
            all_dfs.append(pd.DataFrame(json.load(f)))
            
    if os.path.exists(livinginsider_raw):
        with open(livinginsider_raw, 'r', encoding='utf-8') as f:
            all_dfs.append(pd.DataFrame(json.load(f)))
            
    if not all_dfs:
        print("Error: No raw property data found to clean.")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    
    province_mapping = {
        "ขอนแก่น": "Khon Kaen", "อุบลราชธานี": "Ubon Ratchathani",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan", "อุดรธานี": "Udon Thani",
        "ระยอง": "Rayong", "ชลบุรี": "Chonburi", "สุรินทร์": "Surin",
        "บุรีรัมย์": "Buriram", "พิษณุโลก": "Phitsanulok", "เชียงราย": "Chiang Rai"
    }
    
    if 'province' in df.columns:
        df['province_en'] = df['province'].map(province_mapping).fillna(
            df['province_en'] if 'province_en' in df.columns else df['province'])
    
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')
    print(f"Merged and cleaned property data saved to {processed_file_path}")


def clean_landmarks(raw_file_path, processed_file_path):
    """
    Cleans and standardizes POI/Landmarks data.
    - Phase 1:   Exact Dedup (name + lat + lon)
    - Phase 1.5: Anchor Dedup Layer 1 รัศมี 500 เมตร (ป้องกัน node/way/relation ซ้ำ)
    - Phase 2:   Fuzzy Dedup รัศมี 300 เมตร (ชื่อคล้ายกัน ข้ามแหล่ง OSM/Google)
    - Phase 3:   ลบ POI ที่ไม่มีชื่อ
    """
    import math

    if not os.path.exists(raw_file_path):
        print(f"Error: Raw file {raw_file_path} not found.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not data:
        print("Warning: No landmarks data to clean.")
        return

    df = pd.DataFrame(data)
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
        return " ".join(n.split())

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

    # ========== Phase 1: Exact Dedup ==========
    df = df.drop_duplicates(subset=['name', 'lat', 'lon'], keep='first')
    exact_removed = before_total - len(df)

    # ========== Phase 1.5: Anchor Dedup (Layer 1, รัศมี 500m) ==========
    # ห้างสรรพสินค้า/โรงพยาบาลขนาดใหญ่มักถูกบันทึกใน OSM เป็น node+way+relation
    # ใช้รัศมี 500m เพราะพิกัดอาจต่างกันถึง 200-400m ในสถานที่ขนาดใหญ่
    anchor_drop = set()
    layer1_df = df[df['layer'] == 1].copy()
    for _, group in layer1_df.groupby(['province', 'category']):
        anchor_drop |= _dedup_group(group, radius_m=500, prefer_osm=False)
    df = df.drop(index=anchor_drop)
    anchor_removed = len(anchor_drop)

    # ========== Phase 2: Fuzzy Dedup (All Layers, รัศมี 300m) ==========
    # ป้องกัน OSM กับ Google Maps บันทึกสถานที่เดียวกันซ้ำ
    fuzzy_drop = set()
    for _, group in df.groupby(['province', 'category']):
        fuzzy_drop |= _dedup_group(group, radius_m=300, prefer_osm=True)
    df = df.drop(index=fuzzy_drop)
    fuzzy_removed = len(fuzzy_drop)

    # ========== Phase 3: Remove unnamed ==========
    df = df[df['name'].astype(str).str.strip() != '']

    # ========== Summary ==========
    total_removed = before_total - len(df)
    print(f"  Dedup Summary:")
    print(f"    Exact match removed:        {exact_removed}")
    print(f"    Anchor (Layer1) removed:    {anchor_removed}")
    print(f"    Fuzzy match removed:        {fuzzy_removed}")
    print(f"    Total removed:              {total_removed} ({before_total} -> {len(df)})")

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

    output_cols = ['province', 'province_en', 'name', 'name_en',
                   'category', 'layer', 'layer_name', 'lat', 'lon', 'source']
    df = df[[c for c in output_cols if c in df.columns]]

    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')

    print(f"  Landmarks summary:")
    for layer in sorted(df['layer'].unique()):
        count = len(df[df['layer'] == layer])
        lname = (df[df['layer'] == layer]['layer_name'].iloc[0]
                 if 'layer_name' in df.columns else f"Layer {layer}")
        print(f"    Layer {layer} ({lname}): {count} POIs")
    print(f"  Total: {len(df)} POIs saved to {processed_file_path}")


if __name__ == "__main__":
    pass
