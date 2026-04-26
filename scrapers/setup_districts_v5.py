import requests
import json
import os
import time

def fetch_district_centroids():
    """
    ดึงพิกัดจุดศูนย์กลาง (Centroid) ของแต่ละอำเภอ 
    วิธีนี้เร็วกว่าการดึง Polygon มาก และเพียงพอต่อการทำ Spatial Matching
    """
    provinces = ["ขอนแก่น", "อุบลราชธานี", "ระยอง", "ชลบุรี", "เชียงราย", 
                 "อุดรธานี", "ประจวบคีรีขันธ์", "สุรินทร์", "บุรีรัมย์", "พิษณุโลก"]
    
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    all_districts = []

    print(f"--- Fetching District Centroids (High Speed Mode) ---")

    for prov in provinces:
        print(f"  Fetching districts for {prov}...", end=" ", flush=True)
        
        # Query: หา node ที่เป็นจุดศูนย์กลางอำเภอ (admin_level=6)
        query = f"""
        [out:json][timeout:30];
        area["name"="{prov}"]["admin_level"="4"]->.a;
        node["admin_level"="6"](area.a);
        out body;
        """
        
        try:
            response = requests.get(OVERPASS_URL, params={'data': query}, headers=headers, timeout=45)
            if response.status_code == 200:
                data = response.json()
                nodes = data.get('elements', [])
                
                for n in nodes:
                    n['province_ref'] = prov
                    all_districts.append(n)
                
                print(f"Done! ({len(nodes)} districts)")
            else:
                print(f"Failed (Status {response.status_code})")
            
            time.sleep(1)
        except Exception as e:
            print(f"Error: {e}")

    if all_districts:
        output_path = "data/raw/district_centroids.json"
        os.makedirs("data/raw", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_districts, f, ensure_ascii=False, indent=2)
        print(f"\n[Success] Saved {len(all_districts)} district centroids to {output_path}")

if __name__ == "__main__":
    fetch_district_centroids()
