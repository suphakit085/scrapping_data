import os
import sys

# Force standard streams to use UTF-8 to prevent charmap encoding errors on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.restaurants import scrape_restaurants
from utils.data_cleaner import clean_landmarks
from utils.geo_boundaries import prompt_admin_areas, prompt_parallel_workers, prompt_resume_or_fresh

PROVINCE_OPTIONS = [
    {"name": "ขอนแก่น",        "slug": "khon-kaen"},
    {"name": "อุบลราชธานี",     "slug": "ubon-ratchathani"},
    {"name": "ประจวบคีรีขันธ์", "slug": "prachuap-khiri-khan"},
    {"name": "อุดรธานี",        "slug": "udon-thani"},
    {"name": "ระยอง",           "slug": "rayong"},
    {"name": "ชลบุรี",          "slug": "chonburi"},
    {"name": "สุรินทร์",        "slug": "surin"},
    {"name": "บุรีรัมย์",       "slug": "buriram"},
    {"name": "พิษณุโลก",        "slug": "phitsanulok"},
    {"name": "เชียงราย",        "slug": "chiang-rai"},
]

def prompt_province_selection():
    # If environment variable is set, bypass prompt
    env_choice = os.environ.get("PROVINCE")
    if env_choice:
        env_choice = env_choice.strip().lower()
        if env_choice in ('a', 'all'):
            print(f"[CI/Non-Interactive] Selected All Provinces via Environment Variable")
            return None
        for prov in PROVINCE_OPTIONS:
            if prov['slug'] == env_choice or prov['name'] == env_choice:
                print(f"[CI/Non-Interactive] Selected Province via Environment Variable: {prov['name']} ({prov['slug']})")
                return prov
        print(f"[CI/Non-Interactive] Invalid PROVINCE='{env_choice}', defaulting to All Provinces")
        return None

    print("\n[Terminal UI - Select Province]")
    print("เลือกจังหวัดที่ต้องการรันข้อมูลร้านอาหาร:")
    for idx, prov in enumerate(PROVINCE_OPTIONS, 1):
        print(f"   [{idx}] {prov['name']} ({prov['slug']})")
    print("   [a] เลือกทั้งหมด (All Provinces)")
    print("   [q] ออกจากโปรแกรม")
    
    while True:
        choice = input("กรุณาเลือก (1-10, a หรือ q): ").strip().lower()
        if choice in ('q', 'quit', 'exit'):
            print("\nออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        if choice == 'a':
            return None  # รันทั้งหมด
        try:
            val = int(choice)
            if 1 <= val <= len(PROVINCE_OPTIONS):
                return PROVINCE_OPTIONS[val-1]
        except ValueError:
            pass
        print(f"เลือกไม่ถูกต้อง กรุณาเลือก 1 ถึง {len(PROVINCE_OPTIONS)} หรือพิมพ์ a/q")

def main():
    print("========================================")
    print("Starting Restaurants-Only Pipeline")
    print("========================================")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 🆕 ถามจังหวัดที่ต้องการรันก่อน
    selected_prov = prompt_province_selection()
    
    # 🆕 กำหนดชื่อไฟล์ดิบและไฟล์คลีนตามผลการเลือก
    if selected_prov:
        prov_slug = selected_prov['slug']
        restaurants_raw_path = os.path.abspath(os.path.join(script_dir, f"data/raw/restaurants_{prov_slug}_raw.json"))
        restaurants_clean_path = os.path.abspath(os.path.join(script_dir, f"data/processed/restaurants_{prov_slug}_clean.csv"))
        selected_slugs = [prov_slug]
        print(f"\n[Selected] คุณเลือกจังหวัด: {selected_prov['name']} ({prov_slug})")
    else:
        restaurants_raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/restaurants_raw.json"))
        restaurants_clean_path = os.path.abspath(os.path.join(script_dir, "data/processed/restaurants.csv"))
        selected_slugs = None
        print("\n[Selected] คุณเลือกดึงข้อมูลทุกจังหวัด (All Provinces)")
        
    temp_restaurants_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_restaurants"))
    
    # Check resume upfront
    prompt_resume_or_fresh("Restaurants Pipeline", temp_restaurants_dir)
    
    # Prompt user once at the pipeline entrypoint
    extract_admin_areas = prompt_admin_areas("Restaurants Pipeline")
    pw_restaurants = prompt_parallel_workers("Restaurants", default_workers=4)
    
    landmarks_raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/landmarks_raw.json"))
    clean_combined_path = os.path.abspath(os.path.join(script_dir, "data/processed/landmarks_clean.csv"))
    
    # 1. ดึงข้อมูลร้านอาหาร (OSM + Google Maps)
    print("\n[1/2] Scraping Restaurants...")
    scrape_restaurants(
        restaurants_raw_path,
        parallel_workers=pw_restaurants,
        extract_admin_areas=extract_admin_areas,
        selected_provinces=selected_slugs
    )
    
    # 2. รวมและทำความสะอาดไฟล์
    print("\n[2/2] Cleaning and Merging Data...")
    if selected_slugs:
        # หากเจาะจงจังหวัด ให้คลีนเฉพาะร้านอาหารของจังหวัดนั้น
        clean_landmarks(
            raw_file_paths=[restaurants_raw_path],
            processed_file_path=clean_combined_path,
            restaurants_output_path=restaurants_clean_path
        )
    else:
        # หากดึงทั้งหมด ให้ทำการคลีนแบบเดิมร่วมกับแลนด์มาร์ก
        clean_landmarks(
            raw_file_paths=[landmarks_raw_path, restaurants_raw_path],
            processed_file_path=clean_combined_path,
            restaurants_output_path=restaurants_clean_path
        )
    
    print("\n========================================")
    print("✅ Done! Data saved to:")
    if not selected_slugs:
        print(f"  - Combined: {clean_combined_path}")
    print(f"  - Restaurants Only: {restaurants_clean_path}")

if __name__ == "__main__":
    main()
