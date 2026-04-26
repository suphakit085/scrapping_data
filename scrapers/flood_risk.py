import os
import requests
import json
import time
from dotenv import load_dotenv

load_dotenv()

GISTDA_API_KEY = os.getenv("GISTDA_API_KEY")
BASE_URL = "https://api-gateway.gistda.or.th/api/2.0/resources" 

# พิกัด Bounding Box ของ 10 จังหวัดเป้าหมาย
PROVINCE_BBOX = {
    "ขอนแก่น": [101.75, 15.65, 103.10, 17.10],
    "อุบลราชธานี": [104.30, 14.20, 105.65, 16.05],
    "ชลบุรี": [100.80, 12.50, 101.60, 13.60],
    "เชียงราย": [99.25, 19.00, 100.60, 20.50],
    "ระยอง": [101.00, 12.50, 101.90, 13.20],
    "อุดรธานี": [102.00, 16.80, 103.50, 18.10],
    "ประจวบคีรีขันธ์": [99.00, 10.90, 100.10, 12.80],
    "สุรินทร์": [103.00, 14.30, 104.10, 15.50],
    "บุรีรัมย์": [102.50, 14.20, 103.60, 15.60],
    "พิษณุโลก": [99.90, 16.30, 101.10, 17.70]
}

def get_grid_bboxes(bbox, step=0.1): # ลดขนาดตารางลงครึ่งหนึ่ง
    """แบ่ง Bbox ใหญ่เป็น Bbox ย่อยๆ (ขนาดประมาณ 10x10 กม.)"""
    min_x, min_y, max_x, max_y = bbox
    grids = []
    curr_x = min_x
    while curr_x < max_x:
        curr_y = min_y
        while curr_y < max_y:
            next_x = min(curr_x + step, max_x)
            next_y = min(curr_y + step, max_y)
            grids.append([curr_x, curr_y, next_x, next_y])
            curr_y += step
        curr_x += step
    return grids

def fetch_flood_risk_resilient():
    if not GISTDA_API_KEY:
        print("[Error] GISTDA_API_KEY not found in .env")
        return

    headers = {"API-Key": GISTDA_API_KEY, "Accept": "application/json"}
    all_flood_features = []

    print(f"--- Fetching Flood Frequency (Resilient Grid Mode) ---")

    for prov_name, bbox in PROVINCE_BBOX.items():
        print(f"\nProcessing {prov_name}...")
        grids = get_grid_bboxes(bbox)
        print(f"  Divided into {len(grids)} tiny chunks.")
        
        prov_features = 0
        for i, grid in enumerate(grids):
            bbox_str = ",".join(map(str, grid))
            params = {"bbox": bbox_str, "limit": 200}
            
            try:
                response = requests.get(f"{BASE_URL}/features/flood-freq", params=params, headers=headers, timeout=60)
                if response.status_code == 200:
                    features = response.json().get("features", [])
                    for f in features:
                        f["properties"]["province_ref"] = prov_name
                        all_flood_features.append(f)
                    prov_features += len(features)
                    print(".", end="", flush=True)
                else:
                    print(f"[{response.status_code}]", end="", flush=True)
            except Exception as e:
                print("!", end="", flush=True)
            
            time.sleep(1.0) # เว้นระยะ 1 วินาทีให้เซิร์ฟเวอร์พัก
            
        print(f" Done! Found {prov_features} hotspots in {prov_name}.")

    if all_flood_features:
        output_path = "data/raw/flood_risk_raw.json"
        os.makedirs("data/raw", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"type": "FeatureCollection", "features": all_flood_features}, f, ensure_ascii=False, indent=2)
        print(f"\n[Success] Saved {len(all_flood_features)} flood hotspots to {output_path}")

if __name__ == "__main__":
    fetch_flood_risk_resilient()
