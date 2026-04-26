"""
Main Pipeline: Landmarks + Micro-Zone Intelligence (v5.0)
Full Automation: Scrape -> Clean -> Analyze -> Validate
"""

import os
import pandas as pd
from scrapers.landmarks import scrape_landmarks
from scrapers.baania_trends import scrape_baania_micro_trends
from scrapers.google_maps_sync import scrape_google_maps_sync
from scrapers.weather_data import scrape_weather_from_tmd_api
from scrapers.population_dopa import scrape_population_age_groups
from scrapers.setup_tambons import setup_tambon_coordinates
from utils.data_cleaner import clean_landmarks
from utils.property_trends_merger import merge_property_trends
from utils.zone_analyzer import analyze_zones
from utils.pipeline_quality import validate_pipeline_outputs

def run_full_micro_pipeline():
    print(f"\n{'='*70}")
    print(f"🚀 STARTING FULL MICRO-ZONE INTELLIGENCE PIPELINE (v5.0)")
    print(f"Target: 10 Provinces | Granularity: Tambon Level")
    print(f"{'='*70}")

    # Step 1: Environment & Setup
    print("\n[Step 1] Preparing Master Lookups...")
    # (Tambon lookup is now dynamically handled via Nominatim Reverse Geocoding in v5.1)

    # Step 2: Dynamic Data Collection (The Heavy Work)
    print("\n[Step 2] Updating Dynamic Data Sources...")
    # ประชากรรายตำบล
    scrape_population_age_groups("data/processed/population_stats.csv")
    # สภาพอากาศ 2026
    scrape_weather_from_tmd_api()
    # ราคาอสังหาฯ รายตำบล
    scrape_baania_micro_trends("data/raw/baania_trends_raw.json")
    
    # Step 3: Landmarks & Sync (Only if needed, or run from cache)
    raw_landmarks_path = "data/raw/landmarks_raw.json"
    processed_landmarks_path = "data/processed/landmarks_clean.csv"
    if not os.path.exists(raw_landmarks_path):
        print("\n[Step 3] Scraping Primary Landmarks...")
        scrape_landmarks(raw_landmarks_path)
    
    # Step 4: Cleaning & Merging
    print("\n[Step 4] Cleaning and Merging Datasets...")
    clean_landmarks(raw_landmarks_path, processed_landmarks_path)
    
    # Step 5: Final Micro-Zone Analysis (The BI Engine)
    print("\n[Step 5] Executing v5.0 Micro-Zone Analyzer...")
    processed_zones_path = "data/processed/zone_profiles.csv"
    analyze_zones(
        raw_landmarks_path,
        processed_zones_path,
        radius_km=2.0,
        landmarks_clean_path=processed_landmarks_path,
        population_path="data/processed/population_stats.csv",
        weather_path="data/raw/weather_stats.json"
    )

    # Step 6: Validation
    print("\n[Step 6] Quality Assurance Check...")
    is_valid, messages = validate_pipeline_outputs(
        landmarks_path=processed_landmarks_path,
        zones_path=processed_zones_path
    )
    
    if is_valid:
        print(f"\n{'='*70}")
        print(f"✅ SUCCESS: All 10 Provinces are now Analyzed at Micro-Level!")
        print(f"Results: {processed_zones_path}")
        print(f"{'='*70}")
    else:
        print(f"\n⚠️ WARNING: Pipeline completed with some data issues: {messages}")

if __name__ == "__main__":
    run_full_micro_pipeline()
