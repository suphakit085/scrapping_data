import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.restaurants import scrape_restaurants
from utils.data_cleaner import clean_landmarks
from utils.geo_boundaries import prompt_admin_areas, prompt_parallel_workers

def main():
    print("========================================")
    print("Starting Restaurants-Only Pipeline")
    print("========================================")
    
    # Prompt user once at the pipeline entrypoint
    extract_admin_areas = prompt_admin_areas("Restaurants Pipeline")
    pw_restaurants = prompt_parallel_workers("Restaurants", default_workers=4)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # กำหนด Path ของไฟล์ต่างๆ (แบบ absolute ปลอดภัยและชัดเจน)
    restaurants_raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/restaurants_raw.json"))
    landmarks_raw_path = os.path.abspath(os.path.join(script_dir, "data/raw/landmarks_raw.json"))
    
    clean_combined_path = os.path.abspath(os.path.join(script_dir, "data/processed/landmarks_clean.csv"))
    restaurants_clean_path = os.path.abspath(os.path.join(script_dir, "data/processed/restaurants.csv"))
    
    # 1. ดึงข้อมูลร้านอาหาร (OSM + Google Maps)
    print("\n[1/2] Scraping Restaurants...")
    scrape_restaurants(
        restaurants_raw_path,
        parallel_workers=pw_restaurants,
        extract_admin_areas=extract_admin_areas
    )
    
    # 2. รวมและทำความสะอาดไฟล์
    print("\n[2/2] Cleaning and Merging Data...")
    clean_landmarks(
        raw_file_paths=[landmarks_raw_path, restaurants_raw_path],
        processed_file_path=clean_combined_path,
        restaurants_output_path=restaurants_clean_path
    )
    
    print("\n========================================")
    print("✅ Done! Data saved to:")
    print(f"  - Combined: {clean_combined_path}")
    print(f"  - Restaurants Only: {restaurants_clean_path}")

if __name__ == "__main__":
    main()
