import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_landmarks
from utils.geo_boundaries import prompt_admin_areas, prompt_parallel_workers

def main():
    print("========================================")
    print("Starting Landmarks-Only Pipeline")
    print("========================================")
    
    # Prompt user once at the pipeline entrypoint (Upfront Questionnaire)
    extract_admin_areas = prompt_admin_areas("Landmarks Pipeline")
    pw_osm = prompt_parallel_workers("OSM Landmarks", default_workers=2)
    pw_gmaps = prompt_parallel_workers("Google Maps Sync", default_workers=3)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/landmarks_raw.json"))
    clean_path = os.path.abspath(os.path.join(script_dir, "data/processed/landmarks_clean.csv"))
    
    print("\n[1/3] Scraping OSM Landmarks...")
    scrape_landmarks(
        raw_path,
        parallel_workers=pw_osm,
        extract_admin_areas=extract_admin_areas
    )
    
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
