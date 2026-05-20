import os
import sys

# Add the root directory to the Python path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.bank_loans import run_scraper as run_bank_scraper
from scrapers.dotproperty_trends import scrape_dotproperty_micro_trends as scrape_dotproperty_trends
from scrapers.livinginsider_trends import scrape_livinginsider_micro_trends as scrape_livinginsider_trends
from scrapers.baania_trends import scrape_baania_micro_trends as scrape_baania_trends
from scrapers.landmarks import scrape_landmarks
from scrapers.restaurants import scrape_restaurants
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_bank_loans, clean_landmarks
from utils.property_trends_merger import merge_property_trends
from utils.zone_analyzer import analyze_zones
from utils.aws_uploader import upload_to_s3
from utils.pipeline_quality import validate_pipeline_outputs
from utils.geo_boundaries import prompt_admin_areas, prompt_parallel_workers, prompt_resume_or_fresh


# ============================================================
# Terminal UI — เมนูหลัก
# ============================================================

def prompt_scraper_selection():
    MENU = """
╔══════════════════════════════════════════════════════╗
║       🚀  Web Scraping Pipeline — เมนูหลัก          ║
╠══════════════════════════════════════════════════════╣
║  [1]  รันทุกอย่าง (Full Pipeline)                   ║
║  [2]  ดึงเฉพาะ Landmarks (OSM + Google Maps Sync)   ║
║  [3]  ดึงเฉพาะ Restaurants                          ║
║  [4]  เลือกเองทีละรายการ (Custom)                   ║
║  [q]  ออกจากโปรแกรม                                 ║
╚══════════════════════════════════════════════════════╝"""
    print(MENU)

    while True:
        choice = input("กรุณาเลือก (1/2/3/4/q): ").strip().lower()
        if choice in ('1', '2', '3', '4'):
            return choice
        elif choice in ('q', 'quit', 'exit'):
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        print("❌ เลือกไม่ถูกต้อง กรุณาพิมพ์ 1, 2, 3, 4 หรือ q")


def prompt_custom_selection():
    """ให้ผู้ใช้เลือกทีละรายการ (checkbox-style)"""
    options = {
        "a": ("Bank Loans",          False),
        "b": ("Property Trends",     False),
        "c": ("Landmarks (OSM)",     False),
        "d": ("Google Maps Sync",    False),
        "e": ("Restaurants",         False),
    }
    print("\n📋 เลือกรายการที่ต้องการรัน (พิมพ์รหัสค้างไว้ เช่น ace)")
    print("─────────────────────────────────────────────")
    for key, (label, _) in options.items():
        print(f"   [{key}]  {label}")
    print("   [q]  ออกจากโปรแกรม")
    print("─────────────────────────────────────────────")
    while True:
        raw = input("กรุณาพิมพ์รหัสที่ต้องการ (เช่น ce): ").strip().lower()
        if 'q' in raw:
            print("\n👋 ออกจากโปรแกรมแล้ว")
            raise SystemExit(0)
        selected = {k: (label, k in raw) for k, (label, _) in options.items()}
        chosen = [label for k, (label, on) in selected.items() if on]
        if not chosen:
            print("❌ ไม่ได้เลือกรายการใดเลย กรุณาลองใหม่")
            continue
        print(f"\n✅ จะรัน: {', '.join(chosen)}")
        confirm = input("ยืนยัน? (y/n): ").strip().lower()
        if confirm in ('y', 'yes'):
            return {k: on for k, (label, on) in selected.items()}
        print("↩️  กลับไปเลือกใหม่...")


# ============================================================
# Phase Functions
# ============================================================

def run_landmarks_pipeline(raw_landmarks_path, extract_admin_areas, pw_osm=2, pw_gmaps=3):
    print("\n[Landmarks] Scraping OSM Landmarks...")
    scrape_landmarks(raw_landmarks_path, parallel_workers=pw_osm, extract_admin_areas=extract_admin_areas)
    print("\n[Landmarks] Syncing Google Maps Data...")
    scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path, parallel_workers=pw_gmaps, extract_admin_areas=extract_admin_areas)

def run_restaurants_pipeline(restaurants_raw_path, extract_admin_areas, pw_restaurants=4):
    print("\n[Restaurants] Scraping...")
    scrape_restaurants(restaurants_raw_path, parallel_workers=pw_restaurants, extract_admin_areas=extract_admin_areas)

