import pandas as pd
import json
import os

def clean_bank_loans(raw_file_path, processed_file_path):
    """
    Cleans bank loan data.
    """
    if not os.path.exists(raw_file_path):
        print(f"Error: Raw file {raw_file_path} not found.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Basic cleaning (can be expanded later)
    # df['Interest_Rate'] = df['Interest_Rate'].astype(float) # Example conversion
    
    # Ensure processed directory exists
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    
    df.to_csv(processed_file_path, index=False, encoding='utf-8')
    print(f"Cleaned data saved to {processed_file_path}")

def clean_reic_trends(raw_file_path, processed_file_path):
    """
    Cleans REIC real estate trend data.
    """
    if not os.path.exists(raw_file_path):
        print(f"Error: Raw file {raw_file_path} not found.")
        return

    with open(raw_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    df = pd.DataFrame(data)
    
    # Basic cleaning (standardizing province names)
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
        df['province_en'] = df['province'].map(province_mapping).fillna(df['province'])
    
    os.makedirs(os.path.dirname(processed_file_path), exist_ok=True)
    df.to_csv(processed_file_path, index=False, encoding='utf-8')
    print(f"Cleaned data saved to {processed_file_path}")

if __name__ == "__main__":
    pass
