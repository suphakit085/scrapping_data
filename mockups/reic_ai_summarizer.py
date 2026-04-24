import pandas as pd
import os
import random

def generate_mock_reic_data():
    provinces = [
        "ขอนแก่น", "อุบลราชธานี", "ประจวบคีรีขันธ์", "อุดรธานี", 
        "ระยอง", "ชลบุรี", "สุรินทร์", "บุรีรัมย์", "พิษณุโลก", "เชียงราย"
    ]
    
    data_list = []
    
    for prov in provinces:
        # สุ่มข้อมูลให้ดูสมจริงตามสภาพเศรษฐกิจแต่ละที่
        house_rem = random.randint(1500, 5000)
        condo_rem = random.randint(500, 3000)
        
        # สุ่ม Absorption Rate (ระยอง ชลบุรี อาจจะสูงกว่าที่อื่น)
        base_rate = 2.5 if prov in ["ชลบุรี", "ระยอง"] else 1.5
        abs_house = round(base_rate + random.uniform(0.5, 2.0), 1)
        abs_condo = round(base_rate + random.uniform(-0.5, 1.5), 1)
        
        sentiment = round(45.0 + random.uniform(0, 15.0), 1)
        
        analysis = "ตลาดมีความต้องการต่อเนื่อง" if abs_house > 3.0 else "ควรระวังการระบายสต็อกเก่า"
        if sentiment < 50:
            analysis += " | ผู้ประกอบการเริ่มชะลอตัว"
            
        data_list.append({
            "report_source": "REIC Summary Q1/2026",
            "province": prov,
            "district": "เมือง",
            "remaining_units_total": house_rem + condo_rem,
            "house_remaining": house_rem,
            "condo_remaining": condo_rem,
            "absorption_rate_house": abs_house,
            "absorption_rate_condo": abs_condo,
            "new_launch_growth_pct": round(random.uniform(-5.0, 15.0), 1),
            "sentiment_index": sentiment,
            "market_analysis": analysis,
            "last_updated": "2026-04-24"
        })
    
    return data_list

def save_to_csv(data, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"DONE: Mocked 10 provinces to {output_path}")

if __name__ == "__main__":
    mock_data = generate_mock_reic_data()
    save_to_csv(mock_data, "data/processed/reic_trends.csv")
    
    # โชว์ตัวอย่างให้ดู 3 แถว
    df = pd.DataFrame(mock_data)
    print("\n--- Preview REIC Trends Mockup (10 Provinces) ---")
    print(df[['province', 'absorption_rate_house', 'sentiment_index', 'market_analysis']].head(10).to_string(index=False))
