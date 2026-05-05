# -*- coding: utf-8 -*-
"""
Main Pipeline: Landmarks + Micro-Zone Intelligence (v5.0)
Full Automation: Scrape -> Clean -> Analyze -> Validate
"""

import sys
import os
import pandas as pd

# Enforce UTF-8 for terminal output (fixes Mojibake on Windows CMD)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from scrapers.landmarks import scrape_landmarks
from scrapers.baania_trends import scrape_baania_micro_trends
from scrapers.livinginsider_trends import scrape_livinginsider_micro_trends
from scrapers.dotproperty_trends import scrape_dotproperty_micro_trends
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
    print(f"🚀 STARTING FULL MICRO-ZONE INTELLIGENCE PIPELINE (v5.2)")
    print(f"Target: 10 Provinces | Granularity: Tambon Level")
    print(f"{'='*70}")

    # Step 1: Environment & Setup
    print("\n[Step 1] Preparing Master Lookups...")
    # (Tambon lookup is now dynamically handled via Nominatim Reverse Geocoding in v5.1)

    # Step 2: Pillar Data Collection (Focus: Population & Weather)
    print("\n[Step 2] Collecting Core Pillar Data...")
    # ประชากร (Age Groups / Density)
    scrape_population_age_groups("data/processed/population_stats.csv")
    # สภาพอากาศ 2026 (TMD API)
    scrape_weather_from_tmd_api()
    
    # Step 3: Strategic Infrastructure (Landmarks & Roads)
    print("\n[Step 3] Collecting Infrastructure Data...")
    raw_landmarks_path = "data/raw/landmarks_raw.json"
    road_path = "data/raw/road_network.json"
    
    # 1. Landmarks (Pillar 1)
    if not os.path.exists(raw_landmarks_path) or os.path.getsize(raw_landmarks_path) < 100:
        print("   -> Scraping Primary Landmark Anchors...")
        scrape_landmarks(raw_landmarks_path)
    
    # 2. Roads (Pillar 2 - OSM Connectivity)
    from scrapers.road_analysis import fetch_road_network
    print("   -> Analyzing Road Networks (OSM)...")
    fetch_road_network(raw_landmarks_path, road_path)

    # 3. Google Maps Sync (Pillar 1 Enrichment)
    print("   -> Syncing Premium Amenities (Malls, Hospitals, etc.)...")
    scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path)
    clean_landmarks(raw_landmarks_path, "data/processed/landmarks_clean.csv")

    # Step 4: Final 4-Pillar Analysis (The Green Frame)
    print("\n[Step 4] Running Green-Frame Micro-Zone Analysis...")
    processed_zones_path = "data/processed/zone_profiles.csv"
    analyze_zones(
        raw_landmarks_path,
        processed_zones_path,
        radius_km=2.0,
        population_path="data/processed/population_stats.csv",
        weather_path="data/raw/weather_stats.json",
        road_path="data/raw/road_network.json",
        flood_path="data/raw/flood_risk_raw.json"
    )

    # Step 5: Validation
    print("\n[Step 5] Quality Assurance Check...")
    # The pipeline quality tool expects 3 paths.
    # Since run_zones_only might not have freshly merged trends, we point to the existing paths
    is_valid, messages = validate_pipeline_outputs(
        landmarks_path="data/processed/landmarks_clean.csv",
        property_trends_path="data/processed/property_trends.csv",
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
