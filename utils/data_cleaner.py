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
    """
    Merges and cleans property trend data from multiple sources.
    """
    all_dfs = []
    
    # Load DotProperty
    if os.path.exists(dotproperty_raw):
        with open(dotproperty_raw, 'r', encoding='utf-8') as f:
            all_dfs.append(pd.DataFrame(json.load(f)))
            
    # Load LivingInsider
    if os.path.exists(livinginsider_raw):
        with open(livinginsider_raw, 'r', encoding='utf-8') as f:
            all_dfs.append(pd.DataFrame(json.load(f)))
            
    if not all_dfs:
        print("Error: No raw property data found to clean.")
        return

    # Merge all sources
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Standardizing province names (English)
    province_mapping = {
        "ขอนแก่น": "Khon Kaen",
        "อุบลราชธานี": "Ubon Ratchathani",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
        "อุดรธานี": "Udon Thani",
        "ระยอง": "Rayong",
        "ชลบุรี": "Chonburi",
        "สุรินทร์": "Surin",
        "บุรีรัมย์": "Buriram",
        "พิษณุโลก": "Phitsanulok",
        "เชียงราย": "Chiang Rai"
    }
    
    if 'province' in df.columns:
        df['province_en'] = df['province'].map(province_mapping).fillna(df['province_en'] if 'province_en' in df.columns else df['province'])
    
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')
    print(f"Merged and cleaned property data saved to {processed_file_path}")

def clean_landmarks(raw_file_path, processed_file_path):
    """
    Cleans and standardizes POI/Landmarks data.
    - Smart Dedup: ชื่อคล้ายกัน + อยู่ใกล้กันไม่เกิน 300 เมตร = ซ้ำ
    - Standardizes province names
    - Sorts by province → layer → category
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
    
    # ========== Phase 1: Exact Dedup (เร็ว) ==========
    df = df.drop_duplicates(subset=['name', 'lat', 'lon'], keep='first')
    exact_removed = before_total - len(df)
    
    # ========== Phase 2: Smart Fuzzy Dedup (ชื่อคล้าย + ใกล้กัน) ==========
    def _haversine_m(lat1, lon1, lat2, lon2):
        R = 6371000  # เมตร
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    def _normalize_name(name: str) -> str:
        """ทำให้ชื่อเรียบง่ายเพื่อเปรียบเทียบ"""
        if not name:
            return ""
        n = str(name).strip().lower()
        # ลบคำที่ไม่สำคัญออก
        for noise in ["สาขา", "branch", "(", ")", "-", "–", ".", ","]:
            n = n.replace(noise, " ")
        # ลบช่องว่างซ้ำ
        n = " ".join(n.split())
        return n

    def _name_is_similar(name_a: str, name_b: str) -> bool:
        """เช็คว่าชื่อสถานที่คล้ายกันหรือไม่"""
        a = _normalize_name(name_a)
        b = _normalize_name(name_b)
        if not a or not b:
            return False
        # ชื่อเหมือนกันเป๊ะ
        if a == b:
            return True
        # ชื่อหนึ่งเป็น substring ของอีกชื่อ
        if a in b or b in a:
            return True
        # แยกเป็นคำแล้วดูว่ามีคำร่วมกันกี่คำ (Jaccard-like)
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return False
        common = words_a & words_b
        union = words_a | words_b
        similarity = len(common) / len(union)
        return similarity >= 0.5  # ร่วมกัน >= 50% ของคำทั้งหมด

    # แบ่งตามจังหวัด+หมวดหมู่ เพื่อลดเวลาเปรียบเทียบ (ไม่ต้องเทียบข้ามจังหวัด)
    fuzzy_removed = 0
    drop_indices = set()
    
    for (province, category), group in df.groupby(['province', 'category']):
        indices = group.index.tolist()
        for i in range(len(indices)):
            if indices[i] in drop_indices:
                continue
            row_a = df.loc[indices[i]]
            for j in range(i + 1, len(indices)):
                if indices[j] in drop_indices:
                    continue
                row_b = df.loc[indices[j]]
                
                # เช็คระยะทาง (ถ้าไกลกว่า 300 เมตร ข้ามไป)
                dist = _haversine_m(row_a['lat'], row_a['lon'],
                                    row_b['lat'], row_b['lon'])
                if dist > 300:
                    continue
                
                # เช็คชื่อ
                if _name_is_similar(row_a['name'], row_b['name']):
                    # เก็บตัวที่มีข้อมูลเยอะกว่า (prefer OSM > Google Maps)
                    if row_b.get('source', '') == 'Google Maps' and row_a.get('source', '') != 'Google Maps':
                        drop_indices.add(indices[j])
                    elif row_a.get('source', '') == 'Google Maps' and row_b.get('source', '') != 'Google Maps':
                        drop_indices.add(indices[i])
                        break
                    else:
                        drop_indices.add(indices[j])  # เก็บตัวแรก
    
    df = df.drop(index=drop_indices)
    fuzzy_removed = len(drop_indices)
    
    # ========== Phase 3: Remove unnamed POIs ==========
    df = df[df['name'].astype(str).str.strip() != '']
    
    # ========== Summary ==========
    total_removed = before_total - len(df)
    print(f"  Dedup Summary:")
    print(f"    Exact match removed:  {exact_removed}")
    print(f"    Fuzzy match removed:  {fuzzy_removed}")
    print(f"    Total removed:        {total_removed} (from {before_total} → {len(df)})")
    
    # Standardize province names (English)
    province_mapping = {
        "ขอนแก่น": "Khon Kaen",
        "อุบลราชธานี": "Ubon Ratchathani",
        "ประจวบคีรีขันธ์": "Prachuap Khiri Khan",
        "อุดรธานี": "Udon Thani",
        "ระยอง": "Rayong",
        "ชลบุรี": "Chonburi",
        "สุรินทร์": "Surin",
        "บุรีรัมย์": "Buriram",
        "พิษณุโลก": "Phitsanulok",
        "เชียงราย": "Chiang Rai"
    }
    if 'province' in df.columns:
        df['province_en'] = df['province'].map(province_mapping).fillna(df.get('province_en', df['province']))
    
    # Sort for readability
    df = df.sort_values(['province', 'layer', 'category', 'name']).reset_index(drop=True)
    
    # Select and order columns for output
    output_cols = [
        'province', 'province_en', 'name', 'name_en',
        'category', 'layer', 'layer_name',
        'lat', 'lon', 'source'
    ]
    df = df[[c for c in output_cols if c in df.columns]]
    
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8-sig')
    
    # Print summary
    print(f"  Landmarks summary:")
    for layer in sorted(df['layer'].unique()):
        count = len(df[df['layer'] == layer])
        name = df[df['layer'] == layer]['layer_name'].iloc[0] if 'layer_name' in df.columns else f"Layer {layer}"
        print(f"    Layer {layer} ({name}): {count} POIs")
    print(f"  Total: {len(df)} POIs saved to {processed_file_path}")


if __name__ == "__main__":
    pass
