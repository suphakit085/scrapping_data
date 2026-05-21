import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_landmarks
from utils.geo_boundaries import (
    prompt_admin_areas,
    prompt_landmark_source_mode,
    prompt_parallel_workers,
    prompt_resume_or_fresh,
)

def main():
    print("========================================")
    print("Starting Landmarks-Only Pipeline")
    print("========================================")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_landmarks_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_landmarks"))
    temp_gmaps_sync_dir = os.path.abspath(os.path.join(script_dir, "data/raw/temp_gmaps_sync"))
    raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/landmarks_raw.json"))
    clean_path = os.path.abspath(os.path.join(script_dir, "data/processed/landmarks_clean.csv"))

    source_mode = prompt_landmark_source_mode(default_mode="both")
    
    # Check resume upfront only for the selected source(s).
    if source_mode in ("both", "osm"):
        prompt_resume_or_fresh("OSM Landmarks", temp_landmarks_dir)
    if source_mode in ("both", "google"):
        prompt_resume_or_fresh("Google Maps Sync", temp_gmaps_sync_dir)
    
    # Prompt user once at the pipeline entrypoint (Upfront Questionnaire)
    extract_admin_areas = prompt_admin_areas("Landmarks Pipeline")
    pw_osm = 2
    pw_gmaps = 3
    if source_mode in ("both", "osm"):
        pw_osm = prompt_parallel_workers("OSM Landmarks", default_workers=2)
    if source_mode in ("both", "google"):
        pw_gmaps = prompt_parallel_workers("Google Maps Sync", default_workers=3)
    
    if source_mode in ("both", "osm"):
        print("\n[1/3] Scraping OSM Landmarks...")
        scrape_landmarks(
            raw_path,
            parallel_workers=pw_osm,
            extract_admin_areas=extract_admin_areas
        )
    
    if source_mode in ("both", "google"):
        if source_mode == "google" and not os.path.exists(raw_path):
            print(f"\n[Warning] Raw baseline not found: {raw_path}")
            print("[Warning] Google Maps Sync will run with an empty dedup baseline.")
        print("\n[2/3] Syncing Google Maps Data...")
        scrape_google_maps_sync(
            osm_raw_path=raw_path,
            output_path=raw_path,
            parallel_workers=pw_gmaps,
            extract_admin_areas=extract_admin_areas
        )
    
    print("\n[3/3] Cleaning and Deduplicating...")
    clean_landmarks(raw_path, clean_path)
    
    print("\n========================================")
    print("Done! Clean data saved to:", clean_path)

if __name__ == "__main__":
    main()
