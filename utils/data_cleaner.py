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
    - Removes duplicates (same name + same lat/lon)
    - Standardizes province names
    - Sorts by province → layer → category
    """
    if not os.path.exists(raw_file_path):
        print(f"Error: Raw file {raw_file_path} not found.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data:
        print("Warning: No landmarks data to clean.")
        return

    df = pd.DataFrame(data)
    
    # Remove exact duplicates (same name + coordinates)
    before = len(df)
    df = df.drop_duplicates(subset=['name', 'lat', 'lon'], keep='first')
    removed = before - len(df)
    if removed:
        print(f"  Removed {removed} duplicate POIs.")
    
    # Remove unnamed POIs (keep only those with names)
    df = df[df['name'].astype(str).str.strip() != '']
    
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
