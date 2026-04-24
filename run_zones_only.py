"""
Landmarks & Zone Analysis Pipeline (แยกส่วนเฉพาะทำเล)
รันเฉพาะ:
1. Scrape OSM Landmarks
2. Sync Google Maps (Hybrid)
3. Clean Landmarks
4. Zone Analysis (Calculate Scores)
"""

import os
from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_landmarks
from utils.zone_analyzer import analyze_zones

def run_landmarks_pipeline():
    print("========================================")
    print("🚀 Running Landmarks & Zone Analysis ONLY")
    print("========================================")
    
    raw_landmarks_path = "data/raw/landmarks_raw.json"
    processed_landmarks_path = "data/processed/landmarks_clean.csv"
    processed_zones_path = "data/processed/zone_profiles.csv"
    
    # 1. Scrape & Enrich
    print("\n[Step 1] Scraping OSM Landmarks...")
    scrape_landmarks(raw_landmarks_path)
    
    print("\n[Step 2] Syncing with Google Maps (Enrichment)...")
    scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path)
    
    # 2. Process
    print("\n[Step 3] Cleaning Landmarks...")
    clean_landmarks(raw_landmarks_path, processed_landmarks_path)
    
    print("\n[Step 4] Generating Zone Profiles (Livability Score)...")
    analyze_zones(raw_landmarks_path, processed_zones_path,
                  radius_km=2.0,
                  landmarks_clean_path=processed_landmarks_path)
    
    print("\n========================================")
    print("✅ Landmarks & Zone Pipeline Completed!")
    print(f"Result 1: {processed_landmarks_path}")
    print(f"Result 2: {processed_zones_path}")
    print("========================================")

if __name__ == "__main__":
    run_landmarks_pipeline()