def run_clean_phase(raw_bank_path, raw_baania_path, raw_livinginsider_path,
                    raw_dotproperty_path, raw_landmarks_path,
                    processed_bank_path, processed_property_path, processed_landmarks_path):
    print("\n[Phase 2] Cleaning and Processing Data...")
    if os.path.exists(raw_bank_path):
        clean_bank_loans(raw_bank_path, processed_bank_path)
    if all(os.path.exists(p) for p in [raw_baania_path, raw_livinginsider_path, raw_dotproperty_path]):
        merge_property_trends(
            baania_path=raw_baania_path,
            livinginsider_path=raw_livinginsider_path,
            output_path=processed_property_path,
            dotproperty_path=raw_dotproperty_path
        )
    if os.path.exists(raw_landmarks_path):
        clean_landmarks(raw_landmarks_path, processed_landmarks_path)

def run_s3_upload(processed_bank_path, processed_property_path, processed_landmarks_path, processed_zones_path):
    print("\n[Phase 3] Uploading to AWS S3...")
    S3_BUCKET_NAME = "your-target-bucket-name"
    S3_PREFIX = "web-scraping-data/processed/"
    for path in [processed_bank_path, processed_property_path, processed_landmarks_path, processed_zones_path]:
        upload_to_s3(path, S3_BUCKET_NAME, S3_PREFIX)


# ============================================================
# Main
# ============================================================

