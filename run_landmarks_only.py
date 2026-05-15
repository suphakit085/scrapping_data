import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_landmarks

def main():
    print("========================================")
    print("Starting Landmarks-Only Pipeline")
    print("========================================")
    
    raw_path = "data/raw/landmarks_raw.json"
    clean_path = "data/processed/landmarks_clean.csv"
    
    print("\n[1/3] Scraping OSM Landmarks...")
    scrape_landmarks(raw_path)
    
    print("\n[2/3] Syncing Google Maps Data...")
    scrape_google_maps_sync(raw_path, raw_path)
    
    print("\n[3/3] Cleaning and Deduplicating...")
    clean_landmarks(raw_path, clean_path)
    
    print("\n========================================")
    print("Done! Clean data saved to:", clean_path)

if __name__ == "__main__":
    main()
