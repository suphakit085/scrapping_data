"""
Landmarks & Zone Analysis Pipeline (แยกส่วนเฉพาะทำเล)
รันเฉพาะ:
1. Scrape OSM Landmarks
2. Sync Google Maps (Hybrid)
3. Clean Landmarks (Dedup)
4. Merge Property Trends (Baania + LivingInsider)
5. Zone Analysis (Calculate Scores + Price Enrichment)
"""

import os
from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_landmarks
from utils.property_trends_merger import merge_property_trends
from utils.zone_analyzer import analyze_zones
from utils.pipeline_quality import validate_pipeline_outputs

def run_landmarks_pipeline():
    print("========================================")
    print("Running Landmarks & Zone Analysis ONLY")
    print("========================================")
    
    raw_landmarks_path       = "data/raw/landmarks_raw.json"
    processed_landmarks_path = "data/processed/landmarks_clean.csv"
    processed_zones_path     = "data/processed/zone_profiles.csv"
    baania_raw_path          = "data/raw/baania_trends_raw.json"
    livinginsider_raw_path   = "data/raw/livinginsider_trends_raw.json"
    dotproperty_raw_path     = "data/raw/reic_trends_raw.json"
    property_trends_path     = "data/processed/property_trends.csv"
    
    # Step 1: Scrape Landmarks
    print("\n[Step 1] Scraping OSM Landmarks...")
    scrape_landmarks(raw_landmarks_path)
    
    # Step 2: Sync Google Maps
    print("\n[Step 2] Syncing with Google Maps (Enrichment)...")
    scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path)
    
    # Step 3: Clean & Dedup Landmarks
    print("\n[Step 3] Cleaning Landmarks...")
    clean_landmarks(raw_landmarks_path, processed_landmarks_path)
    
    # Step 4: Merge Property Trends
    print("\n[Step 4] Merging Property Trends (Baania + LivingInsider)...")
    merge_property_trends(
        baania_path=baania_raw_path,
        livinginsider_path=livinginsider_raw_path,
        output_path=property_trends_path,
        dotproperty_path=dotproperty_raw_path
    )
    
    # Step 5: Zone Analysis (Livability Score + Price Enrichment)
    print("\n[Step 5] Generating Zone Profiles (Livability Score + Price Data)...")
    analyze_zones(
        raw_landmarks_path,
        processed_zones_path,
        radius_km=2.0,
        landmarks_clean_path=processed_landmarks_path,
        property_trends_path=property_trends_path
    )

    # Step 6: Data Quality Gate
    print("\n[Step 6] Validating Processed Outputs...")
    is_valid, quality_messages = validate_pipeline_outputs(
        landmarks_path=processed_landmarks_path,
        property_trends_path=property_trends_path,
        zones_path=processed_zones_path,
        expected_province_count=10,
    )
    for msg in quality_messages:
        print(msg)
    if not is_valid:
        raise RuntimeError("Data quality gate failed.")

    print("\n========================================")
    print("Landmarks & Zone Pipeline Completed!")
    print(f"Result 1: {processed_landmarks_path}")
    print(f"Result 2: {property_trends_path}")
    print(f"Result 3: {processed_zones_path}")
    print("========================================")

if __name__ == "__main__":
    run_landmarks_pipeline()