def main():
    print("╔══════════════════════════════════════════════════════╗")
    print("║       🤖  Automated Web Scraping Pipeline            ║")
    print("╚══════════════════════════════════════════════════════╝")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Paths (Absolute)
    raw_bank_path          = os.path.abspath(os.path.join(script_dir, "data/raw/bank_loans_raw.json"))
    raw_dotproperty_path   = os.path.abspath(os.path.join(script_dir, "data/raw/dotproperty_trends_raw.json"))
    raw_baania_path        = os.path.abspath(os.path.join(script_dir, "data/raw/baania_trends_raw.json"))
    raw_livinginsider_path = os.path.abspath(os.path.join(script_dir, "data/raw/livinginsider_trends_raw.json"))
    raw_landmarks_path     = os.path.abspath(os.path.join(script_dir, "data/raw/landmarks_raw.json"))
    restaurants_raw_path   = os.path.abspath(os.path.join(script_dir, "data/raw/restaurants_raw.json"))
    processed_bank_path        = os.path.abspath(os.path.join(script_dir, "data/processed/bank_loans_clean.csv"))
    reic_processed_path        = os.path.abspath(os.path.join(script_dir, "data/processed/reic_trends.csv"))
    processed_property_path    = os.path.abspath(os.path.join(script_dir, "data/processed/property_trends.csv"))
    processed_landmarks_path   = os.path.abspath(os.path.join(script_dir, "data/processed/landmarks_clean.csv"))
    processed_zones_path       = os.path.abspath(os.path.join(script_dir, "data/processed/zone_profiles.csv"))

    # ── เมนูหลัก ──────────────────────────────────────────
    mode = prompt_scraper_selection()

    # If custom, resolve custom selection upfront
    custom_sel = None
    if mode == '4':
        custom_sel = prompt_custom_selection()

    # ── Check Resume/Start Fresh upfront conditionally ──
    temp_landmarks_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_landmarks"))
    temp_gmaps_sync_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_gmaps_sync"))
    temp_restaurants_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_restaurants"))

    if mode == '1':
        prompt_resume_or_fresh("OSM Landmarks", temp_landmarks_dir)
        prompt_resume_or_fresh("Google Maps Sync", temp_gmaps_sync_dir)
        prompt_resume_or_fresh("Restaurants", temp_restaurants_dir)
    elif mode == '2':
        prompt_resume_or_fresh("OSM Landmarks", temp_landmarks_dir)
        prompt_resume_or_fresh("Google Maps Sync", temp_gmaps_sync_dir)
    elif mode == '3':
        prompt_resume_or_fresh("Restaurants", temp_restaurants_dir)
    elif mode == '4' and custom_sel:
        if custom_sel.get('c'):
            prompt_resume_or_fresh("OSM Landmarks", temp_landmarks_dir)
        if custom_sel.get('d'):
            prompt_resume_or_fresh("Google Maps Sync", temp_gmaps_sync_dir)
        if custom_sel.get('e'):
            prompt_resume_or_fresh("Restaurants", temp_restaurants_dir)

    # ── ถามเรื่อง District/Sub-district ──────────────────
    extract_admin_areas = prompt_admin_areas("Pipeline")

    # ── Upfront Questionnaire for Parallel Workers ───────
    pw_osm = 2
    pw_gmaps = 3
    pw_restaurants = 4

    if mode == '1':
        pw_osm = prompt_parallel_workers("OSM Landmarks", default_workers=2)
        pw_gmaps = prompt_parallel_workers("Google Maps Sync", default_workers=3)
        pw_restaurants = prompt_parallel_workers("Restaurants", default_workers=4)
    elif mode == '2':
        pw_osm = prompt_parallel_workers("OSM Landmarks", default_workers=2)
        pw_gmaps = prompt_parallel_workers("Google Maps Sync", default_workers=3)
    elif mode == '3':
        pw_restaurants = prompt_parallel_workers("Restaurants", default_workers=4)
    elif mode == '4' and custom_sel:
        if custom_sel.get('c'):
            pw_osm = prompt_parallel_workers("OSM Landmarks", default_workers=2)
        if custom_sel.get('d'):
            pw_gmaps = prompt_parallel_workers("Google Maps Sync", default_workers=3)
        if custom_sel.get('e'):
            pw_restaurants = prompt_parallel_workers("Restaurants", default_workers=4)

    # ── รันตาม Mode ───────────────────────────────────────
    if mode == '1':
        # Full Pipeline
        print("\n🚀 รันทุกอย่าง (Full Pipeline)")
        print("\n[Phase 1] Scraping Data...")
        run_bank_scraper(raw_bank_path)
        scrape_dotproperty_trends(raw_dotproperty_path)
        scrape_baania_trends(raw_baania_path)
        scrape_livinginsider_trends(raw_livinginsider_path)
        run_landmarks_pipeline(raw_landmarks_path, extract_admin_areas, pw_osm=pw_osm, pw_gmaps=pw_gmaps)
        run_restaurants_pipeline(restaurants_raw_path, extract_admin_areas, pw_restaurants=pw_restaurants)
        run_clean_phase(raw_bank_path, raw_baania_path, raw_livinginsider_path,
                        raw_dotproperty_path, raw_landmarks_path,
                        processed_bank_path, processed_property_path, processed_landmarks_path)

    elif mode == '2':
        # Landmarks only
        print("\n🏛️  ดึงเฉพาะ Landmarks")
        run_landmarks_pipeline(raw_landmarks_path, extract_admin_areas, pw_osm=pw_osm, pw_gmaps=pw_gmaps)
        if os.path.exists(raw_landmarks_path):
            clean_landmarks(raw_landmarks_path, processed_landmarks_path)

    elif mode == '3':
        # Restaurants only
        print("\n🍜  ดึงเฉพาะ Restaurants")
        run_restaurants_pipeline(restaurants_raw_path, extract_admin_areas, pw_restaurants=pw_restaurants)

    elif mode == '4':
        # Custom
        print("\n🛠️  โหมด Custom")
        print("\n[Phase 1] Scraping Data...")
        if custom_sel.get('a'): run_bank_scraper(raw_bank_path)
        if custom_sel.get('b'):
            scrape_dotproperty_trends(raw_dotproperty_path)
            scrape_baania_trends(raw_baania_path)
            scrape_livinginsider_trends(raw_livinginsider_path)
        if custom_sel.get('c'): scrape_landmarks(raw_landmarks_path, parallel_workers=pw_osm, extract_admin_areas=extract_admin_areas)
        if custom_sel.get('d'): scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path, parallel_workers=pw_gmaps, extract_admin_areas=extract_admin_areas)
        if custom_sel.get('e'): run_restaurants_pipeline(restaurants_raw_path, extract_admin_areas, pw_restaurants=pw_restaurants)

        run_clean_phase(raw_bank_path, raw_baania_path, raw_livinginsider_path,
                        raw_dotproperty_path, raw_landmarks_path,
                        processed_bank_path, processed_property_path, processed_landmarks_path)

    # ── Zone Analysis & Quality Gate (เฉพาะ Full Pipeline) ──
    if mode == '1':
        print("\n[Phase 2b] Analyzing Zone Profiles...")
        analyze_zones(
            raw_landmarks_path, processed_zones_path, radius_km=2.0,
            landmarks_clean_path=processed_landmarks_path,
            property_trends_path=processed_property_path,
            reic_trends_path=reic_processed_path,
            population_path=os.path.abspath(os.path.join(script_dir, "data/processed/population_stats.csv")),
            road_path=os.path.abspath(os.path.join(script_dir, "data/raw/road_network.json")),
            flood_path=os.path.abspath(os.path.join(script_dir, "data/raw/flood_risk_raw.json"))
        )
        print("\n[Phase 2c] Validating Processed Outputs...")
        is_valid, quality_messages = validate_pipeline_outputs(
            landmarks_path=processed_landmarks_path,
            property_trends_path=processed_property_path,
            zones_path=processed_zones_path,
            expected_province_count=10,
        )
        for msg in quality_messages:
            print(msg)
        if not is_valid:
            raise RuntimeError("Data quality gate failed. Skip S3 upload.")
        run_s3_upload(processed_bank_path, processed_property_path, processed_landmarks_path, processed_zones_path)

    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  ✅  Pipeline Execution Completed Successfully!      ║")
    print("╚══════════════════════════════════════════════════════╝")

if __name__ == "__main__":
    main()
