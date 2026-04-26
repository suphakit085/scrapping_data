import requests
import json
import os
import time

def setup_tambon_coordinates():
    print("--- Generating Tambon (Sub-district) Coordinate Lookup (Resilient) ---")
    
    provinces = [
        "Khon Kaen", "Ubon Ratchathani", "Chon Buri", "Rayong", "Udon Thani", 
        "Chiang Rai", "Phitsanulok", "Prachuap Khiri Khan", "Surin", "Buri Ram"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    lookup_results = []
    overpass_url = "https://lz4.overpass-api.de/api/interpreter"
    
    for prov in provinces:
        print(f"  Fetching tambons for {prov}...")
        overpass_query = f"""
        [out:json][timeout:60];
        area["name:en"="{prov}"]["admin_level"="4"]->.a;
        (
          node["admin_level"="8"](area.a);
          way["admin_level"="8"](area.a);
          relation["admin_level"="8"](area.a);
        );
        out center;
        """
        
        try:
            response = requests.get(overpass_url, params={'data': overpass_query}, headers=headers, timeout=60)
            if response.status_code == 200:
                data = response.json()
                count = 0
                for element in data.get('elements', []):
                    tags = element.get('tags', {})
                    name_th = tags.get('name:th') or tags.get('name')
                    amphoe = tags.get('addr:amphoe') or tags.get('is_in:amphoe') or "Unknown"
                    if name_th:
                        lat = element.get('lat') or element.get('center', {}).get('lat')
                        lon = element.get('lon') or element.get('center', {}).get('lon')
                        if lat and lon:
                            lookup_results.append({
                                "province_en": prov,
                                "amphoe": amphoe.replace("อำเภอ", "").strip(),
                                "tambon": name_th.replace("ตำบล", "").strip(),
                                "lat": lat, "lon": lon
                            })
                            count += 1
                print(f"    -> Found {count} tambons.")
            else:
                print(f"    [Skip] Overpass unavailable for {prov} (Status {response.status_code})")
        except Exception as e:
            print(f"    [Skip] Error fetching {prov}: {e}")
        
        time.sleep(2)

    output_path = "data/raw/tambon_lookup.json"
    os.makedirs("data/raw", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(lookup_results, f, ensure_ascii=False, indent=2)
    print(f"\n[Finished] Tambon lookup table prepared.")

if __name__ == "__main__":
    setup_tambon_coordinates()
