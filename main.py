import os
import sys

# Add the root directory to the Python path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.bank_loans import run_scraper as run_bank_scraper
from scrapers.reic_trends import scrape_dotproperty_trends
from scrapers.livinginsider_trends import scrape_livinginsider_trends
from scrapers.landmarks import scrape_landmarks
from scrapers.google_maps_sync import scrape_google_maps_sync
from utils.data_cleaner import clean_bank_loans, clean_property_trends, clean_landmarks
from utils.zone_analyzer import analyze_zones
from utils.aws_uploader import upload_to_s3

def main():
    print("========================================")
    print("Starting Automated Web Scraping Pipeline")
    print("========================================")
    
    raw_bank_path = "data/raw/bank_loans_raw.json"
    raw_dotproperty_path = "data/raw/reic_trends_raw.json"
    raw_livinginsider_path = "data/raw/livinginsider_trends_raw.json"
    raw_landmarks_path = "data/raw/landmarks_raw.json"
    processed_bank_path = "data/processed/bank_loans_clean.csv"
    processed_property_path = "data/processed/property_trends_clean.csv"
    processed_landmarks_path = "data/processed/landmarks_clean.csv"
    processed_zones_path = "data/processed/zone_profiles.csv"
    
    # 1. Scrape Data
    print("\n[Phase 1] Scraping Data...")
    run_bank_scraper(raw_bank_path)
    scrape_dotproperty_trends(raw_dotproperty_path)
    scrape_livinginsider_trends(raw_livinginsider_path)
    scrape_landmarks(raw_landmarks_path)
    scrape_google_maps_sync(raw_landmarks_path, raw_landmarks_path)  # Enrich OSM with Google Maps
    
    # 2. Clean Data
    print("\n[Phase 2] Cleaning and Processing Data...")
    clean_bank_loans(raw_bank_path, processed_bank_path)
    clean_property_trends(raw_dotproperty_path, raw_livinginsider_path, processed_property_path)
    clean_landmarks(raw_landmarks_path, processed_landmarks_path)
    
    # 2b. Zone Analysis (Landmark proximity profiles)
    print("\n[Phase 2b] Analyzing Zone Profiles...")
    analyze_zones(raw_landmarks_path, processed_zones_path, radius_km=2.0)
    
    # 3. Upload to AWS S3 (AWS Glue ETL entry point)
    print("\n[Phase 3] Uploading to AWS S3...")
    
    # IMPORTANT: Replace 'your-target-bucket-name' with your actual S3 bucket
    S3_BUCKET_NAME = "your-target-bucket-name"
    S3_PREFIX = "web-scraping-data/processed/" 
    
    # Note: These will print 'Credentials not available' if you haven't run `aws configure`
    # or set up AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your environment.
    upload_to_s3(processed_bank_path, S3_BUCKET_NAME, S3_PREFIX)
    upload_to_s3(processed_property_path, S3_BUCKET_NAME, S3_PREFIX)
    upload_to_s3(processed_landmarks_path, S3_BUCKET_NAME, S3_PREFIX)
    upload_to_s3(processed_zones_path, S3_BUCKET_NAME, S3_PREFIX)
    
    print("\n========================================")
    print("Pipeline Execution Completed Successfully.")
    print("========================================")

if __name__ == "__main__":
    main()
