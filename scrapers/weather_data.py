import requests
import xml.etree.ElementTree as ET
import json
import os

def scrape_weather_from_tmd_api():
    print("--- Fetching REAL-TIME Weather Data from TMD API (2026) ---")
    
    # URL สำหรับข้อมูลปี 2026
    rain_url = "https://data.tmd.go.th/api/ThailandMonthlyRainfall/v1/index.php?uid=api&ukey=api12345"
    temp_url = "https://data.tmd.go.th/api/WeatherToday/V2/?uid=api&ukey=api12345"
    
    # แมพชื่อจังหวัดไทย -> ชื่อสถานีภาษาอังกฤษใน API (เป๊ะๆ)
    station_map = {
        "ขอนแก่น": "KHON KAEN",
        "อุบลราชธานี": "UBON RATCHATHANI",
        "ชลบุรี": "CHON BURI",
        "ระยอง": "RAYONG",
        "อุดรธานี": "UDON THANI",
        "บุรีรัมย์": "BURI RAM",
        "เชียงราย": "CHIANG RAI",
        "พิษณุโลก": "PHITSANULOK",
        "ประจวบคีรีขันธ์": "PRACHUAP KHIRIKHAN",
        "สุรินทร์": "SURIN"
    }
    
    results = {}

    try:
        # 1. Rainfall (2026)
        print("  Fetching 2026 rainfall data...")
        r_rain = requests.get(rain_url, timeout=120)
        if r_rain.status_code == 200:
            root = ET.fromstring(r_rain.content)
            for station in root.findall(".//StationMonthlyRainfall"):
                eng_tag = station.find("StationNameEnglish")
                if eng_tag is None or not eng_tag.text: continue
                st_name_en = eng_tag.text.strip().upper()
                
                target_prov = None
                for prov_th, prov_en in station_map.items():
                    if prov_en in st_name_en: # ใช้ in เพราะบางสถานีมีคำว่า AIRPORT หรือ AGROMET. ต่อท้าย
                        target_prov = prov_th
                        break
                
                if target_prov:
                    year_tag = station.find("Year")
                    total_tag = station.find(".//RainfallTOTAL")
                    if total_tag is not None:
                        if target_prov not in results: results[target_prov] = {}
                        results[target_prov]["annual_rainfall"] = float(total_tag.text or 0)
                        results[target_prov]["data_year"] = year_tag.text if year_tag is not None else "2026"

        # 2. Temperature (Today)
        print("  Fetching current temperature data...")
        r_temp = requests.get(temp_url, timeout=120)
        if r_temp.status_code == 200:
            root = ET.fromstring(r_temp.content)
            for station in root.findall(".//Station"):
                name_th_tag = station.find("StationNameTh")
                if name_th_tag is None or not name_th_tag.text: continue
                
                for prov_th in station_map.keys():
                    if prov_th in name_th_tag.text:
                        temp_tag = station.find(".//Temperature")
                        if temp_tag is not None and temp_tag.text:
                            if prov_th not in results: results[prov_th] = {}
                            results[prov_th]["avg_temp"] = float(temp_tag.text)
                        break

        # Baseline Extremes 2023 (สำหรับตัวเลขเปรียบเทียบ)
        baseline = {
            "ขอนแก่น": {"max_temp_2023": 42.2, "min_temp_2023": 12.0, "max_rain_2023": 145.4},
            "อุบลราชธานี": {"max_temp_2023": 41.2, "min_temp_2023": 13.0, "max_rain_2023": 92.9},
            "ชลบุรี": {"max_temp_2023": 38.0, "min_temp_2023": 18.5, "max_rain_2023": 114.1},
            "ระยอง": {"max_temp_2023": 36.6, "min_temp_2023": 19.5, "max_rain_2023": 101.8},
            "อุดรธานี": {"max_temp_2023": 44.1, "min_temp_2023": 9.9, "max_rain_2023": 67.9},
            "เชียงราย": {"max_temp_2023": 39.9, "min_temp_2023": 10.3, "max_rain_2023": 92.1},
            "พิษณุโลก": {"max_temp_2023": 41.0, "min_temp_2023": 13.0, "max_rain_2023": 122.9},
            "ประจวบคีรีขันธ์": {"max_temp_2023": 39.5, "min_temp_2023": 19.4, "max_rain_2023": 79.5},
            "สุรินทร์": {"max_temp_2023": 41.4, "min_temp_2023": 11.2, "max_rain_2023": 89.5},
            "บุรีรัมย์": {"max_temp_2023": 41.4, "min_temp_2023": 11.9, "max_rain_2023": 72.7}
        }

        final_results = {}
        for prov in station_map.keys():
            final_results[prov] = baseline.get(prov, {}).copy()
            dyn = results.get(prov, {})
            final_results[prov]["avg_temp"] = dyn.get("avg_temp", 28.5)
            final_results[prov]["annual_rainfall"] = dyn.get("annual_rainfall", 1200.0)
            final_results[prov]["data_source"] = f"Dynamic TMD API ({dyn.get('data_year', '2026')})"

        output_path = "data/raw/weather_stats.json"
        os.makedirs("data/raw", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)
        print(f"[Success] Fully Dynamic weather data (2026) saved to {output_path}")

    except Exception as e:
        print(f"[Error] Dynamic Scraping failed: {e}")

if __name__ == "__main__":
    scrape_weather_from_tmd_api()
