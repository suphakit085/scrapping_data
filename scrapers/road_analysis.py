import requests
import json
import os
import time
import pandas as pd

def fetch_road_network(landmarks_path, output_path, radius_km=2.0):
    """
    ดึงข้อมูลโครงข่ายถนนรอบๆ Anchor ของแต่ละโซน โดยอ้างอิงจาก Landmarks Raw (Layer 1)
    """
    if not os.path.exists(landmarks_path):
        print(f"[Error] {landmarks_path} not found.")
        return

    with open(landmarks_path, "r", encoding="utf-8") as f:
        all_landmarks = json.load(f)
    
    # กรองเฉพาะ Layer 1 (Anchor หลักของโซน)
    layer1 = [l for l in all_landmarks if l.get("layer") == 1]
    
    print(f"--- Fetching Road Connectivity Data (OSM) ---")
    
    # โหลดข้อมูลเดิมถ้ามี เพื่อรันต่อ (Resume)
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                road_data = json.load(f)
            done_anchors = {item['zone_anchor'] for item in road_data}
            print(f"  Resuming from existing file. {len(done_anchors)} zones already processed.")
        except:
            road_data = []
            done_anchors = set()
    else:
        road_data = []
        done_anchors = set()

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"
    headers = {
        "User-Agent": "RealEstateBIProject/1.0 (contact: researcher@example.com)",
        "Accept-Language": "en"
    }

    for item in layer1:
        name = str(item.get('name', 'Unknown')).replace('\u200b', '').strip()
        if name in done_anchors:
            continue
            
        lat, lon = item['lat'], item['lon']
        print(f"  Analyzing roads for: {name}...", end=" ", flush=True)

        query = f"""
        [out:json][timeout:30];
        (
          way["highway"](around:{radius_km * 1000},{lat},{lon});
        );
        out body;
        >;
        out skel qt;
        """
        
        try:
            response = requests.get(OVERPASS_URL, params={'data': query}, headers=headers, timeout=45)
            if response.status_code == 200:
                data = response.json()
                elements = data.get('elements', [])
                
                highways = [e for e in elements if e.get('type') == 'way']
                primary_roads = [h for h in highways if h.get('tags', {}).get('highway') in ['primary', 'secondary', 'trunk']]
                node_count = len([e for e in elements if e.get('type') == 'node'])
                
                road_data.append({
                    "zone_anchor": name,
                    "lat": lat, "lon": lon,
                    "total_road_segments": len(highways),
                    "primary_road_count": len(primary_roads),
                    "road_node_density": node_count,
                    "road_complexity_score": round((len(highways) * 2) + (len(primary_roads) * 5), 2)
                })
                print(f"Done! ({len(highways)} segments)")
                
                if len(road_data) % 10 == 0:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(road_data, f, ensure_ascii=False, indent=2)
            else:
                print(f"Failed (Status {response.status_code})")
            
            time.sleep(1.2)
        except Exception as e:
            print(f"Error: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(road_data, f, ensure_ascii=False, indent=2)
    print(f"\n[Success] Road network data saved to {output_path}")

if __name__ == "__main__":
    fetch_road_network("data/raw/landmarks_raw.json", "data/raw/road_network.json")
